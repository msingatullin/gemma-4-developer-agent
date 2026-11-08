#!/usr/bin/env python3
"""
Master Execution Script for Real Gemma 4 B2_assertion_aware Exploratory Benchmark:
1. Provisions GPU pod (RTX A6000 / A40 / L40 / A100) on RunPod.
2. Polls endpoint readiness and runs pre-flight smoke test.
3. Executes 30 real inference calls for B2_assertion_aware (15 tasks x 2 seeds: 42, 100)
   in collect_only mode against google/gemma-4-31B-it-qat-w4a16-ct.
4. Guarantees immediate pod teardown and verifies billing cessation in fail-safe finally block.
5. Runs containerized patch execution in unprivileged Docker sandbox (gemma4-eval-sandbox:latest).
6. Computes Pass Rate, token consumption, and paired differences vs A, B, and C.
"""
import os
import sys
import time
import json
import shutil
import tempfile
import datetime
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
OUTPUT_DIR = BASE_DIR / "real_run_20261108"
PROMPTS_DIR = BASE_DIR / "frozen_prompts"
TASKS_DIR = BASE_DIR / "tasks"

B2_CHECKPOINT_FILE = OUTPUT_DIR / "real_b2_experiment_checkpoint.jsonl"
B2_EXECUTION_RESULTS_FILE = OUTPUT_DIR / "real_b2_patch_execution_results.jsonl"
B2_ANALYSIS_FILE = OUTPUT_DIR / "real_b2_patch_execution_analysis.json"
B2_REPORT_FILE = OUTPUT_DIR / "REAL_B2_EXPLORATORY_REPORT.md"

ENV_FILE = Path("/home/mikhail/.runpod/runpod.env")
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k] = v.strip("\"'")

RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
if not RUNPOD_API_KEY:
    raise ValueError("RUNPOD_API_KEY is not set.")

import runpod
from runpod.api import ctl_commands
runpod.api_key = RUNPOD_API_KEY

sys.path.insert(0, str(BASE_DIR))
from evaluator import evaluate_response, parse_structured_response, check_preflight_syntax

MODEL_NAME = "google/gemma-4-31B-it-qat-w4a16-ct"
IMAGE_NAME = "vllm/vllm-openai:gemma4-unified"
DOCKER_ARGS = (
    f"{MODEL_NAME} "
    f"--served-model-name {MODEL_NAME} "
    f"--host 0.0.0.0 --port 8000 "
    f"--max-model-len 4096 "
    f"--gpu-memory-utilization 0.90 "
    f"--enforce-eager "
    f"--trust-remote-code"
)
CANDIDATE_GPUS = [
    ("NVIDIA RTX A6000", "SECURE"),
    ("NVIDIA A40", "SECURE"),
    ("NVIDIA L40", "SECURE"),
    ("NVIDIA A100 80GB PCIe", "SECURE"),
    ("NVIDIA RTX A6000", "COMMUNITY"),
]

DOCKER_SANDBOX_IMAGE = "gemma4-eval-sandbox:latest"
CONTAINER_TIMEOUT_SEC = 20

def get_pod_logs(pod_id: str) -> str:
    """Attempt to fetch logs via RunPod REST v2."""
    try:
        data = ctl_commands.run_rest_request("GET", f"/v2/pods/{pod_id}/logs")
        if isinstance(data, dict):
            return data.get("logs") or data.get("output") or ""
        return str(data or "")
    except Exception:
        return ""

def poll_endpoint_ready(endpoint: str, pod_id: str, timeout_sec: int = 900) -> bool:
    """Poll endpoint /v1/models until HTTP 200 is returned."""
    url = f"{endpoint.rstrip('/')}/v1/models"
    t0 = time.time()
    last_print = 0
    print(f"[READY POLL] Checking {url} for readiness (timeout {timeout_sec}s)...", flush=True)
    
    while time.time() - t0 < timeout_sec:
        elapsed = int(time.time() - t0)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RunPodPoll/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"\n[READY POLL] SUCCESS after {elapsed}s! Models returned: {data}", flush=True)
                    return True
        except Exception as e:
            if elapsed - last_print >= 15:
                pod_status = "UNKNOWN"
                try:
                    p = ctl_commands.get_pod(pod_id)
                    pod_status = p.get("status") if p else "NOT FOUND"
                except Exception:
                    pass
                print(f"[READY POLL] {elapsed}s elapsed | Pod status: {pod_status} | Error: {e}", flush=True)
                last_print = elapsed
        time.sleep(5)
    return False

