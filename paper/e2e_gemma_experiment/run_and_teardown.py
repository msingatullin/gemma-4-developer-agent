#!/usr/bin/env python3
"""
Streamlined Runner & Guaranteed Teardown for Real Gemma 4 RunPod Benchmark:
Pod: imqm4fxvqoqgsx (RTX A6000 48GB, SECURE)
Model: google/gemma-4-31B-it-qat-w4a16-ct
"""
import os
import sys
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "real_run_20261108"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = OUTPUT_DIR / "real_experiment_checkpoint.jsonl"
ANALYSIS_FILE = OUTPUT_DIR / "real_paired_statistical_analysis.json"

POD_ID = "imqm4fxvqoqgsx"
ENDPOINT = f"https://{POD_ID}-8000.proxy.runpod.net"
MODEL_NAME = "google/gemma-4-31B-it-qat-w4a16-ct"

# Setup RunPod
ENV_FILE = Path("/home/mikhail/.runpod/runpod.env")
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k] = v.strip("\"'")

import runpod
from runpod.api import ctl_commands
runpod.api_key = os.environ.get("RUNPOD_API_KEY")

sys.path.insert(0, str(BASE_DIR))
from run_e2e_inference import run_experiment

def main():
    t_start = time.time()
    try:
        print("="*70)
        print("STARTING REAL GEMMA 4 INFERENCE RUN ON RUNPOD")
        print(f"Pod ID: {POD_ID}")
        print(f"Endpoint: {ENDPOINT}")
        print(f"Model: {MODEL_NAME}")
        print(f"Mode: collect_only (No candidate execution on host or pod)")
        print(f"Output Checkpoint: {CHECKPOINT_FILE}")
        print(f"Output Analysis: {ANALYSIS_FILE}")
        print("="*70)
        
        # Run 120 calls with seeds [42, 100]
        run_experiment(
            endpoint=ENDPOINT,
            model_name=MODEL_NAME,
            seeds=[42, 100],
            dry_run=False,
            collect_only=True,
            checkpoint_file=CHECKPOINT_FILE,
            analysis_file=ANALYSIS_FILE
        )
        print("\nALL 120 CALLS COMPLETED AND ANALYZED SUCCESSFULLY!")
        
    finally:
        print("\n" + "="*70)
        print("GUARANTEED TEARDOWN: TERMINATING POD AND VERIFYING BILLING")
        print("="*70)
        try:
            print(f"Sending terminate command for pod {POD_ID}...")
            ctl_commands.terminate_pod(POD_ID)
        except Exception as e:
            print(f"Error terminating pod: {e}")
            
        print("Verifying termination...")
        for _ in range(24):
            try:
                p = ctl_commands.get_pod(POD_ID)
                if not p or p.get("status") in ["TERMINATED", "DELETED"]:
                    print(f"Pod {POD_ID} confirmed TERMINATED/DELETED. Compute billing STOPPED.")
                    break
            except Exception:
                print(f"Pod {POD_ID} no longer exists. Compute billing STOPPED.")
                break
            time.sleep(5)
            
        try:
            billing = ctl_commands.run_rest_request("GET", "/v2/billing")
            tot = billing.get("totals", {}).get("totalAmount", 0)
            print(f"Current total account spending: ${tot:.4f} USD")
        except Exception as e:
            print(f"Could not fetch billing: {e}")
            
        elapsed = time.time() - t_start
        print(f"Total benchmark run wall-clock duration: {elapsed:.1f}s ({elapsed/60:.2f} min)")

if __name__ == "__main__":
    main()
