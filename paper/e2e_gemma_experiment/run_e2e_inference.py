#!/usr/bin/env python3
"""
Robust, Resilient E2E Inference Runner for Gemma 4 Evaluation:
- Safe collect_only mode by DEFAULT: Calls model, collects response and diagnostics, NO candidate execution.
- Strict completeness validation (15 tasks x 4 variants x 2 seeds = 120 unique records).
- Two-tier diagnostic evaluation: Tier 1 Objective Rubric + Tier 2 Lexical Proxy.
- Per-call incremental checkpointing with JSONL recovery and deduplication.
- Strict endpoint health verification: aborts immediately if model endpoint is unreachable.
- Explicit finish_reason and truncation accounting.
- Latin-Square balanced variant ordering per task.
- Task-clustered paired statistical bootstrap analysis (no silent zero substitution).
"""
import os
import sys
import json
import time
import argparse
import datetime
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "frozen_prompts"
TASKS_DIR = BASE_DIR / "tasks"
DEFAULT_CHECKPOINT_FILE = BASE_DIR / "experiment_checkpoint.jsonl"
DEFAULT_PAIRED_ANALYSIS_FILE = BASE_DIR / "paired_statistical_analysis.json"

sys.path.insert(0, str(BASE_DIR))
from evaluator import evaluate_response
from statistics import compute_task_clustered_paired_stats, validate_dataset_integrity

VARIANTS = ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]

def check_endpoint_health(endpoint: str, model_name: str) -> dict:
    """Verify endpoint is responsive and returns model info. Aborts if unreachable."""
    url = f"{endpoint.rstrip('/')}/v1/models"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            available_models = [m.get("id") for m in data.get("data", [])]
            print(f"Endpoint health check PASSED. Available models: {available_models}")
            if model_name not in available_models and not any(model_name in m for m in available_models):
                print(f"WARNING: Requested model '{model_name}' not in reported list {available_models}")
            return {"status": "ok", "models": available_models}
    except Exception as e:
        print(f"FATAL: Endpoint health check query to {url} failed: {e}")
        raise ConnectionError(f"Cannot reach inference endpoint at {url}: {e}")

def call_vllm_api(
    endpoint: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    seed: int,
    max_tokens: int = 1536,
    temp: float = 0.2,
    max_retries: int = 6
) -> tuple[str, str, float, int]:
    """Call an OpenAI-compatible vLLM endpoint with robust retry logic and finish_reason check."""
    url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
        "seed": seed
    }
    data = json.dumps(payload).encode("utf-8")
    retry_delays = [3, 8, 15, 25, 40, 60]
    
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
            )
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - t0
            
            choice = res_data["choices"][0]
            resp_text = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "unknown")
            usage = res_data.get("usage", {}).get("total_tokens", 0)
            return resp_text, finish_reason, latency, usage
        except Exception as e:
            last_err = e
            wait_time = retry_delays[min(attempt, len(retry_delays) - 1)]
            print(f"  [API Retry {attempt+1}/{max_retries}] error: {e}, waiting {wait_time}s...")
            time.sleep(wait_time)
            
    raise RuntimeError(f"API call failed after {max_retries} attempts: {last_err}")

def load_completed_checkpoints(checkpoint_file: Path) -> dict:
    """Load existing checkpoints from JSONL file."""
    completed = {}
    if checkpoint_file.exists():
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        key = (record["task_id"], record["variant"], record["seed"])
                        completed[key] = record
                    except Exception:
                        pass
    return completed