def smoke_test(endpoint: str) -> bool:
    """Run single 1-prompt pre-flight check."""
    print("\n" + "="*60)
    print("RUNNING PRE-FLIGHT SMOKE TEST")
    print("="*60)
    url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Reply with exactly: READY"}
        ],
        "max_tokens": 16,
        "temperature": 0.0
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
        }
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    lat = time.perf_counter() - t0
    choice = res["choices"][0]
    content = choice["message"]["content"].strip()
    finish = choice.get("finish_reason")
    print(f"Smoke test output: '{content}' (finish: {finish}, latency: {lat:.2f}s)")
    if finish != "stop" or not content:
        raise RuntimeError(f"Smoke test failed: content='{content}', finish='{finish}'")
    print("PRE-FLIGHT SMOKE TEST PASSED SUCCESSFULLY!\n")
    return True

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
    """Call an OpenAI-compatible vLLM endpoint with robust retry logic."""
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
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
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

def run_single_docker_test(record: dict) -> dict:
    """Execute candidate patch in isolated, unprivileged docker container."""
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
        
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        shutil.copy(test_task_file, tmp_p / "test_task.py")
        (tmp_p / "source.py").write_text(candidate_code, encoding="utf-8")
        
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
            DOCKER_SANDBOX_IMAGE,
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

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_p = BASE_DIR / "task_manifest.json"
    tasks = json.loads(manifest_p.read_text(encoding="utf-8"))
    
    seeds = [42, 100]
    total_calls = len(tasks) * len(seeds) # 15 * 2 = 30 calls
    
    pod_id = None
    start_time = time.time()
    gpu_used = "UNKNOWN"
    
    try:
        # Step 1: Provision Pod (or reuse existing active pod)
        print("[STEP 1] Checking for active RunPod GPU Pod or provisioning new...", flush=True)
        pod = None
        existing_pods = ctl_commands.get_pods()
        for p in existing_pods:
            if p.get("status") == "RUNNING" and ("gemma4" in p.get("name", "") or p.get("id") == "ifwwu0t3odva9z"):
                pod = p
                pod_id = p["id"]
                gpu_used = f"{p.get('gpu', {}).get('id')} ({p.get('cloud')})"
                print(f"  -> Reusing existing running pod {pod_id} on {gpu_used}!", flush=True)
                break

        if not pod:
            for gpu_id, cloud in CANDIDATE_GPUS:
                print(f"  Attempting {gpu_id} on {cloud} cloud...", flush=True)
                try:
                    pod = ctl_commands.create_pod(
                        name="gemma4-b2-eval",
                        image_name=IMAGE_NAME,
                        gpu_type_id=gpu_id,
                        cloud_type=cloud,
                        container_disk_in_gb=70,
                        ports="8000/http",
                        docker_args=DOCKER_ARGS,
                        start_ssh=False
                    )
                    if pod and pod.get("id"):
                        gpu_used = f"{gpu_id} ({cloud})"
                        print(f"  -> SUCCESS! Pod created with ID: {pod['id']} on {gpu_used}", flush=True)
                        break
                except Exception as e:
                    print(f"  -> FAILED: {e}", flush=True)
                    
        if not pod or not pod.get("id"):
            raise RuntimeError("Failed to provision any candidate GPU pod on RunPod.")
            
        pod_id = pod["id"]
        proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
        print(f"Pod ID: {pod_id}", flush=True)
        print(f"Proxy Endpoint URL: {proxy_url}", flush=True)
        
        # Step 2: Poll Readiness
        print("\n[STEP 2] Monitoring pod startup and weight initialization...", flush=True)
        is_ready = poll_endpoint_ready(proxy_url, pod_id, timeout_sec=900)
        if not is_ready:
            raise TimeoutError("Pod did not become ready within timeout period.")
            
        # Step 3: Smoke Test
        print("\n[STEP 3] Running 1-prompt pre-flight smoke test...", flush=True)
        smoke_test(proxy_url)
        
        # Step 4: Execute 30 B2 calls
        print(f"\n[STEP 4] Executing 30 B2_assertion_aware calls (15 tasks x 2 seeds) in collect_only mode...", flush=True)
        records = []
        call_num = 0
        
        # Open checkpoint file for appending
        checkpoint_fh = open(B2_CHECKPOINT_FILE, "w", encoding="utf-8")
        
        for seed in seeds:
            print(f"\n--- SEED {seed} ---")
            for t in tasks:
                tid = t["id"]
                call_num += 1
                prompt_file = PROMPTS_DIR / f"{tid}__B2_assertion_aware.json"
                precord = json.loads(prompt_file.read_text(encoding="utf-8"))
                
                print(f"[{call_num}/{total_calls}] Task: {tid} | Var: B2_assertion_aware | Seed: {seed} ...", end=" ", flush=True)
                
                t_stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                resp_text, finish_reason, lat, tokens = call_vllm_api(
                    endpoint=proxy_url,
                    model_name=MODEL_NAME,
                    system_prompt=precord["system_prompt"],
                    user_prompt=precord["user_prompt"],
                    seed=seed,
                    max_tokens=1536,
                    temp=0.2
                )
                
                meta_p = TASKS_DIR / tid / "meta.json"
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                eval_res = evaluate_response(tid, resp_text, meta, execute_candidate=False)
                
                record = {
                    "task_id": tid,
                    "variant": "B2_assertion_aware",
                    "seed": seed,
                    "model_name": MODEL_NAME,
                    "finish_reason": finish_reason,
                    "is_truncated": (finish_reason == "length"),
                    "latency_sec": round(lat, 3),
                    "tokens_used": tokens,
                    "prompt_chars": precord["prompt_char_len"],
                    "trace_chars": precord["trace_char_len"],
                    "timestamp": t_stamp,
                    "model_response": resp_text,
                    **eval_res
                }
                
                records.append(record)
                checkpoint_fh.write(json.dumps(record) + "\n")
                checkpoint_fh.flush()
                
                diag_flag = "PASS" if record["objective_diagnostic_pass"] else "FAIL"
                syntax_flag = "SYNTAX_OK" if record["preflight_syntax_pass"] else "SYNTAX_ERR"
                print(f"DONE in {lat:.2f}s | {tokens} tok | Diag: {diag_flag} | {syntax_flag}", flush=True)
                
        checkpoint_fh.close()
        print(f"\n[STEP 4 COMPLETED] All 30 calls finished and written to {B2_CHECKPOINT_FILE}", flush=True)
        
    finally:
        # Step 5: Fail-Safe Pod Teardown
        if pod_id:
            print("\n" + "="*60)
            print(f"[FAIL-SAFE TEARDOWN] Terminating pod {pod_id} immediately...")
            print("="*60)
            try:
                ctl_commands.terminate_pod(pod_id)
                print("Teardown signal sent.")
            except Exception as e:
                print(f"Teardown command error: {e}")
                
            # Verify billing cessation
            for check in range(12):
                time.sleep(5)
                try:
                    p = ctl_commands.get_pod(pod_id)
                    if not p or p.get("status") in ["TERMINATING", "TERMINATED", "DEAD"]:
                        print(f"Teardown verified: pod is {p.get('status') if p else 'DELETED'}.")
                        break
                except Exception:
                    print("Pod no longer found via API. Teardown confirmed.")
                    break
                    
            duration_min = (time.time() - start_time) / 60
            est_cost = (duration_min / 60) * 0.79 # A6000 is ~$0.79/hr
            print(f"Session finished in {duration_min:.1f} minutes. GPU: {gpu_used}. Estimated spend: ${est_cost:.3f} USD.")
            print("="*60)

    # Step 6: Isolated Container Execution of Candidate Patches
    print("\n" + "="*60)
    print("[STEP 6] Executing 30 Candidate Patches in Docker Sandbox...")
    print("="*60)
    
    with open(B2_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        loaded_records = [json.loads(l) for l in f if l.strip()]
        
    execution_results = []
    with open(B2_EXECUTION_RESULTS_FILE, "w", encoding="utf-8") as out_f:
        for idx, rec in enumerate(loaded_records):
            print(f"[{idx+1}/30] Testing {rec['task_id']} | Seed {rec['seed']} in Docker sandbox...", end=" ", flush=True)
            res = run_single_docker_test(rec)
            execution_results.append(res)
            out_f.write(json.dumps(res) + "\n")
            out_f.flush()
            status_str = "PASS" if res["patch_test_pass"] else f"FAIL ({res['failure_category']})"
            print(f"{status_str} in {res['exec_latency_sec']}s")
            
    # Compute summary metrics
    total_b2 = len(execution_results)
    passed_b2 = sum(1 for r in execution_results if r["patch_test_pass"])
    pass_rate_b2 = (passed_b2 / total_b2) * 100 if total_b2 else 0.0
    
    # Token usage
    total_tokens_b2 = sum(r["tokens_used"] for r in loaded_records)
    mean_tokens_b2 = total_tokens_b2 / total_b2 if total_b2 else 0.0
    
    # Compare with existing results
    # Load A, B, C, D from real_patch_execution_results.jsonl
    real_exec_p = OUTPUT_DIR / "real_patch_execution_results.jsonl"
    existing_results = {}
    if real_exec_p.exists():
        with open(real_exec_p, "r", encoding="utf-8") as f:
            for l in f:
                d = json.loads(l)
                var = d["variant"]
                existing_results.setdefault(var, []).append(d)
                
    # Load existing checkpoint tokens
    real_ckpt_p = OUTPUT_DIR / "real_experiment_checkpoint.jsonl"
    existing_tokens = {}
    if real_ckpt_p.exists():
        with open(real_ckpt_p, "r", encoding="utf-8") as f:
            for l in f:
                d = json.loads(l)
                var = d["variant"]
                existing_tokens.setdefault(var, []).append(d["tokens_used"])
                
    summary_report = {
        "variant": "B2_assertion_aware",
        "description": "AST-guided assertion-aware traceback compressor (Post-hoc exploratory)",
        "total_calls": total_b2,
        "passed_tests": passed_b2,
        "pass_rate_pct": round(pass_rate_b2, 2),
        "total_api_tokens": total_tokens_b2,
        "mean_api_tokens_per_call": round(mean_tokens_b2, 1),
        "tasks_detail": [
            {
                "task_id": r["task_id"],
                "seed": r["seed"],
                "passed": r["patch_test_pass"],
                "failure_category": r["failure_category"],
                "failure_reason": r["failure_reason"]
            }
            for r in execution_results
        ]
    }
    
    B2_ANALYSIS_FILE.write_text(json.dumps(summary_report, indent=2), encoding="utf-8")
    
    print("\n" + "="*70)
    print("FINAL BENCHMARK COMPARISON (A, B, B2, C, D)")
    print("="*70)
    print(f"{'Variant':25s} | {'Calls':5s} | {'Passed':6s} | {'Pass Rate':10s} | {'Total Tokens':12s} | {'Mean Tokens':11s}")
    print("-" * 80)
    
    for vname in ["A_raw", "B_compressed", "B2_assertion_aware", "C_tail35", "D_no_trace"]:
        if vname == "B2_assertion_aware":
            tot = total_b2
            pas = passed_b2
            pr = pass_rate_b2
            ttok = total_tokens_b2
            mtok = mean_tokens_b2
        else:
            v_res = existing_results.get(vname, [])
            tot = len(v_res)
            pas = sum(1 for r in v_res if r["patch_test_pass"])
            pr = (pas / tot) * 100 if tot else 0.0
            v_toks = existing_tokens.get(vname, [])
            ttok = sum(v_toks)
            mtok = ttok / len(v_toks) if v_toks else 0.0
        print(f"{vname:25s} | {tot:5d} | {pas:6d} | {pr:9.1f}% | {ttok:12d} | {mtok:11.1f}")
    print("="*70)

if __name__ == "__main__":
    main()
