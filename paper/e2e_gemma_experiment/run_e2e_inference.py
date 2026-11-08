#!/usr/bin/env python3
"""
Robust, Resilient E2E Inference Runner for Gemma 4 Evaluation:
- Incremental checkpointing: appends to JSONL after EVERY call
- Safe resumption: skips already completed (task_id, variant, seed) keys without duplicating
- Truncation / finish_reason validation
- Balanced Latin-Square variant ordering across tasks to prevent sequence bias
- Full model and environment metadata recording
- Task-clustered paired statistical bootstrap analysis (Task as unit of analysis)
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
CHECKPOINT_FILE = BASE_DIR / "experiment_checkpoint.jsonl"
PAIRED_ANALYSIS_FILE = BASE_DIR / "paired_statistical_analysis.json"

sys.path.insert(0, str(BASE_DIR))
from evaluator import evaluate_response
from statistics import compute_task_clustered_paired_stats

VARIANTS = ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]

def check_endpoint_health(endpoint: str, model_name: str) -> dict:
    """Verify endpoint is responsive and returns model info."""
    url = f"{endpoint.rstrip('/')}/v1/models"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GemmaEvaluation/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Endpoint health check PASSED. Available models: {[m.get('id') for m in data.get('data', [])]}")
            return {"status": "ok", "models": data}
    except Exception as e:
        print(f"Warning: Endpoint health check query to {url} failed: {e}")
        return {"status": "unreachable", "error": str(e)}

def call_vllm_api(endpoint: str, model_name: str, system_prompt: str, user_prompt: str, seed: int, max_tokens: int = 1024, temp: float = 0.2, max_retries: int = 3) -> tuple[str, str, float, int]:
    """Call an OpenAI-compatible vLLM endpoint with retry logic and finish_reason check."""
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
    
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=180) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - t0
            
            choice = res_data["choices"][0]
            resp_text = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "unknown")
            usage = res_data.get("usage", {}).get("total_tokens", 0)
            return resp_text, finish_reason, latency, usage
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
            
    raise RuntimeError(f"Failed after {max_retries} attempts: {last_err}")

def load_completed_checkpoints() -> dict:
    """Load existing checkpoints from JSONL file."""
    completed = {}
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        key = (record["task_id"], record["variant"], record["seed"])
                        completed[key] = record
                    except Exception:
                        pass
    return completed

def append_checkpoint(record: dict):
    """Atomically append a single execution record to checkpoint JSONL."""
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def run_experiment(endpoint: str, model_name: str, seeds: list[int], dry_run: bool = False):
    manifest_p = BASE_DIR / "task_manifest.json"
    tasks = json.loads(manifest_p.read_text(encoding="utf-8"))
    
    completed_checkpoints = load_completed_checkpoints()
    print(f"Loaded {len(completed_checkpoints)} already completed records from {CHECKPOINT_FILE}")
    
    if not dry_run:
        check_endpoint_health(endpoint, model_name)
        
    total_planned = len(tasks) * len(VARIANTS) * len(seeds)
    print(f"\nStarting Gemma 4 E2E Benchmark:")
    print(f"  Model: {model_name}")
    print(f"  Tasks: {len(tasks)} tasks")
    print(f"  Variants: {VARIANTS} (balanced Latin-square ordering)")
    print(f"  Seeds: {seeds}")
    print(f"  Total planned inference calls: {total_planned}")
    
    records_in_memory = list(completed_checkpoints.values())
    call_idx = len(completed_checkpoints)
    
    for seed in seeds:
        print(f"\n=== SEED {seed} ===")
        for task_idx, t in enumerate(tasks):
            tid = t["id"]
            
            # Balanced Latin-Square rotation of variant order per task to remove order bias
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
                    resp_text = f"DEFECT_LOCATION: {t['target_symbol']}\nROOT_CAUSE: {t['root_cause']}\nPROPOSED_CODE:\n```python\n# dry run mock\npass\n```"
                    finish_reason = "stop"
                    latency = 0.01
                    tokens = 150
                else:
                    resp_text, finish_reason, latency, tokens = call_vllm_api(
                        endpoint=endpoint,
                        model_name=model_name,
                        system_prompt=precord["system_prompt"],
                        user_prompt=precord["user_prompt"],
                        seed=seed
                    )
                    
                # Blinded & sandboxed evaluation
                eval_res = evaluate_response(tid, resp_text, t)
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
                append_checkpoint(record)
                completed_checkpoints[ckey] = record
                records_in_memory.append(record)
                
                print(f"Loc: {'PASS' if eval_res['blinded_localization_pass'] else 'FAIL'} | "
                      f"Syntax: {'PASS' if eval_res['preflight_syntax_pass'] else 'FAIL'} | "
                      f"Test: {'PASS' if eval_res['test_suite_pass'] else 'FAIL'} ({latency:.2f}s, finish: {finish_reason})")

    # Perform full task-clustered paired statistical bootstrap analysis
    run_paired_analysis(records_in_memory)

def run_paired_analysis(results: list[dict]):
    """Execute task-clustered paired statistical bootstrap across multiple metrics."""
    metrics = ["test_suite_pass", "blinded_localization_pass", "preflight_syntax_pass"]
    
    full_analysis = {
        "analysis_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_records": len(results),
        "metrics_evaluated": {}
    }
    
    print("\n" + "="*70)
    print("TASK-CLUSTERED PAIRED STATISTICAL BOOTSTRAP ANALYSIS (N=10,000 resamples)")
    print("Sampling unit: Task ID (Seeds averaged within task)")
    print("="*70)
    
    for m in metrics:
        stats = compute_task_clustered_paired_stats(results, metric_key=m, n_bootstrap=10000)
        full_analysis["metrics_evaluated"][m] = stats
        
        print(f"\nMetric: {m.upper()}")
        for comp_name, comp in stats.get("paired_comparisons", {}).items():
            print(f"  {comp_name:20s}: Δ = {comp['mean_delta']:+.4f} (95% CI: [{comp['ci_95_lower']:+.4f}, {comp['ci_95_upper']:+.4f}], p = {comp['p_value_permutation']:.4f})")
            
    PAIRED_ANALYSIS_FILE.write_text(json.dumps(full_analysis, indent=2), encoding="utf-8")
    print(f"\nFull paired analysis saved to {PAIRED_ANALYSIS_FILE}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8000")
    parser.add_argument("--model", default="google/gemma-4-31B-it-qat-w4a16-ct")
    parser.add_argument("--seeds", default="42,100")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    seeds = [int(s.strip()) for s in args.seeds.split(",")]
    run_experiment(args.endpoint, args.model, seeds, dry_run=args.dry_run)
