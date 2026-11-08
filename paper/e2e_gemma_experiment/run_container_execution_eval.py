#!/usr/bin/env python3
"""
Containerized Patch Test Execution Benchmark for Gemma 4 Real Run.

Executes all 120 real model proposed code patches in an isolated,
unprivileged Docker container (gemma4-eval-sandbox:latest) with:
- --network none (no internet, no intranet)
- --user 1000:1000 (unprivileged user)
- --cap-drop ALL (no Linux capabilities)
- --memory 512m (RAM limit)
- --cpus 1.0 (CPU core limit)
- --pids-limit 64 (fork bomb protection)
- -v <tmpdir>:/sandbox:ro (read-only mount)
- --tmpfs /tmp (ephemeral scratch for pytest cache)
- Zero host environment variables or cloud secrets passed.

Measures:
- Patch Test Pass Rate per variant (A_raw, B_compressed, C_tail35, D_no_trace)
- Task-clustered bootstrap paired differences and permutation p-values
- Detailed classification of test failure root causes
"""
import os
import sys
import json
import time
import math
import random
import shutil
import tempfile
import subprocess
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent.parent
TASKS_DIR = BASE_DIR / "tasks"
REAL_RUN_DIR = BASE_DIR / "real_run_20261108"
CHECKPOINT_FILE = REAL_RUN_DIR / "real_experiment_checkpoint.jsonl"
EXECUTION_RESULTS_FILE = REAL_RUN_DIR / "real_patch_execution_results.jsonl"
EXECUTION_ANALYSIS_FILE = REAL_RUN_DIR / "real_patch_execution_analysis.json"
EXECUTION_REPORT_FILE = REAL_RUN_DIR / "REAL_PATCH_EXECUTION_REPORT.md"

# Load local statistics module safely avoiding stdlib clash
stat_spec = importlib.util.spec_from_file_location("local_exp_statistics", BASE_DIR / "statistics.py")
local_stats = importlib.util.module_from_spec(stat_spec)
stat_spec.loader.exec_module(local_stats)
validate_dataset_integrity = local_stats.validate_dataset_integrity
compute_task_clustered_paired_stats = local_stats.compute_task_clustered_paired_stats

eval_spec = importlib.util.spec_from_file_location("local_evaluator", BASE_DIR / "evaluator.py")
local_evaluator = importlib.util.module_from_spec(eval_spec)
eval_spec.loader.exec_module(local_evaluator)
parse_structured_response = local_evaluator.parse_structured_response
check_preflight_syntax = local_evaluator.check_preflight_syntax

DOCKER_IMAGE = "gemma4-eval-sandbox:latest"
CONTAINER_TIMEOUT_SEC = 20