def append_checkpoint(record: dict, checkpoint_file: Path):
    """Atomically append a single execution record to checkpoint JSONL."""
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def run_experiment(
    endpoint: str,
    model_name: str,
    seeds: list[int],
    dry_run: bool = False,
    collect_only: bool = True,
    checkpoint_file: Path = DEFAULT_CHECKPOINT_FILE,
    analysis_file: Path = DEFAULT_PAIRED_ANALYSIS_FILE
):
    manifest_p = BASE_DIR / "task_manifest.json"
    tasks = json.loads(manifest_p.read_text(encoding="utf-8"))
    
    completed_checkpoints = load_completed_checkpoints(checkpoint_file)
    print(f"Loaded {len(completed_checkpoints)} existing records from {checkpoint_file}")
    
    if not dry_run:
        check_endpoint_health(endpoint, model_name)
        
    total_planned = len(tasks) * len(VARIANTS) * len(seeds)
    print(f"\n=======================================================")
    print(f"Gemma 4 Evaluation Experiment Configuration:")
    print(f"  Model: {model_name}")
    print(f"  Execution Mode: {'COLLECT_ONLY (Candidate execution DISABLED)' if collect_only else 'DANGEROUS: SANDBOX EXECUTION ENABLED'}")
    print(f"  Tasks: {len(tasks)} synthetic reproduction tasks")
    print(f"  Variants: {VARIANTS} (Latin-Square balanced)")
    print(f"  Seeds: {seeds}")
    print(f"  Planned Inference Calls: {total_planned}")
    print(f"=======================================================\n")
    
    records_in_memory = list(completed_checkpoints.values())
    call_idx = len(completed_checkpoints)
    
    for seed in seeds:
        print(f"\n=== SEED {seed} ===")
        for task_idx, t in enumerate(tasks):
            tid = t["id"]
            
            # Latin-Square rotation of variant ordering per task
            rotated_variants = VARIANTS[task_idx % len(VARIANTS):] + VARIANTS[:task_idx % len(VARIANTS)]
            
            for var in rotated_variants:
                ckey = (tid, var, seed)
                if ckey in completed_checkpoints:
                    print(f"  [SKIPPING] {tid} | {var} | Seed {seed} (Already in checkpoint)")
                    continue
                    
                call_idx += 1
                prompt_file = PROMPTS_DIR / f"{tid}__{var}.json"
                precord = json.loads(prompt_file.read_text(encoding="utf-8"))
                
                print(f"[{call_idx}/{total_planned}] Task: {tid} | Var: {var} | Seed: {seed} ...", end=" ", flush=True)
                
                t_stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if dry_run:
                    # Deterministic mock dry run for testing execution pipeline
                    time.sleep(0.01)
                    # Produce answer satisfying objective rubric for task_01, task_02 etc.
                    resp_text = (
                        f"DEFECT_LOCATION: {t['target_symbol']}\n"
                        f"ROOT_CAUSE: {t['root_cause']}\n"
                        f"PROPOSED_CODE:\n```python\n# dry run mock\npass\n```"
                    )
                    finish_reason = "stop"
                    latency = 0.01
                    tokens = 120
                else:
                    resp_text, finish_reason, latency, tokens = call_vllm_api(
                        endpoint=endpoint,
                        model_name=model_name,
                        system_prompt=precord["system_prompt"],
                        user_prompt=precord["user_prompt"],
                        seed=seed
                    )
                    
                # Two-tier evaluation (execute_candidate=False in collect_only mode)
                eval_res = evaluate_response(
                    task_id=tid,
                    response_text=resp_text,
                    meta=t,
                    execute_candidate=(not collect_only)
                )
                is_truncated = (finish_reason == "length")
                
                record = {
                    "task_id": tid,
                    "variant": var,
                    "seed": seed,
                    "model_name": model_name,
                    "finish_reason": finish_reason,
                    "is_truncated": is_truncated,
                    "latency_sec": latency,
                    "tokens_used": tokens,
                    "prompt_chars": precord["prompt_char_len"],
                    "trace_chars": precord["trace_char_len"],
                    "timestamp": t_stamp,
                    "model_response": resp_text,
                    **eval_res
                }
                
                # Checkpoint immediately to disk
                append_checkpoint(record, checkpoint_file)
                completed_checkpoints[ckey] = record
                records_in_memory.append(record)
                
                print(f"ObjDiag: {'PASS' if eval_res['objective_diagnostic_pass'] else 'FAIL'} | "
                      f"LexProxy: {'PASS' if eval_res['heuristic_lexical_root_cause_pass'] else 'FAIL'} | "
                      f"Syntax: {'PASS' if eval_res['preflight_syntax_pass'] else 'FAIL'} "
                      f"({latency:.2f}s, finish: {finish_reason})")

    # Strict completeness check & task-clustered paired statistical bootstrap analysis
    run_paired_analysis(records_in_memory, analysis_file)

