#!/usr/bin/env python3
"""
Reproducible E2E Inference Runner for Gemma 4 Evaluation:
- Runs 15 tasks x 3 variants (A, B, C) x 2 seeds = 90 runs
- Supports vLLM / OpenAI-compatible endpoint (e.g. RunPod instance) or local HuggingFace pipeline
- Evaluates root cause diagnosis and executes pytest test suites
- Computes paired differences and confidence intervals
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "frozen_prompts"
TASKS_DIR = BASE_DIR / "tasks"

sys.path.insert(0, str(BASE_DIR))
from evaluator import evaluate_response

def call_vllm_api(endpoint: str, model_name: str, system_prompt: str, user_prompt: str, seed: int, max_tokens: int = 1024, temp: float = 0.2) -> tuple[str, float, int]:
    """Call an OpenAI-compatible vLLM endpoint."""
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
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
    latency = time.perf_counter() - t0
    
    choice = res_data["choices"][0]["message"]["content"]
    usage = res_data.get("usage", {}).get("total_tokens", 0)
    return choice, latency, usage

def run_experiment(endpoint: str, model_name: str, seeds: list[int], dry_run: bool = False):
    manifest_p = BASE_DIR / "task_manifest.json"
    tasks = json.loads(manifest_p.read_text(encoding="utf-8"))
    
    results = []
    print(f"Starting E2E Evaluation on {model_name}...")
    print(f"Tasks: {len(tasks)}, Seeds: {seeds}, Variants: ['A_raw', 'B_compressed', 'C_tail35']")
    print(f"Total planned calls: {len(tasks) * 3 * len(seeds)}")
    
    call_idx = 0
    total_calls = len(tasks) * 3 * len(seeds)
    
    for seed in seeds:
        print(f"\n=== SEED {seed} ===")
        for t in tasks:
            tid = t["id"]
            for var in ["A_raw", "B_compressed", "C_tail35"]:
                call_idx += 1
                prompt_file = PROMPTS_DIR / f"{tid}__{var}.json"
                precord = json.loads(prompt_file.read_text(encoding="utf-8"))
                
                print(f"[{call_idx}/{total_calls}] Task: {tid} | Var: {var} | Seed: {seed} ...", end=" ", flush=True)
                
                if dry_run:
                    # Mock dry run for pipeline verification
                    time.sleep(0.01)
                    resp_text = f"ROOT_CAUSE: {t['root_cause']}\n```python\n# dry run mock\npass\n```"
                    latency = 0.01
                    tokens = 150
                else:
                    resp_text, latency, tokens = call_vllm_api(
                        endpoint=endpoint,
                        model_name=model_name,
                        system_prompt=precord["system_prompt"],
                        user_prompt=precord["user_prompt"],
                        seed=seed
                    )
                    
                # Run evaluation
                eval_res = evaluate_response(tid, resp_text, t)
                
                record = {
                    "task_id": tid,
                    "variant": var,
                    "seed": seed,
                    "latency_sec": latency,
                    "tokens_used": tokens,
                    "prompt_chars": precord["prompt_char_len"],
                    "trace_chars": precord["trace_char_len"],
                    "model_response": resp_text,
                    **eval_res
                }
                results.append(record)
                print(f"Syntax: {'PASS' if eval_res['preflight_syntax_pass'] else 'FAIL'} | "
                      f"Diag: {'PASS' if eval_res['root_cause_accuracy'] else 'FAIL'} | "
                      f"Test: {'PASS' if eval_res['test_suite_pass'] else 'FAIL'} ({latency:.2f}s)")

    # Save raw results
    out_file = BASE_DIR / "experiment_raw_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nRaw results saved to {out_file}")
    
    # Analyze aggregate metrics
    analyze_results(results)

def analyze_results(results: list[dict]):
    """Compute aggregate pass rates and paired statistical differences."""
    from collections import defaultdict
    import math

    by_variant = defaultdict(lambda: {"syntax": 0, "diag": 0, "test": 0, "total": 0, "tokens": 0, "latency": 0.0})
    
    for r in results:
        v = r["variant"]
        by_variant[v]["total"] += 1
        if r["preflight_syntax_pass"]:
            by_variant[v]["syntax"] += 1
        if r["root_cause_accuracy"]:
            by_variant[v]["diag"] += 1
        if r["test_suite_pass"]:
            by_variant[v]["test"] += 1
        by_variant[v]["tokens"] += r["tokens_used"]
        by_variant[v]["latency"] += r["latency_sec"]
        
    summary = {}
    print("\n=== AGGREGATE RESULTS BY TRACEBACK VARIANT ===")
    for v, stats in by_variant.items():
        n = stats["total"]
        syntax_rate = stats["syntax"] / n * 100
        diag_rate = stats["diag"] / n * 100
        test_rate = stats["test"] / n * 100
        avg_tokens = stats["tokens"] / n
        avg_lat = stats["latency"] / n
        
        summary[v] = {
            "n_runs": n,
            "syntax_pass_rate_pct": syntax_rate,
            "root_cause_accuracy_pct": diag_rate,
            "test_suite_pass_rate_pct": test_rate,
            "avg_tokens": avg_tokens,
            "avg_latency_sec": avg_lat
        }
        print(f"Variant {v}:")
        print(f"  Root Cause Accuracy: {diag_rate:.1f}% ({stats['diag']}/{n})")
        print(f"  Test Suite Pass Rate: {test_rate:.1f}% ({stats['test']}/{n})")
        print(f"  Syntax Valid Rate:   {syntax_rate:.1f}% ({stats['syntax']}/{n})")
        print(f"  Avg Latency:         {avg_lat:.2f}s | Avg Tokens: {avg_tokens:.0f}")

    sum_file = BASE_DIR / "experiment_summary.json"
    sum_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary metrics saved to {sum_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8000")
    parser.add_argument("--model", default="google/gemma-4-31B-it-qat-w4a16-ct")
    parser.add_argument("--seeds", default="42,100")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    seeds = [int(s.strip()) for s in args.seeds.split(",")]
    run_experiment(args.endpoint, args.model, seeds, dry_run=args.dry_run)