def run_single_patch_test(record: dict) -> dict:
    """Execute candidate patch in isolated docker container."""
    task_id = record["task_id"]
    variant = record["variant"]
    seed = record["seed"]
    response_text = record["model_response"]
    
    parsed = parse_structured_response(response_text)
    candidate_code = parsed["code"]
    
    # 1. Preflight syntax check
    syntax_pass, syntax_err = check_preflight_syntax(candidate_code)
    if not syntax_pass:
        return {
            "task_id": task_id,
            "variant": variant,
            "seed": seed,
            "patch_test_pass": False,
            "exit_code": -1,
            "execution_status": "SYNTAX_ERROR_ABORT",
            "failure_category": "SYNTAX_ERROR",
            "failure_reason": syntax_err,
            "exec_latency_sec": 0.0,
            "test_output": f"Preflight syntax check failed: {syntax_err}",
            "candidate_code_len": len(candidate_code)
        }
        
    task_dir = TASKS_DIR / task_id
    test_task_file = task_dir / "test_task.py"
    if not test_task_file.exists():
        return {
            "task_id": task_id,
            "variant": variant,
            "seed": seed,
            "patch_test_pass": False,
            "exit_code": -2,
            "execution_status": "HARNESS_ERROR",
            "failure_category": "HARNESS_ERROR",
            "failure_reason": f"Missing test harness {test_task_file}",
            "exec_latency_sec": 0.0,
            "test_output": "Test file not found",
            "candidate_code_len": len(candidate_code)
        }
        
    # 2. Prepare isolated staging dir
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        shutil.copy(test_task_file, tmp_p / "test_task.py")
        (tmp_p / "source.py").write_text(candidate_code, encoding="utf-8")
        
        # Set world-readable permissions for container user 1000
        tmp_p.chmod(0o755)
        (tmp_p / "test_task.py").chmod(0o644)
        (tmp_p / "source.py").chmod(0o644)
        
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--user", "1000:1000",
            "--cap-drop", "ALL",
            "--memory", "512m",
            "--cpus", "1.0",
            "--pids-limit", "64",
            "-v", f"{tmpdir}:/sandbox:ro",
            "--tmpfs", "/tmp",
            "-e", "PYTHONPATH=/sandbox",
            DOCKER_IMAGE,
            "python3", "-m", "pytest", "/sandbox/test_task.py", "-q", "-o", "cache_dir=/tmp/.pytest_cache"
        ]
        
        t0 = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CONTAINER_TIMEOUT_SEC
            )
            exec_latency = time.perf_counter() - t0
            exit_code = res.returncode
            stdout = res.stdout
            stderr = res.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            exec_latency = time.perf_counter() - t0
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            timed_out = True

        combined_output = (stdout + "\n" + stderr).strip()
        
        if timed_out:
            pass_status = False
            exec_status = "TIMEOUT_EXPIRED"
            fail_category = "TIMEOUT"
            fail_reason = f"Execution exceeded {CONTAINER_TIMEOUT_SEC}s limit"
        elif exit_code == 0:
            pass_status = True
            exec_status = "CONTAINER_EXECUTION_PASS"
            fail_category = "NONE"
            fail_reason = ""
        else:
            pass_status = False
            exec_status = "CONTAINER_EXECUTION_FAIL"
            # Categorize failure from output
            fail_category = "TEST_ASSERTION_FAILURE"
            fail_reason = "Test assertions failed"
            if "AttributeError" in combined_output:
                fail_category = "ATTRIBUTE_ERROR"
            elif "TypeError" in combined_output:
                fail_category = "TYPE_ERROR"
            elif "ValueError" in combined_output:
                fail_category = "VALUE_ERROR"
            elif "KeyError" in combined_output:
                fail_category = "KEY_ERROR"
            elif "ImportError" in combined_output or "ModuleNotFoundError" in combined_output:
                fail_category = "IMPORT_ERROR"
            elif "AssertionError" in combined_output:
                fail_category = "ASSERTION_ERROR"
                
            # Extract first failure line
            for line in combined_output.splitlines():
                line_str = line.strip()
                if line_str.startswith("E   ") or "FAILED" in line_str:
                    fail_reason = line_str[:120]
                    break

        return {
            "task_id": task_id,
            "variant": variant,
            "seed": seed,
            "patch_test_pass": pass_status,
            "exit_code": exit_code,
            "execution_status": exec_status,
            "failure_category": fail_category,
            "failure_reason": fail_reason,
            "exec_latency_sec": round(exec_latency, 3),
            "test_output": combined_output[:600],
            "candidate_code_len": len(candidate_code)
        }

def compute_variant_ci(execution_results: list[dict], variant: str, n_bootstrap: int = 10000, seed: int = 42) -> dict:
    """Compute task-clustered bootstrap CI for single variant pass rate."""
    var_records = [r for r in execution_results if r["variant"] == variant]
    tasks = sorted(list(set(r["task_id"] for r in var_records)))
    task_means = []
    for tid in tasks:
        t_recs = [r for r in var_records if r["task_id"] == tid]
        task_means.append(sum(1.0 if r["patch_test_pass"] else 0.0 for r in t_recs) / len(t_recs))
        
    n_tasks = len(task_means)
    obs_mean = sum(task_means) / n_tasks
    se = math.sqrt(obs_mean * (1.0 - obs_mean) / len(var_records)) if len(var_records) > 0 else 0.0
    
    rng = random.Random(seed)
    boot_means = []
    for _ in range(n_bootstrap):
        resampled = [task_means[rng.randrange(n_tasks)] for _ in range(n_tasks)]
        boot_means.append(sum(resampled) / n_tasks)
    boot_means.sort()
    
    ci_lower = boot_means[int(0.025 * n_bootstrap)]
    ci_upper = boot_means[int(0.975 * n_bootstrap)]
    
    passes = sum(1 for r in var_records if r["patch_test_pass"])
    return {
        "variant": variant,
        "sample_size": len(var_records),
        "passes": passes,
        "mean": obs_mean,
        "se": se,
        "ci_95": [ci_lower, ci_upper]
    }

