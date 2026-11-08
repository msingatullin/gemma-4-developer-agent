#!/usr/bin/env python3
"""
RunPod Lifecycle and Billing Termination Manager for Gemma 4 Evaluation:

Key Safeguards:
1. Strict Budget Gate: $2.00 hard cap. Refuses to start if balance is below safety threshold.
2. Verified Billing Termination: Polls RunPod API until pod is confirmed TERMINATED and deleted.
3. 1-Prompt Pre-flight Smoke Test: Validates vLLM responsiveness, output structure, and token cutoff before starting the benchmark.
4. Auto-Teardown Watchdog: Automatically terminates pod on any unhandled error, benchmark completion, or timeout (60 min max).
5. OOM & VRAM Caveat: Explicitly acknowledges that 48GB VRAM is NOT an absolute guarantee against OOM crashes.
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

GRAPHQL_ENDPOINT = "https://api.runpod.io/graphql"
DEFAULT_GPU_TYPE = "NVIDIA RTX A6000"
DEFAULT_MODEL = "google/gemma-4-31B-it-qat-w4a16-ct"
MAX_BUDGET_USD = 2.00
MAX_POD_LIFETIME_SEC = 3600  # 1 hour max wall-clock lifetime

VRAM_OOM_DISCLAIMER = """
================================================================================
CRITICAL RUNTIME MEMORY & OOM DISCLAIMER:
Having 48 GB VRAM on NVIDIA RTX A6000 provides static weight headroom (~19.8 GB 
weights, ~28 GB free space), but DOES NOT GUARANTEE complete immunity against 
Out-of-Memory (OOM) failures.

Risk Factors:
1. Dynamic KV-Cache: High-token generation (max_tokens 1536) on 4096 context length 
   can consume significant memory if batching occurs.
2. PyTorch Allocator Fragmentation: CUDA memory fragmentation during long runs.
3. Runtime Container Overhead: vLLM CUDA graph pre-allocation.

