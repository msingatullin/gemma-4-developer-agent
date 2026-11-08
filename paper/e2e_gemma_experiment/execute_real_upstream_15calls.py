#!/usr/bin/env python3
"""
Master Execution Script for Phase 2: 15 Live Gemma 4 31B Inferences on Real Repositories
Fulfills all Lead / P2 requirements:
1. Strict 80GB GPU constraint (A100 80GB PCIe, A100-SXM4-80GB, H100 80GB). Automatic exclusion of <=48GB GPUs.
2. Context window --max-model-len 16384 to support authentic tasks up to 12,657 required tokens.
3. Strict HTTP 400 abort without retry (context length exceeded or payload error).
4. Prompt integrity check: SHA256 validation of every frozen prompt before inference.
5. Filter: zero-token responses, empty content, and finish_reason=length are rejected.
6. Checkpoint resilience: Reuses valid completed inferences without re-calling or overwriting.
7. Automated fail-safe pod teardown even on exception, with redundant GraphQL termination and zero-pod verification.
8. 60-minute hard runtime cap.
9. Immediate Docker containerized evaluation (--network none, --cap-drop ALL, 1GB RAM).
10. Transparent comparative reporting (A_raw vs B2_assertion_aware vs C_tail35).
"""

import os
import sys
import time
import json
import hashlib
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
MEASUREMENTS_FILE = SAMPLE_DIR / "exact_prompt_token_measurements.json"

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

# Exact required context is 12,657 tokens -> safe power-of-two window is 16384
MAX_MODEL_LEN = 16384
DOCKER_ARGS = (
    f"{MODEL_NAME} "
    f"--served-model-name {MODEL_NAME} "
    f"--host 0.0.0.0 --port 8000 "
    f"--max-model-len {MAX_MODEL_LEN} "
    f"--gpu-memory-utilization 0.90 "
    f"--enforce-eager "
    f"--trust-remote-code"
)

# STRICT 80GB GPU LIST: Under NO circumstances allow 48GB GPUs (RTX A6000, A40, L40)
CANDIDATE_GPUS = [
    ("NVIDIA A100 80GB PCIe", "COMMUNITY"),
    ("NVIDIA A100-SXM4-80GB", "COMMUNITY"),
    ("NVIDIA A100 80GB PCIe", "SECURE"),
    ("NVIDIA A100-SXM4-80GB", "SECURE"),
    ("NVIDIA H100 80GB HBM3", "COMMUNITY"),
    ("NVIDIA H100 PCIe", "COMMUNITY"),
    ("NVIDIA H100 80GB HBM3", "SECURE"),
    ("NVIDIA H100 PCIe", "SECURE"),
]

TASKS = [
    "pallets__flask-4045",
    "pallets__flask-4992",
    "pallets__flask-5063",
    "psf__requests-1963",
    "psf__requests-2148"
]

VARIANTS = ["A_raw", "B2_assertion_aware", "C_tail35"]

# Hard maximum total run budget (60 minutes)
MAX_RUN_TIME_SEC = 3600

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

def terminate_pod_raw(pod_id: str):
    """Redundant raw GraphQL termination mutation."""
    import requests
    url = f"https://api.runpod.io/graphql?api_key={RUNPOD_API_KEY}"
    mutation = f"""mutation {{ podTerminate(input: {{ podId: "{pod_id}" }}) }}"""
    requests.post(url, json={"query": mutation}, timeout=15)

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

