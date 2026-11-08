#!/usr/bin/env python3
"""
Paired Statistical Analysis Module for Gemma 4 Evaluation.
Computes task-clustered paired differences, 95% bootstrap confidence intervals,
and permutation p-values where the Task (not the seed) is the sampling unit.
"""
import math
import random
from collections import defaultdict

def compute_task_clustered_paired_stats(
    results: list[dict],
    metric_key: str = "test_suite_pass",
    variants: list[str] = ("A_raw", "B_compressed", "C_tail35", "D_no_trace"),
    n_bootstrap: int = 10000,
    seed: int = 42
) -> dict:
    """
    Compute paired differences and 95% bootstrap confidence intervals.
    
    The sampling unit is the Task ID. If there are K seeds per task,
    the score for (task, variant) is the mean over the K seeds.
    
    Returns a dictionary of paired statistics:
    - delta(B - A)
    - delta(B - C)
    - delta(B - D)
    with mean, std, 95% CI [lower, upper], and paired p-value.
    """
    # 1. Aggregate by (task_id, variant) -> mean across seeds
    task_scores = defaultdict(lambda: defaultdict(list))
    for r in results:
        tid = r["task_id"]
        var = r["variant"]
        val = 1.0 if r.get(metric_key) else 0.0
        task_scores[tid][var].append(val)
        
    tasks = sorted(task_scores.keys())
    n_tasks = len(tasks)
    if n_tasks == 0:
        return {}
        
    task_means = {
        tid: {v: (sum(vals) / len(vals) if vals else 0.0) for v, vals in task_scores[tid].items()}
        for tid in tasks
    }
    
    # 2. Compute paired differences per task
    comparisons = [
        ("B_compressed", "A_raw", "delta_B_minus_A"),
        ("B_compressed", "C_tail35", "delta_B_minus_C"),
    ]
    if any("D_no_trace" in task_means[t] for t in tasks):
        comparisons.append(("B_compressed", "D_no_trace", "delta_B_minus_D"))
        
    paired_deltas = {}
    for v1, v2, label in comparisons:
        deltas = [task_means[tid].get(v1, 0.0) - task_means[tid].get(v2, 0.0) for tid in tasks]
        mean_delta = sum(deltas) / n_tasks
        
        # 3. Task-level clustered bootstrap for 95% CI
        rng = random.Random(seed)
        boot_means = []
        for _ in range(n_bootstrap):
            resampled_deltas = [deltas[rng.randrange(n_tasks)] for _ in range(n_tasks)]
            boot_means.append(sum(resampled_deltas) / n_tasks)
            
        boot_means.sort()
        ci_lower = boot_means[int(0.025 * n_bootstrap)]
        ci_upper = boot_means[int(0.975 * n_bootstrap)]
        
        # 4. Paired permutation test for p-value (sign flipping under H0: mean delta == 0)
        perm_means = []
        for _ in range(n_bootstrap):
            flipped = [d if rng.random() > 0.5 else -d for d in deltas]
            perm_means.append(sum(flipped) / n_tasks)
            
        abs_mean = abs(mean_delta)
        p_val = sum(1 for m in perm_means if abs(m) >= abs_mean) / n_bootstrap
        
        paired_deltas[label] = {
            "v1": v1,
            "v2": v2,
            "mean_delta": mean_delta,
            "ci_95_lower": ci_lower,
            "ci_95_upper": ci_upper,
            "p_value_permutation": p_val,
            "task_deltas": {tid: round(task_means[tid].get(v1, 0.0) - task_means[tid].get(v2, 0.0), 4) for tid in tasks}
        }
        
    return {
        "n_tasks": n_tasks,
        "metric_evaluated": metric_key,
        "n_bootstrap": n_bootstrap,
        "paired_comparisons": paired_deltas
    }

if __name__ == "__main__":
    print("Testing paired statistics module...")
    # Mock data with 15 tasks: B beats A by 0.20 on average
    mock_results = []
    for i in range(1, 16):
        tid = f"task_{i:02d}"
        for seed in [42, 100]:
            # B passes 60% of time, A passes 40% of time, C passes 30% of time
            mock_results.append({"task_id": tid, "variant": "A_raw", "seed": seed, "test_suite_pass": i <= 6})
            mock_results.append({"task_id": tid, "variant": "B_compressed", "seed": seed, "test_suite_pass": i <= 9})
            mock_results.append({"task_id": tid, "variant": "C_tail35", "seed": seed, "test_suite_pass": i <= 4})
            
    stats = compute_task_clustered_paired_stats(mock_results, "test_suite_pass")
    b_vs_a = stats["paired_comparisons"]["delta_B_minus_A"]
    print(f"Delta(B - A): {b_vs_a['mean_delta']:.4f} (95% CI: [{b_vs_a['ci_95_lower']:.4f}, {b_vs_a['ci_95_upper']:.4f}], p={b_vs_a['p_value_permutation']:.4f})")
    assert b_vs_a["mean_delta"] == 0.20
    assert b_vs_a["ci_95_lower"] >= 0
    assert b_vs_a["ci_95_upper"] > 0
    print("Paired statistics self-test PASSED!")