def run_paired_analysis(results: list[dict], analysis_file: Path = DEFAULT_PAIRED_ANALYSIS_FILE):
    """Execute strict integrity check and task-clustered paired statistical bootstrap."""
    metrics = [
        "objective_diagnostic_pass",
        "objective_localization_pass",
        "objective_root_cause_pass",
        "heuristic_lexical_localization_pass",
        "heuristic_lexical_root_cause_pass",
        "preflight_syntax_pass"
    ]
    
    # Check integrity first
    integrity = validate_dataset_integrity(results)
    
    full_analysis = {
        "analysis_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "integrity_report": integrity,
        "metrics_evaluated": {}
    }
    
    print("\n" + "="*70)
    print("DATASET INTEGRITY & COMPLETENESS REPORT")
    print("="*70)
    print(f"  Total records: {integrity['total_records']} (Expected: {integrity['expected_total_records']})")
    print(f"  Unique cells: {integrity['unique_cells_count']}")
    print(f"  Missing cells: {integrity['missing_count']}")
    print(f"  Duplicates: {integrity['duplicate_count']}")
    print(f"  Truncated responses (finish_reason=length): {integrity['truncated_count']}")
    print(f"  Integrity status: {'VALID & COMPLETE' if integrity['is_complete'] else 'VIOLATION / INCOMPLETE'}")
    
    if not integrity["is_complete"]:
        print(f"\nFATAL: Dataset fails strict completeness criteria!")
        if integrity["missing_keys"]:
            print(f"  Missing: {integrity['missing_keys'][:5]} (total {integrity['missing_count']})")
        if integrity["duplicates"]:
            print(f"  Duplicates: {integrity['duplicates'][:5]}")
        print("Silent zero-substitution prohibited. Paired statistical analysis cannot proceed.")
        analysis_file.parent.mkdir(parents=True, exist_ok=True)
        analysis_file.write_text(json.dumps(full_analysis, indent=2), encoding="utf-8")
        return
        
    print("\n" + "="*70)
    print("TASK-CLUSTERED PAIRED STATISTICAL BOOTSTRAP ANALYSIS (N=10,000 resamples)")
    print("Sampling unit: Task ID (Seeds averaged within task)")
    print("="*70)
    
    for m in metrics:
        stats = compute_task_clustered_paired_stats(results, metric_key=m, n_bootstrap=10000, strict_completeness=True)
        full_analysis["metrics_evaluated"][m] = stats
        
        print(f"\nMetric: {m.upper()}")
        if stats.get("status") == "OK":
            for comp_name, comp in stats.get("paired_comparisons", {}).items():
                print(f"  {comp_name:20s}: Δ = {comp['mean_delta']:+.4f} (95% CI: [{comp['ci_95_lower']:+.4f}, {comp['ci_95_upper']:+.4f}], p = {comp['p_value_permutation']:.4f})")
        else:
            print(f"  Status: {stats.get('status')} - {stats.get('error', stats.get('message'))}")
            
    analysis_file.parent.mkdir(parents=True, exist_ok=True)
    analysis_file.write_text(json.dumps(full_analysis, indent=2), encoding="utf-8")
    print(f"\nFull paired analysis saved to {analysis_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemma 4 E2E Inference Runner")
    parser.add_argument("--endpoint", default="http://localhost:8000", help="vLLM OpenAI-compatible endpoint")
    parser.add_argument("--model", default="google/gemma-4-31B-it-qat-w4a16-ct", help="Model name")
    parser.add_argument("--seeds", default="42,100", help="Comma-separated random seeds")
    parser.add_argument("--dry-run", action="store_true", help="Run local deterministic dry run without network")
    parser.add_argument("--output-dir", default=None, help="Output directory for checkpoints and analysis")
    parser.add_argument("--checkpoint-file", default=None, help="Explicit checkpoint JSONL path")
    parser.add_argument("--analysis-file", default=None, help="Explicit analysis JSON path")
    parser.add_argument("--execute-candidate-code", action="store_true", default=False,
                        help="DANGEROUS: Opt-in to execute candidate code in sandbox. By default, collect_only mode is enforced.")
    args = parser.parse_args()
    
    seeds = [int(s.strip()) for s in args.seeds.split(",")]
    collect_only = not args.execute_candidate_code
    
    if args.output_dir:
        out_p = Path(args.output_dir).resolve()
        out_p.mkdir(parents=True, exist_ok=True)
        ckpt_p = out_p / "real_experiment_checkpoint.jsonl" if not args.checkpoint_file else Path(args.checkpoint_file).resolve()
        an_p = out_p / "real_paired_statistical_analysis.json" if not args.analysis_file else Path(args.analysis_file).resolve()
    else:
        ckpt_p = Path(args.checkpoint_file).resolve() if args.checkpoint_file else DEFAULT_CHECKPOINT_FILE
        an_p = Path(args.analysis_file).resolve() if args.analysis_file else DEFAULT_PAIRED_ANALYSIS_FILE
    
    run_experiment(
        endpoint=args.endpoint,
        model_name=args.model,
        seeds=seeds,
        dry_run=args.dry_run,
        collect_only=collect_only,
        checkpoint_file=ckpt_p,
        analysis_file=an_p
    )