def call_gemma_chat(endpoint: str, system_prompt: str, user_prompt: str, max_retries: int = 2) -> dict:
    """
    Executes a single chat completion against Gemma 4 31B.
    Fails fast on HTTP 400 (Bad Request / Context Exceeded) without retries.
    Rejects empty responses, finish_reason=length, and 0-token answers.
    """
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
            with urllib.request.urlopen(req, timeout=180) as resp:
                res = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - t0
            
            choice = res["choices"][0]
            usage = res.get("usage", {})
            content = choice["message"].get("content", "")
            finish_reason = choice.get("finish_reason")
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            # Strict validation
            if not content or not content.strip():
                raise ValueError("Model returned empty response content.")
            if finish_reason == "length":
                raise ValueError("Generation truncated by max_tokens limit (finish_reason=length).")
            if prompt_tokens <= 0 or completion_tokens <= 0:
                raise ValueError(f"Invalid token counts: prompt={prompt_tokens}, comp={completion_tokens}.")

            return {
                "content": content,
                "finish_reason": finish_reason,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_sec": round(latency, 3),
                "status": "SUCCESS"
            }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            last_err = f"HTTP {e.code}: {e.reason} - {err_body}"
            print(f"  [API ERROR] {last_err}", flush=True)
            # HARD ABORT on 400: Never retry context length or malformed payload rejections
            if e.code == 400:
                raise RuntimeError(
                    f"CRITICAL ABORT: Server returned HTTP 400 Bad Request: {last_err}. "
                    f"Possible context length violation. Halting pipeline immediately."
                )
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            last_err = str(e)
            print(f"  [Attempt {attempt+1}/{max_retries}] API call error: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
            
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
    print("PHASE 2: 15 CALLS ON REAL REPOSITORIES (FLASK & REQUESTS) ON 80GB GPU")
    print("="*80)

    # 1. Check budget and active pods
    balance_start, active_pods = check_runpod_status()
    print(f"Current RunPod Balance: ${balance_start:.4f}")
    print(f"Active Pods Count: {len(active_pods)}")

    # 2. Load prompt SHA256 integrity map
    assert MEASUREMENTS_FILE.exists(), f"Missing measurements file: {MEASUREMENTS_FILE}"
    measurements_data = json.loads(MEASUREMENTS_FILE.read_text(encoding="utf-8"))
    sha_map = {
        (m["instance_id"], m["variant"]): m["prompt_file_sha256"]
        for m in measurements_data["measurements"]
    }

    # 3. Load existing checkpoints to prevent loss and avoid redundant calls
    completed_calls = {}
    if INFERENCE_RESULTS_FILE.exists():
        print(f"[*] Inspecting existing checkpoint file: {INFERENCE_RESULTS_FILE.name}")
        with open(INFERENCE_RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if (r.get("status") == "SUCCESS" and 
                        r.get("model_response", "").strip() and 
                        r.get("prompt_tokens", 0) > 0 and 
                        r.get("completion_tokens", 0) > 0):
                        completed_calls[(r["task_id"], r["variant"])] = r
                except Exception:
                    pass
        print(f"[*] Found {len(completed_calls)} previously completed valid inference records.")

    total_needed = len(TASKS) * len(VARIANTS)
    needed_pairs = [(t, v) for t in TASKS for v in VARIANTS if (t, v) not in completed_calls]
    print(f"[*] Total required inferences: {total_needed} (Pending: {len(needed_pairs)}, Completed: {len(completed_calls)})")

    pod_id = None
    created_new_pod = False
    start_time = time.time()

    try:
        if needed_pairs:
            # Need to run GPU inference
            print("\n[STEP 1] Provisioning RunPod 80GB GPU Pod for Gemma 4 31B...")
            for p in active_pods:
                if p.get("desiredStatus") == "RUNNING" and ("gemma4" in p.get("name", "") or "80gb" in p.get("name", "").lower()):
                    pod_id = p["id"]
                    print(f"  -> Reusing existing running pod {pod_id}!", flush=True)
                    break

            if not pod_id:
                for gpu_id, cloud in CANDIDATE_GPUS:
                    print(f"  Attempting 80GB GPU: {gpu_id} on {cloud} cloud...", flush=True)
                    try:
                        pod = ctl_commands.create_pod(
                            name="gemma4-real-15calls-80gb",
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
                            print(f"  -> SUCCESS! Created 80GB Pod ID: {pod_id} on {gpu_id} ({cloud})", flush=True)
                            break
                    except Exception as e:
                        print(f"  -> Failed on {gpu_id} ({cloud}): {e}", flush=True)

            if not pod_id:
                raise RuntimeError("Failed to provision any candidate 80GB GPU pod on RunPod.")

            proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
            print(f"Proxy URL: {proxy_url}")

            # Step 2: Poll Readiness
            print("\n[STEP 2] Waiting for vLLM model to load with --max-model-len 16384...")
            ready = poll_endpoint_ready(proxy_url, pod_id, timeout_sec=900)
            if not ready:
                raise TimeoutError("vLLM endpoint failed to become ready in time.")

            # Step 3: Smoke Test
            print("\n[STEP 3] Smoke test...")
            smoke_test(proxy_url)

            # Step 4: Execute Pending Inferences
            print(f"\n[STEP 4] Executing {len(needed_pairs)} Pending Inferences...")
            call_idx = len(completed_calls)

            for task_id, variant in needed_pairs:
                call_idx += 1
                # Enforce hard runtime limit
                if time.time() - start_time > MAX_RUN_TIME_SEC:
                    raise TimeoutError(f"HARD TIMEOUT REACHED ({MAX_RUN_TIME_SEC}s). Aborting to prevent excess spend.")

                prompt_file = PROMPTS_DIR / f"{task_id}__{variant}.json"
                assert prompt_file.exists(), f"Missing frozen prompt: {prompt_file}"

                # Strict SHA256 integrity check
                actual_sha = hashlib.sha256(prompt_file.read_bytes()).hexdigest()
                expected_sha = sha_map.get((task_id, variant))
                assert actual_sha == expected_sha, f"INTEGRITY ERROR: SHA mismatch for {prompt_file.name}: {actual_sha} != {expected_sha}"

                pdata = json.loads(prompt_file.read_text(encoding="utf-8"))

                print(f"\n[{call_idx}/{total_needed}] Calling Gemma 4 31B: {task_id} [{variant}] (Prompt SHA: {actual_sha[:12]})...", flush=True)
                res = call_gemma_chat(
                    proxy_url,
                    system_prompt=pdata["system_prompt"],
                    user_prompt=pdata["user_prompt"]
                )
                print(f"    Done in {res['latency_sec']}s | Tokens: {res['prompt_tokens']} prompt, {res['completion_tokens']} comp (Total: {res['total_tokens']})")

                if res["status"] != "SUCCESS":
                    raise RuntimeError(f"Inference failed for {task_id} [{variant}]: {res['status']}")

                rec = {
                    "call_index": call_idx,
                    "task_id": task_id,
                    "variant": variant,
                    "prompt_file": prompt_file.name,
                    "prompt_sha256": actual_sha,
                    "prompt_tokens": res["prompt_tokens"],
                    "completion_tokens": res["completion_tokens"],
                    "total_tokens": res["total_tokens"],
                    "latency_sec": res["latency_sec"],
                    "status": res["status"],
                    "model_response": res["content"]
                }
                completed_calls[(task_id, variant)] = rec

                # Append to checkpoint
                with open(INFERENCE_RESULTS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
        else:
            print("\n[*] All 15 inferences already present in valid checkpoint. Skipping GPU provisioning!")

    finally:
        # STEP 5: Fail-Safe Teardown
        if pod_id and created_new_pod:
            print(f"\n[STEP 5] TEARDOWN: Terminating 80GB Pod {pod_id} immediately...", flush=True)
            try:
                ctl_commands.terminate_pod(pod_id)
            except Exception as e:
                print(f"[!] Primary terminate error: {e}", flush=True)

            # Polling to guarantee deletion
            print(f"[*] Verifying pod {pod_id} deletion...", flush=True)
            for poll_idx in range(12):
                time.sleep(5)
                try:
                    bal, current_pods = check_runpod_status()
                    remaining = [p for p in current_pods if p["id"] == pod_id]
                    if not remaining:
                        print(f"[✓] Teardown Verified! Pod {pod_id} deleted. Active pods: {len(current_pods)}", flush=True)
                        break
                    else:
                        print(f"    Waiting for termination... (attempt {poll_idx+1}/12)", flush=True)
                except Exception as e:
                    print(f"    Poll status error: {e}", flush=True)

            bal_end, remaining_pods = check_runpod_status()
            if any(p["id"] == pod_id for p in remaining_pods):
                print(f"[CRITICAL] Triggering raw GraphQL fallback termination for {pod_id}...", flush=True)
                terminate_pod_raw(pod_id)

            cost_incurred = balance_start - bal_end
            print(f"\nRunPod Final Balance: ${bal_end:.4f} (Cost incurred: ${cost_incurred:.4f})")
            print(f"Active Pods Remaining: {len(remaining_pods)}")
            assert len(remaining_pods) == 0, f"LEAKED POD DETECTED: {remaining_pods}"

    # Verify all 15 calls are present
    assert len(completed_calls) == total_needed, f"Expected {total_needed} calls, got {len(completed_calls)}"
    all_inferences = [completed_calls[(t, v)] for t in TASKS for v in VARIANTS]

    # STEP 6: Containerized Evaluation of All 15 Model Outputs
    print("\n" + "="*80)
    print("[STEP 6] Running Containerized Evaluation in Docker Sandbox...")
    print("="*80)

    eval_records = []
    eval_idx = 0
    for rec in all_inferences:
        eval_idx += 1
        task_id = rec["task_id"]
        variant = rec["variant"]
        print(f"\n[{eval_idx}/15] Evaluating candidate patch for {task_id} [{variant}] in Docker...")

        eval_res = evaluate_patch_on_task(task_id, rec["model_response"], run_id=f"eval_{eval_idx}")
        verdict = eval_res.get("verdict")
        print(f"    Verdict: {verdict} (F2P: {eval_res.get('f2p_pass')}, P2P: {eval_res.get('p2p_pass')})")

        eval_entry = {
            "call_index": eval_idx,
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

    variant_stats = {v: {"total": 0, "resolved": 0, "failed_f2p": 0, "regression": 0, "syntax_error": 0, "patch_apply_error": 0, "prompt_tokens": [], "comp_tokens": []} for v in VARIANTS}

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
        elif verdict == "PATCH_APPLY_ERROR":
            variant_stats[v]["patch_apply_error"] += 1
        variant_stats[v]["prompt_tokens"].append(er["prompt_tokens"])
        variant_stats[v]["comp_tokens"].append(er["completion_tokens"])

    report_lines = [
        "# Real Upstream Repository Comparative Report: Gemma 4 31B",
        "",
        "## Summary",
        f"- Target Tasks: 5 authentic upstream issues (Flask 4045, 4992, 5063; Requests 1963, 2148)",
        f"- Variants Tested: A_raw, B2_assertion_aware, C_tail35",
        f"- Total Live Inferences: 15 calls on `google/gemma-4-31B-it-qat-w4a16-ct` (temperature=0.0)",
        f"- Context Window: 16,384 tokens (NVIDIA A100 80GB)",
        f"- Evaluation Sandbox: Docker `python:3.12-slim` (`--network none`, `--cap-drop ALL`, `--user 1000:1000`, 1GB RAM)",
        "",
        "## Aggregate Results by Variant",
        "",
        "| Variant | Resolved / Total | Pass Rate (%) | Avg Prompt Tokens | Avg Completion Tokens | Regressions | Syntax Errors | Apply Errors |",
        "|---|---|---|---|---|---|---|---|"
    ]

    for v in VARIANTS:
        s = variant_stats[v]
        tot = s["total"]
        res = s["resolved"]
        rate = (res / tot * 100.0) if tot > 0 else 0.0
        avg_p = sum(s["prompt_tokens"]) / tot if tot > 0 else 0
        avg_c = sum(s["comp_tokens"]) / tot if tot > 0 else 0
        report_lines.append(f"| {v} | {res}/{tot} | {rate:.1f}% | {avg_p:.0f} | {avg_c:.0f} | {s['regression']} | {s['syntax_error']} | {s['patch_apply_error']} |")

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
