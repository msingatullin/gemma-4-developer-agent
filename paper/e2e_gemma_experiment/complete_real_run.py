#!/usr/bin/env python3
"""
Complete Real Gemma 4 RunPod Inference Run (Resumes from Call 47 to 120):
- Provisions GPU Pod on RTX A6000 (SECURE cloud, $0.59/hr).
- Polls endpoint readiness cleanly.
- Executes smoke test.
- Resumes benchmark, completing all remaining calls up to 120.
- Computes final 120-call paired statistical bootstrap analysis.
- Guaranteed teardown in finally block: terminates pod immediately, verifies deletion, logs billing.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
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

def poll_endpoint_ready(endpoint: str, timeout_sec: int = 900) -> bool:
    """Poll endpoint /v1/models until HTTP 200 is returned."""
    url = f"{endpoint.rstrip('/')}/v1/models"
    t0 = time.time()
    last_print = 0
    print(f"[READY POLL] Checking {url} for readiness (timeout {timeout_sec}s)...", flush=True)
    
    while time.time() - t0 < timeout_sec:
        elapsed = int(time.time() - t0)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"\n[READY POLL] SUCCESS after {elapsed}s! Models returned: {data}", flush=True)
                    return True
        except Exception as e:
            if elapsed - last_print >= 15:
                print(f"[READY POLL] {elapsed}s elapsed: {e}", flush=True)
                last_print = elapsed
        time.sleep(5)
    return False

def smoke_test(endpoint: str) -> bool:
    """Run single 1-prompt pre-flight check."""
    print("\n" + "="*60, flush=True)
    print("RUNNING PRE-FLIGHT SMOKE TEST", flush=True)
    print("="*60, flush=True)
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
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    lat = time.perf_counter() - t0
    choice = res["choices"][0]
    content = choice["message"]["content"].strip()
    finish = choice.get("finish_reason")
    print(f"Smoke test output: '{content}' (finish: {finish}, latency: {lat:.2f}s)", flush=True)
    if finish != "stop" or not content:
        raise RuntimeError(f"Smoke test failed: content='{content}', finish='{finish}'")
    print("PRE-FLIGHT SMOKE TEST PASSED SUCCESSFULLY!\n", flush=True)
    return True

def main():
    pod_id = None
    start_time = time.time()
    
    try:
        # Step 1: Provision Pod
        print("[STEP 1] Provisioning RunPod GPU Pod for Benchmark Completion...", flush=True)
        pod = None
        for gpu_id, cloud in CANDIDATE_GPUS:
            print(f"  Attempting {gpu_id} on {cloud} cloud...", flush=True)
            try:
                pod = ctl_commands.create_pod(
                    name="gemma4-e2e-completion",
                    image_name=IMAGE_NAME,
                    gpu_type_id=gpu_id,
                    cloud_type=cloud,
                    container_disk_in_gb=70,
                    ports="8000/http",
                    docker_args=DOCKER_ARGS,
                    start_ssh=False
                )
                if pod and pod.get("id"):
                    print(f"  -> SUCCESS! Pod created with ID: {pod['id']}", flush=True)
                    break
            except Exception as e:
                print(f"  -> FAILED: {e}", flush=True)
                
        if not pod or not pod.get("id"):
            raise RuntimeError("Failed to provision candidate GPU pod on RunPod.")
            
        pod_id = pod["id"]
        proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
        print(f"Pod ID: {pod_id}", flush=True)
        print(f"Proxy Endpoint URL: {proxy_url}", flush=True)
        
        # Step 2: Poll Readiness
        print("\n[STEP 2] Monitoring pod startup and weight initialization...", flush=True)
        is_ready = poll_endpoint_ready(proxy_url, timeout_sec=900)
        if not is_ready:
            raise TimeoutError("Pod did not become ready within timeout period.")
            
        # Step 3: Smoke Test
        print("\n[STEP 3] Running 1-prompt pre-flight smoke test...", flush=True)
        smoke_test(proxy_url)
        
        # Step 4: Resume Benchmark (Calls 47 to 120)
        print("\n[STEP 4] Resuming evaluation benchmark in collect_only mode...", flush=True)
        run_experiment(
            endpoint=proxy_url,
            model_name=MODEL_NAME,
            seeds=[42, 100],
            dry_run=False,
            collect_only=True,
            checkpoint_file=CHECKPOINT_FILE,
            analysis_file=ANALYSIS_FILE
        )
        print("\n[STEP 4 COMPLETED] Full 120-call evaluation completed successfully!", flush=True)
        
    finally:
        # Step 5: GUARANTEED POD TEARDOWN
        print("\n" + "="*70, flush=True)
        print("[STEP 5] TEARDOWN: TERMINATING POD AND VERIFYING BILLING", flush=True)
        print("="*70, flush=True)
        if pod_id:
            try:
                print(f"Sending terminate command for pod {pod_id} ...", flush=True)
                ctl_commands.terminate_pod(pod_id)
            except Exception as e:
                print(f"Error calling terminate_pod: {e}", flush=True)
                
            print("Verifying termination...", flush=True)
            for _ in range(24):
                try:
                    p = ctl_commands.get_pod(pod_id)
                    if not p or p.get("status") in ["TERMINATED", "DELETED"]:
                        print(f"Pod {pod_id} confirmed TERMINATED/DELETED. Compute billing STOPPED.", flush=True)
                        break
                except Exception:
                    print(f"Pod {pod_id} no longer exists. Compute billing STOPPED.", flush=True)
                    break
                time.sleep(5)
                
            try:
                billing = ctl_commands.run_rest_request("GET", "/v2/billing")
                total_spent = billing.get("totals", {}).get("totalAmount", 0)
                print(f"Current total account spending: ${total_spent:.4f} USD", flush=True)
            except Exception as e:
                print(f"Could not query billing: {e}", flush=True)
                
        duration = time.time() - start_time
        print(f"Total run wall-clock duration: {duration:.1f}s ({duration/60:.2f} min)", flush=True)

if __name__ == "__main__":
    main()
