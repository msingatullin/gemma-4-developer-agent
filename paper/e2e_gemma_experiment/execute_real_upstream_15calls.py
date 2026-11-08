#!/usr/bin/env python3
"""
Master Execution Script for Phase 2: 15 Live Gemma 4 31B Inferences on Real Repositories
Executes:
- 5 authentic defects (Flask 4045, 4992, 5063; Requests 1963, 2148)
- 3 variants: A_raw, B2_assertion_aware, C_tail35
- Total = exactly 15 calls at temperature=0.0
- Automated RunPod lifecycle with fail-safe teardown and zero-pod verification
- Immediate containerized Docker evaluation (--network none, --cap-drop ALL, 1g RAM)
- Transparent comparative reporting (A vs B2 vs C)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXP_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment"
SAMPLE_DIR = EXP_DIR / "real_repo_sample"
PROMPTS_DIR = SAMPLE_DIR / "frozen_prompts"
INFERENCE_RESULTS_FILE = SAMPLE_DIR / "real_inference_15calls.jsonl"
EVAL_RESULTS_FILE = SAMPLE_DIR / "real_eval_results_15calls.jsonl"
COMPARATIVE_REPORT_FILE = SAMPLE_DIR / "REAL_UPSTREAM_COMPARATIVE_REPORT.md"

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

sys.path.insert(0, str(EXP_DIR))
from evaluate_real_repo_patches import evaluate_patch_on_task

MODEL_NAME = "google/gemma-4-31B-it-qat-w4a16-ct"
IMAGE_NAME = "vllm/vllm-openai:gemma4-unified"
DOCKER_ARGS = (
    f"{MODEL_NAME} "
    f"--served-model-name {MODEL_NAME} "
    f"--host 0.0.0.0 --port 8000 "
    f"--max-model-len 14336 "
    f"--gpu-memory-utilization 0.90 "
    f"--enforce-eager "
    f"--trust-remote-code"
)

CANDIDATE_GPUS = [
    ("NVIDIA RTX A6000", "COMMUNITY"),
    ("NVIDIA A40", "COMMUNITY"),
    ("NVIDIA RTX A6000", "SECURE"),
    ("NVIDIA A40", "SECURE"),
    ("NVIDIA L40", "SECURE"),
]

TASKS = [
    "pallets__flask-4045",
    "pallets__flask-4992",
    "pallets__flask-5063",
    "psf__requests-1963",
    "psf__requests-2148"
]

VARIANTS = ["A_raw", "B2_assertion_aware", "C_tail35"]

def check_runpod_status() -> tuple:
    """Check user balance and active pods."""
    import requests
    url = f"https://api.runpod.io/graphql?api_key={RUNPOD_API_KEY}"
    q = """query { myself { clientBalance currentSpendPerHr pods { id name desiredStatus costPerHr } } }"""
    r = requests.post(url, json={"query": q}, timeout=15).json()
    myself = r["data"]["myself"]
    balance = myself["clientBalance"]
    pods = myself["pods"] or []
    return balance, pods

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
                print(f"[READY POLL] {elapsed}s | Pod: {pod_status} | Status: {e}", flush=True)
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

def call_gemma_chat(endpoint: str, system_prompt: str, user_prompt: str, max_retries: int = 3) -> dict:
    url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.0
    }
    data = json.dumps(payload).encode("utf-8")
    
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Gemma4RealEval/1.0"
                }
            )
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=120) as resp:
                res = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - t0
            
            choice = res["choices"][0]
            usage = res.get("usage", {})
            return {
                "content": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "latency_sec": round(latency, 3),
                "status": "SUCCESS"
            }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            last_err = f"HTTP {e.code}: {e.reason} - {err_body}"
            print(f"  [Attempt {attempt+1}/{max_retries}] API call error: {last_err}", flush=True)
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            last_err = str(e)
            print(f"  [Attempt {attempt+1}/{max_retries}] API call error: {e}", flush=True)
            time.sleep(3 * (attempt + 1))
            
    return {
        "content": "",
        "finish_reason": "ERROR",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_sec": 0.0,
        "status": f"FAILED: {last_err}"
    }

def main():
    print("="*80)
    print("PHASE 2: 15 CALLS ON REAL REPOSITORIES (FLASK & REQUESTS)")
    print("="*80)

    # 1. Check budget and active pods
    balance_start, active_pods = check_runpod_status()
    print(f"Current RunPod Balance: ${balance_start:.4f}")
    print(f"Active Pods Count: {len(active_pods)}")

    if len(active_pods) > 0:
        print("[!] Warning: active pods detected before start:")
        for p in active_pods:
            print(f"    Pod {p['id']}: {p['name']} ({p['costPerHr']}/hr)")

    pod_id = None
    created_new_pod = False
    inference_records = []

    if INFERENCE_RESULTS_FILE.exists():
        INFERENCE_RESULTS_FILE.unlink()
    if EVAL_RESULTS_FILE.exists():
        EVAL_RESULTS_FILE.unlink()

    try:
        # Step 1: Provision GPU
        print("\n[STEP 1] Provisioning RunPod GPU Pod for Gemma 4 31B...")
        for p in active_pods:
            if p.get("desiredStatus") == "RUNNING" and ("gemma4" in p.get("name", "") or p.get("id") == "icjxhvimohrirg"):
                pod_id = p["id"]
                created_new_pod = True
                print(f"  -> Reusing existing running pod {pod_id}!", flush=True)
                break

        if not pod_id:
            for gpu_id, cloud in CANDIDATE_GPUS:
                print(f"  Attempting {gpu_id} on {cloud} cloud...", flush=True)
                try:
                    pod = ctl_commands.create_pod(
                        name="gemma4-real-15calls",
                        image_name=IMAGE_NAME,
                        gpu_type_id=gpu_id,
                        cloud_type=cloud,
                        container_disk_in_gb=70,
                        ports="8000/http",
                        docker_args=DOCKER_ARGS,
                        start_ssh=False
                    )
                    if pod and pod.get("id"):
                        pod_id = pod["id"]
                        created_new_pod = True
                        print(f"  -> SUCCESS! Created Pod ID: {pod_id} on {gpu_id} ({cloud})", flush=True)
                        break
                except Exception as e:
                    print(f"  -> Failed: {e}", flush=True)

        if not pod_id:
            raise RuntimeError("Failed to provision any candidate GPU pod on RunPod.")

        proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
        print(f"Proxy URL: {proxy_url}")

        # Step 2: Poll Readiness
        print("\n[STEP 2] Waiting for vLLM model to load...")
        ready = poll_endpoint_ready(proxy_url, pod_id, timeout_sec=900)
        if not ready:
            raise TimeoutError("vLLM endpoint failed to become ready in time.")

        # Step 3: Smoke Test
        print("\n[STEP 3] Smoke test...")
        smoke_test(proxy_url)

        # Step 4: Execute 15 Inferences
        print("\n[STEP 4] Executing 15 Inferences (5 tasks x 3 variants)...")
        call_idx = 0
        total_calls = len(TASKS) * len(VARIANTS)

        for task_id in TASKS:
            print(f"\n=======================================================")
            print(f"[*] Task: {task_id}")
            for variant in VARIANTS:
                call_idx += 1
                prompt_file = PROMPTS_DIR / f"{task_id}__{variant}.json"
                assert prompt_file.exists(), f"Missing frozen prompt: {prompt_file}"
                pdata = json.loads(prompt_file.read_text(encoding="utf-8"))

                print(f"[{call_idx}/{total_calls}] Calling Gemma 4 31B for {task_id} [{variant}]...", flush=True)
                res = call_gemma_chat(
                    proxy_url,
                    system_prompt=pdata["system_prompt"],
                    user_prompt=pdata["user_prompt"]
                )
                print(f"    Done in {res['latency_sec']}s | Tokens: {res['prompt_tokens']} prompt, {res['completion_tokens']} comp (Total: {res['total_tokens']})")

                rec = {
                    "call_index": call_idx,
                    "task_id": task_id,
                    "variant": variant,
                    "prompt_file": prompt_file.name,
                    "prompt_tokens": res["prompt_tokens"],
                    "completion_tokens": res["completion_tokens"],
                    "total_tokens": res["total_tokens"],
                    "latency_sec": res["latency_sec"],
                    "status": res["status"],
                    "model_response": res["content"]
                }
                inference_records.append(rec)

                # Append to checkpoint
                with open(INFERENCE_RESULTS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")

    finally:
        # STEP 5: Fail-Safe Teardown
        if pod_id and created_new_pod:
            print(f"\n[STEP 5] TEARDOWN: Terminating Pod {pod_id} immediately...", flush=True)
            try:
                ctl_commands.terminate_pod(pod_id)
                time.sleep(10)
                # Verify cessation
                for _ in range(6):
                    bal, current_pods = check_runpod_status()
                    remaining = [p for p in current_pods if p["id"] == pod_id]
                    if not remaining:
                        print(f"[✓] Teardown Verified! Pod {pod_id} is deleted. Active pods: {len(current_pods)}")
                        break
                    time.sleep(5)
            except Exception as e:
                print(f"[!] Teardown error: {e}", flush=True)

        bal_end, remaining_pods = check_runpod_status()
        cost_incurred = balance_start - bal_end
        print(f"\nRunPod Final Balance: ${bal_end:.4f} (Cost: ${cost_incurred:.4f})")
        print(f"Active Pods Remaining: {len(remaining_pods)}")
        assert len(remaining_pods) == 0, f"LEAKED POD DETECTED: {remaining_pods}"

    # STEP 6: Containerized Evaluation of All 15 Model Outputs
    print("\n" + "="*80)
    print("[STEP 6] Running Containerized Evaluation in Docker Sandbox...")
    print("="*80)

    eval_records = []
    for rec in inference_records:
        task_id = rec["task_id"]
        variant = rec["variant"]
        call_idx = rec["call_index"]
        print(f"\n[{call_idx}/15] Evaluating candidate patch for {task_id} [{variant}] in Docker...")

        eval_res = evaluate_patch_on_task(task_id, rec["model_response"], run_id=f"eval_{call_idx}")
        verdict = eval_res.get("verdict")
        print(f"    Verdict: {verdict} (F2P: {eval_res.get('f2p_pass')}, P2P: {eval_res.get('p2p_pass')})")

        eval_entry = {
            "call_index": call_idx,
            "task_id": task_id,
            "variant": variant,
            "prompt_tokens": rec["prompt_tokens"],
            "completion_tokens": rec["completion_tokens"],
            "total_tokens": rec["total_tokens"],
            "latency_sec": rec["latency_sec"],
            "eval_result": eval_res
        }
        eval_records.append(eval_entry)

    with open(EVAL_RESULTS_FILE, "w", encoding="utf-8") as f:
        for r in eval_records:
            f.write(json.dumps(r) + "\n")
    print(f"\n[✓] All 15 evaluations complete! Results written to {EVAL_RESULTS_FILE.name}")

    # STEP 7: Produce Comparative Statistics & Report
    print("\n" + "="*80)
    print("STEP 7: COMPARATIVE ANALYSIS (A_raw vs B2_assertion_aware vs C_tail35)")
    print("="*80)

    variant_stats = {v: {"total": 0, "resolved": 0, "failed_f2p": 0, "regression": 0, "syntax_error": 0, "prompt_tokens": [], "comp_tokens": []} for v in VARIANTS}

    for er in eval_records:
        v = er["variant"]
        verdict = er["eval_result"]["verdict"]
        variant_stats[v]["total"] += 1
        if verdict == "RESOLVED":
            variant_stats[v]["resolved"] += 1
        elif verdict == "FAILED_F2P":
            variant_stats[v]["failed_f2p"] += 1
        elif verdict == "REGRESSION":
            variant_stats[v]["regression"] += 1
        elif verdict == "SYNTAX_ERROR":
            variant_stats[v]["syntax_error"] += 1
        variant_stats[v]["prompt_tokens"].append(er["prompt_tokens"])
        variant_stats[v]["comp_tokens"].append(er["completion_tokens"])

    report_lines = [
        "# Real Upstream Repository Comparative Report: Gemma 4 31B",
        "",
        "## Summary",
        f"- Total Tasks: 5 authentic upstream issues (Flask 4045, 4992, 5063; Requests 1963, 2148)",
        f"- Variants Tested: A_raw, B2_assertion_aware, C_tail35",
        f"- Total Live Inferences: 15 calls on `google/gemma-4-31B-it-qat-w4a16-ct` (temperature=0.0)",
        f"- Evaluation Sandbox: Docker `python:3.12-slim` (`--network none`, `--cap-drop ALL`, `--user 1000:1000`, 1GB RAM)",
        "",
        "## Aggregate Results by Variant",
        "",
        "| Variant | Resolved / Total | Pass Rate (%) | Avg Prompt Tokens | Avg Completion Tokens | Regressions | Syntax Errors |",
        "|---|---|---|---|---|---|---|"
    ]

    for v in VARIANTS:
        s = variant_stats[v]
        tot = s["total"]
        res = s["resolved"]
        rate = (res / tot * 100.0) if tot > 0 else 0.0
        avg_p = sum(s["prompt_tokens"]) / tot if tot > 0 else 0
        avg_c = sum(s["comp_tokens"]) / tot if tot > 0 else 0
        report_lines.append(f"| {v} | {res}/{tot} | {rate:.1f}% | {avg_p:.0f} | {avg_c:.0f} | {s['regression']} | {s['syntax_error']} |")

    report_lines.extend([
        "",
        "## Detailed Task-by-Task Outcome Table",
        "",
        "| Task ID | Variant | Verdict | F2P Pass | P2P Pass | Prompt Tok | Comp Tok | Latency (s) |",
        "|---|---|---|---|---|---|---|---|"
    ])

    for er in eval_records:
        vres = er["eval_result"]
        report_lines.append(f"| {er['task_id']} | {er['variant']} | {vres['verdict']} | {vres.get('f2p_pass')} | {vres.get('p2p_pass')} | {er['prompt_tokens']} | {er['completion_tokens']} | {er['latency_sec']} |")

    report_content = "\n".join(report_lines) + "\n"
    COMPARATIVE_REPORT_FILE.write_text(report_content, encoding="utf-8")
    print("\n" + report_content)
    print(f"[✓] Comparative report written to {COMPARATIVE_REPORT_FILE.name}")

if __name__ == "__main__":
    main()