def main():
    print(f"Loading checkpoint records from {CHECKPOINT_FILE}...")
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
        
    print(f"Loaded {len(records)} records. Validating integrity...")
    integrity = validate_dataset_integrity(records)
    if not integrity["is_complete"]:
        raise ValueError(f"Integrity check failed: {integrity}")
    print("Dataset integrity verified: 120 unique cells (15 tasks x 4 variants x 2 seeds).")
    
    print(f"\nStarting containerized execution across {len(records)} candidate patches...")
    print(f"Container configuration: {DOCKER_IMAGE}, network=none, user=1000:1000, cap-drop=ALL, mem=512m")
    
    execution_results = []
    t_start = time.perf_counter()
    
    # Run with 4 concurrent workers
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_single_patch_test, r): r for r in records}
        completed_count = 0
        for fut in as_completed(futures):
            res = fut.result()
            execution_results.append(res)
            completed_count += 1
            if completed_count % 15 == 0 or completed_count == len(records):
                print(f"  Progress: {completed_count}/{len(records)} runs completed ({time.perf_counter() - t_start:.1f}s)")
                
    # Sort results deterministically by (task_id, variant, seed)
    variant_order = {"A_raw": 0, "B_compressed": 1, "C_tail35": 2, "D_no_trace": 3}
    execution_results.sort(key=lambda r: (r["task_id"], variant_order.get(r["variant"], 99), r["seed"]))
    
    # Save results to jsonl
    print(f"\nSaving individual execution records to {EXECUTION_RESULTS_FILE}...")
    with open(EXECUTION_RESULTS_FILE, "w", encoding="utf-8") as f:
        for r in execution_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    # Compute statistical analysis
    print("\nComputing task-clustered statistical analysis on Patch Test Pass Rate...")
    patch_stats = compute_task_clustered_paired_stats(
        execution_results,
        metric_key="patch_test_pass",
        variants=("A_raw", "B_compressed", "C_tail35", "D_no_trace"),
        strict_completeness=True
    )
    
    # Compute variant statistics with clustered CIs
    variant_stats = {}
    for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
        variant_stats[var] = compute_variant_ci(execution_results, var)
        
    # Failure categorization summary
    failures_by_variant = {}
    for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
        var_records = [r for r in execution_results if r["variant"] == var]
        fails = [r for r in var_records if not r["patch_test_pass"]]
        cat_counts = {}
        for f in fails:
            cat = f["failure_category"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        failures_by_variant[var] = {
            "total_calls": len(var_records),
            "passed": len(var_records) - len(fails),
            "failed": len(fails),
            "failure_categories": cat_counts
        }
        
    # Task level pass rates
    task_breakdown = {}
    task_ids = sorted(list(set(r["task_id"] for r in execution_results)))
    for tid in task_ids:
        task_breakdown[tid] = {}
        for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
            var_task = [r for r in execution_results if r["task_id"] == tid and r["variant"] == var]
            passes = sum(1 for r in var_task if r["patch_test_pass"])
            task_breakdown[tid][var] = f"{passes}/{len(var_task)}"
            
    analysis_payload = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "container_isolation": {
            "docker_image": DOCKER_IMAGE,
            "network": "none",
            "user": "1000:1000",
            "cap_drop": "ALL",
            "memory_limit": "512m",
            "cpu_limit": "1.0",
            "pids_limit": 64,
            "host_access": "read-only temporary volume mount with sanitized tmpfs /tmp"
        },
        "integrity_report": integrity,
        "variant_statistics": variant_stats,
        "paired_differences": patch_stats.get("paired_comparisons", {}),
        "failure_taxonomy": failures_by_variant,
        "task_breakdown": task_breakdown
    }
    
    with open(EXECUTION_ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump(analysis_payload, f, indent=2, ensure_ascii=False)
    print(f"Statistical analysis saved to {EXECUTION_ANALYSIS_FILE}.")
    
    # Generate Markdown Report (STRICT OWNER RULE: NO BLOCKQUOTES '>')
    print(f"Generating markdown report at {EXECUTION_REPORT_FILE}...")
    p_diffs = patch_stats.get("paired_comparisons", {})
    
    report_lines = [
        "# Containerized Patch Test Execution Report: Gemma 4 Real Run",
        "",
        "## Executive Summary",
        "",
        "This benchmark provides the actual execution validation for all 120 code patches generated by the real `google/gemma-4-31B-it-qat-w4a16-ct` model during the RunPod inference run.",
        "Candidate patches were executed in an isolated, unprivileged Docker container (`gemma4-eval-sandbox:latest`) with complete network isolation (`--network none`), zero Linux capabilities (`--cap-drop ALL`), strict memory limits (512MB), and read-only host mounts.",
        "",
        "## Key Findings: Patch Test Pass Rate",
        "",
        "| Variant | Description | Total Calls | Passed Tests | Pass Rate (%) | Std Error | 95% Bootstrap CI |",
        "|---|---|---|---|---|---|---|"
    ]
    
    desc_map = {
        "A_raw": "Native uncompressed traceback",
        "B_compressed": "AST-guided compressed traceback (Ours)",
        "C_tail35": "Tail 35-line truncation baseline",
        "D_no_trace": "Zero traceback (Exception text only)"
    }
    
    for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
        st = variant_stats[var]
        ci_str = f"[{st['ci_95'][0]*100:.1f}%, {st['ci_95'][1]*100:.1f}%]"
        report_lines.append(
            f"| {var} | {desc_map[var]} | {st['sample_size']} | {st['passes']} | {st['mean']*100:.1f}% | {st['se']*100:.2f}% | {ci_str} |"
        )
        
    report_lines.extend([
        "",
        "## Paired Differences and Hypothesis Testing",
        "",
        "Paired differences are computed with task ID as the resampling cluster unit (seeds 42 and 100 averaged within each task):",
        "",
        "| Comparison | Delta (mean) | 95% Bootstrap CI | Permutation p-value | Interpretation |",
        "|---|---|---|---|---|"
    ])
    
    for comp in ["delta_B_minus_A", "delta_B_minus_C", "delta_B_minus_D"]:
        if comp in p_diffs:
            diff = p_diffs[comp]
            ci_str = f"[{diff['ci_95_lower']*100:.1f}%, {diff['ci_95_upper']*100:.1f}%]"
            is_sig = diff["p_value_permutation"] < 0.05
            sig_str = "Statistically Significant" if is_sig else "Not Statistically Significant (p >= 0.05; Note: does not prove equivalence)"
            report_lines.append(
                f"| {comp} ({diff['v1']} vs {diff['v2']}) | {diff['mean_delta']*100:+.2f}% | {ci_str} | {diff['p_value_permutation']:.4f} | {sig_str} |"
            )
        
    report_lines.extend([
        "",
        "## Task-by-Task Execution Matrix",
        "",
        "Pass/Total calls per task (across 2 random seeds):",
        "",
        "| Task ID | A_raw | B_compressed | C_tail35 | D_no_trace |",
        "|---|---|---|---|---|"
    ])
    
    for tid in task_ids:
        row = f"| `{tid}` | {task_breakdown[tid]['A_raw']} | {task_breakdown[tid]['B_compressed']} | {task_breakdown[tid]['C_tail35']} | {task_breakdown[tid]['D_no_trace']} |"
        report_lines.append(row)
        
    report_lines.extend([
        "",
        "## Failure Taxonomy and Root Causes",
        "",
        "Breakdown of failed executions by category:",
        "",
        "| Variant | Total Failed | Assertion Error | Attribute Error | Type Error | Value Error | Other |",
        "|---|---|---|---|---|---|---|"
    ])
    
    for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
        f_info = failures_by_variant[var]
        cats = f_info["failure_categories"]
        report_lines.append(
            f"| {var} | {f_info['failed']} | {cats.get('ASSERTION_ERROR', 0)} | {cats.get('ATTRIBUTE_ERROR', 0)} | {cats.get('TYPE_ERROR', 0)} | {cats.get('VALUE_ERROR', 0)} | {sum(v for k,v in cats.items() if k not in ['ASSERTION_ERROR', 'ATTRIBUTE_ERROR', 'TYPE_ERROR', 'VALUE_ERROR'])} |"
        )
        
    report_lines.extend([
        "",
        "## Security Boundary Audit",
        "",
        "All test runs strictly adhered to the unprivileged container security boundary:",
        "- Isolation level: Full Linux namespace isolation via Docker container.",
        "- Network access: Strictly blocked (`--network none`).",
        "- Linux capabilities: Completely dropped (`--cap-drop ALL`).",
        "- Resource limits: 512MB RAM (`--memory 512m`), 1.0 CPU core (`--cpus 1.0`), 64 processes (`--pids-limit 64`).",
        "- Filesystem: Host filesystem mounted strictly read-only (`:ro`). All temporary outputs confined to in-memory `tmpfs`.",
        "- Secrets prevention: Zero environment variables, tokens, or cloud keys mounted or exported.",
        ""
    ])
    
    EXECUTION_REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Report successfully generated at {EXECUTION_REPORT_FILE}.")

if __name__ == "__main__":
    main()