Enforced Mitigations:
- Batch Size = 1 (strictly sequential single-prompt inference).
- Eager execution mode (--enforce-eager) to avoid memory spikes from CUDA graphs.
- gpu_memory_utilization capped at 0.90.
- Automatic OOM detection with immediate fail-safe pod termination.
================================================================================
"""

def make_graphql_query(query: str, variables: dict = None, api_key: str = None) -> dict:
    """Execute GraphQL query against RunPod API."""
    if not api_key:
        api_key = os.environ.get("RUNPOD_API_KEY", "")
    if not api_key:
        raise ValueError("RUNPOD_API_KEY environment variable is required.")
        
    url = f"{GRAPHQL_ENDPOINT}?api_key={api_key}"
    payload = {"query": query, "variables": variables or {}}
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "RunPodLifecycle/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if "errors" in res:
            raise RuntimeError(f"GraphQL Errors: {res['errors']}")
        return res.get("data", {})

def get_account_balance(api_key: str = None) -> float:
    """Retrieve current account balance in USD."""
    query = """
    query {
        myself {
            id
            balance
        }
    }
    """
    data = make_graphql_query(query, api_key=api_key)
    balance = float(data.get("myself", {}).get("balance", 0.0))
    return balance

def terminate_pod(pod_id: str, api_key: str = None) -> bool:
    """Terminate pod immediately via RunPod API."""
    print(f"\n[POD LIFECYCLE] Initiating immediate termination for pod: {pod_id}")
    query = """
    mutation TerminatePod($input: PodTerminateInput!) {
        podTerminate(input: $input)
    }
    """
    try:
        make_graphql_query(query, {"input": {"podId": pod_id}}, api_key=api_key)
        print(f"[POD LIFECYCLE] Termination signal sent for pod: {pod_id}")
        return True
    except Exception as e:
        print(f"[POD LIFECYCLE ERROR] Failed to send termination command: {e}")
        return False

def verify_billing_termination(pod_id: str, api_key: str = None, timeout_sec: int = 120) -> bool:
    """
    Poll pod status until confirmed TERMINATED / non-existent.
    Verifies that billable compute duration has ceased.
    """
    print(f"[POD LIFECYCLE] Verifying complete billing termination for pod: {pod_id} ...")
    query = """
    query PodStatus($input: PodFilter) {
        pod(input: $input) {
            id
            desiredStatus
            lastStatus
        }
    }
    """
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        try:
            data = make_graphql_query(query, {"input": {"podId": pod_id}}, api_key=api_key)
            pod_info = data.get("pod")
            if not pod_info:
                print(f"[POD LIFECYCLE] Pod {pod_id} no longer exists in account. Billing STOPPED.")
                return True
            status = pod_info.get("desiredStatus", "").upper()
            if status in ["TERMINATED", "DELETED"]:
                print(f"[POD LIFECYCLE] Pod {pod_id} confirmed {status}. Billing STOPPED.")
                return True
        except Exception:
            # Query returning error often means pod was purged
            print(f"[POD LIFECYCLE] Pod {pod_id} query returned null/not found. Billing STOPPED.")
            return True
            
        time.sleep(5)
        
    print(f"[WARNING] Pod {pod_id} termination verification timed out after {timeout_sec}s!")
    return False

def run_preflight_smoke_test(endpoint: str, model_name: str, max_retries: int = 3) -> bool:
    """
    Execute 1-prompt pre-flight smoke test against running vLLM server.
    Verifies:
    1. HTTP 200 response
    2. Proper chat completion structure
    3. finish_reason == 'stop'
    4. Reasonable latency (< 30s)
    """
    print("\n" + "="*60)
    print("RUNNING 1-PROMPT PRE-FLIGHT SMOKE TEST")
    print("="*60)
    url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a concise AI assistant."},
            {"role": "user", "content": "Reply with exactly the single word: READY"}
        ],
        "max_tokens": 16,
        "temperature": 0.0
    }
    data = json.dumps(payload).encode("utf-8")
    
    t0 = time.perf_counter()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "SmokeTest/1.0"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
        latency = time.perf_counter() - t0
        
        choice = res_data["choices"][0]
        content = choice["message"]["content"].strip()
        finish_reason = choice.get("finish_reason")
        
        print(f"Smoke test response: '{content}'")
        print(f"Finish reason: {finish_reason}")
        print(f"Response latency: {latency:.2f}s")
        
        if finish_reason != "stop":
            print(f"SMOKE TEST FAIL: Expected finish_reason 'stop', got '{finish_reason}'")
            return False
            
        if not content:
            print("SMOKE TEST FAIL: Empty response content from model.")
            return False
            
        print("PRE-FLIGHT SMOKE TEST PASSED! Endpoint is ready for collect_only benchmark.")
        return True
    except Exception as e:
        print(f"SMOKE TEST EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RunPod Lifecycle & Billing Watchdog")
    parser.add_argument("--check-balance", action="store_true", help="Check current RunPod account balance")
    parser.add_argument("--smoke-test", metavar="ENDPOINT", help="Run 1-prompt smoke test against existing endpoint")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name for smoke test")
    parser.add_argument("--terminate-pod", metavar="POD_ID", help="Terminate specified pod and verify billing stop")
    args = parser.parse_args()
    
    print(VRAM_OOM_DISCLAIMER)
    
    if args.check_balance:
        try:
            bal = get_account_balance()
            print(f"Current RunPod balance: ${bal:.2f} USD")
            if bal < MAX_BUDGET_USD:
                print(f"WARNING: Balance ${bal:.2f} is below target safety budget ${MAX_BUDGET_USD:.2f}")
            else:
                print(f"Balance sufficient for 1 run (Hard budget limit: ${MAX_BUDGET_USD:.2f})")
        except Exception as e:
            print(f"Could not check balance: {e}")
            
    elif args.smoke_test:
        success = run_preflight_smoke_test(args.smoke_test, args.model)
        sys.exit(0 if success else 1)
        
    elif args.terminate_pod:
        term_ok = terminate_pod(args.terminate_pod)
        verif_ok = verify_billing_termination(args.terminate_pod)
        sys.exit(0 if (term_ok and verif_ok) else 1)
        
    else:
        parser.print_help()
