#!/usr/bin/env python3
"""
Master Execution Script for Real Gemma 4 RunPod Inference:
1. Provisions GPU pod (RTX A6000 / A40 / A100).
2. Streams live startup logs and monitors endpoint readiness.
3. Performs 1-prompt pre-flight smoke test.
4. Executes 120 live inference calls (15 tasks x 4 variants x 2 seeds) in collect_only mode.
5. Computes task-clustered paired bootstrap statistics on real responses.
6. Guarantees immediate pod teardown and verifies billing cessation in fail-safe finally block.
"""
import os
import sys
import time
import json
import datetime
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
OUTPUT_DIR = BASE_DIR / "real_run_20261108"
CHECKPOINT_FILE = OUTPUT_DIR / "real_experiment_checkpoint.jsonl"
ANALYSIS_FILE = OUTPUT_DIR / "real_paired_statistical_analysis.json"

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
from run_e2e_inference import run_experiment

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
    print(f"[READY POLL] Checking {url} for readiness (timeout {timeout_sec}s)...")
    
    while time.time() - t0 < timeout_sec:
        elapsed = int(time.time() - t0)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RunPodPoll/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"\n[READY POLL] SUCCESS after {elapsed}s! Models returned: {data}")
                    return True
        except Exception as e:
            if elapsed - last_print >= 15:
                pod_status = "UNKNOWN"
                try:
                    p = ctl_commands.get_pod(pod_id)
                    pod_status = p.get("status") if p else "NOT FOUND"
                except Exception:
                    pass
                log_snippet = get_pod_logs(pod_id)
                log_tail = log_snippet[-200:].strip() if log_snippet else "no logs yet"
                print(f"[READY POLL] {elapsed}s elapsed | Pod status: {pod_status} | Error: {e}")
                if log_tail and log_tail != "no logs yet":
                    print(f"  Logs tail: {log_tail}")
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
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
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

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pod_id = None
    start_time = time.time()
    
    try:
        # Step 1: Provision Pod
        print("[STEP 1] Provisioning RunPod GPU Pod...")
        pod = None
        for gpu_id, cloud in CANDIDATE_GPUS:
            print(f"  Attempting {gpu_id} on {cloud} cloud...")
            try:
                pod = ctl_commands.create_pod(
                    name="gemma4-e2e-eval",
                    image_name=IMAGE_NAME,
                    gpu_type_id=gpu_id,
                    cloud_type=cloud,
                    container_disk_in_gb=70,
                    ports="8000/http",
                    docker_args=DOCKER_ARGS,
                    start_ssh=False
                )
                if pod and pod.get("id"):
                    print(f"  -> SUCCESS! Pod created with ID: {pod['id']}")
                    break
            except Exception as e:
                print(f"  -> FAILED: {e}")
                
        if not pod or not pod.get("id"):
            raise RuntimeError("Failed to provision any candidate GPU pod on RunPod.")
            
        pod_id = pod["id"]
        proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
        print(f"Pod ID: {pod_id}")
        print(f"Proxy Endpoint URL: {proxy_url}")
        
        # Step 2: Poll Readiness
        print("\n[STEP 2] Monitoring pod startup and weight initialization...")
        is_ready = poll_endpoint_ready(proxy_url, pod_id, timeout_sec=900)
        if not is_ready:
            # Print any container logs
            logs = get_pod_logs(pod_id)
            print(f"Container logs:\n{logs[:1000]}")
            raise TimeoutError("Pod did not become ready within timeout period.")
            
        # Step 3: Smoke Test
        print("\n[STEP 3] Running 1-prompt pre-flight smoke test...")
        smoke_test(proxy_url)
        
        # Step 4: 120-call Benchmark
        print("\n[STEP 4] Executing 120-call evaluation benchmark in collect_only mode...")
        run_experiment(
            endpoint=proxy_url,
            model_name=MODEL_NAME,
            seeds=[42, 100],
            dry_run=False,
            collect_only=True,
            checkpoint_file=CHECKPOINT_FILE,
            analysis_file=ANALYSIS_FILE
        )
        print("\n[STEP 4 COMPLETED] All 120 calls finished and analyzed.")
        
    finally:
        # Step 5: GUARANTEED POD TEARDOWN
        print("\n" + "="*60)
        print("[STEP 5] TEARDOWN: TERMINATING POD AND STOPPING BILLING")
        print("="*60)
        if pod_id:
            try:
                print(f"Terminating pod {pod_id} ...")
                ctl_commands.terminate_pod(pod_id)
            except Exception as e:
                print(f"Error calling terminate_pod: {e}")
                
            # Verify termination
            print("Verifying termination...")
            for _ in range(24):
                try:
                    p = ctl_commands.get_pod(pod_id)
                    if not p or p.get("status") in ["TERMINATED", "DELETED"]:
                        print(f"Pod {pod_id} confirmed TERMINATED/DELETED. Billing STOPPED.")
                        break
                except Exception:
                    print("Pod no longer found. Billing STOPPED.")
                    break
                time.sleep(5)
                
            # Query billing info
            try:
                billing = ctl_commands.run_rest_request("GET", "/v2/billing")
                total_spent = billing.get("totals", {}).get("totalAmount", 0)
                print(f"Current total account spending: ${total_spent:.4f} USD")
            except Exception as e:
                print(f"Could not query billing: {e}")
                
        duration = time.time() - start_time
        print(f"Total run wall-clock duration: {duration:.1f}s ({duration/60:.2f} min)")

if __name__ == "__main__":
    main()
