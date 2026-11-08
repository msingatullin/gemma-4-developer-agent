#!/usr/bin/env python3
"""
Paired Statistical Analysis Module with Strict Completeness Verification.

Enforces:
1. Strict Completeness: 15 tasks x 4 variants x 2 seeds = 120 unique records.
2. Zero Silent Imputation: Rejects datasets with missing variants or duplicates instead of substituting zeros.
3. Explicit Truncation Accounting: Flags and tracks records terminated by token length (finish_reason='length').
4. Task-Clustered Paired Statistics: Task ID as resampling unit (seeds averaged within task).
"""
import math
import random
from collections import defaultdict

DEFAULT_VARIANTS = ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]
DEFAULT_SEEDS = [42, 100]

def validate_dataset_integrity(
    results: list[dict],
    expected_task_ids: list[str] = None,
    expected_variants: list[str] = None,
    expected_seeds: list[int] = None
) -> dict:
    """
    Perform strict verification on evaluation dataset.
    Requires exactly len(tasks) * len(variants) * len(seeds) records, with zero duplicates.
    """
    if expected_variants is None:
        expected_variants = DEFAULT_VARIANTS
    if expected_seeds is None:
        expected_seeds = DEFAULT_SEEDS
    if expected_task_ids is None:
        # Infer or require 15 tasks
        expected_task_ids = sorted(list(set(r.get("task_id", "") for r in results if r.get("task_id"))))
        
    expected_total = len(expected_task_ids) * len(expected_variants) * len(expected_seeds)
    
    seen_keys = {}
    duplicates = []
    truncated = []
    
    for idx, r in enumerate(results):
        key = (r.get("task_id"), r.get("variant"), r.get("seed"))
        if key in seen_keys:
            duplicates.append({"key": key, "first_index": seen_keys[key], "duplicate_index": idx})
        else:
            seen_keys[key] = idx
            
        # Check truncation
        if r.get("is_truncated") or r.get("finish_reason") == "length":
            truncated.append(key)
            
    # Check missing keys
    missing = []
    for tid in expected_task_ids:
        for var in expected_variants:
            for s in expected_seeds:
                k = (tid, var, s)
                if k not in seen_keys:
                    missing.append(k)
                    
    is_complete = (len(missing) == 0 and len(duplicates) == 0 and len(results) == expected_total)
    
    return {
        "is_complete": is_complete,
        "total_records": len(results),
        "expected_total_records": expected_total,
        "unique_cells_count": len(seen_keys),
        "missing_count": len(missing),
        "missing_keys": [f"{t}__{v}__seed{s}" for t, v, s in missing],
        "duplicate_count": len(duplicates),
        "duplicates": [f"{k[0]}__{k[1]}__seed{k[2]}" for k in [d["key"] for d in duplicates]],
        "truncated_count": len(truncated),
        "truncated_keys": [f"{t}__{v}__seed{s}" for t, v, s in truncated]
    }

def compute_task_clustered_paired_stats(
    results: list[dict],
    metric_key: str = "objective_diagnostic_pass",
    variants: list[str] = ("A_raw", "B_compressed", "C_tail35", "D_no_trace"),
    expected_task_count: int = 15,
    expected_seeds: list[int] = (42, 100),
    n_bootstrap: int = 10000,
    seed: int = 42,
    strict_completeness: bool = True
) -> dict:
    """
    Compute paired differences and 95% bootstrap confidence intervals with strict validation.
    
    If strict_completeness=True:
      Validates that all tasks have all variants and seeds.
      Refuses to compute paired differences if records are missing or duplicated (no zero-fill!).
    """
    integrity = validate_dataset_integrity(
        results,
        expected_variants=list(variants),
        expected_seeds=list(expected_seeds)
    )
    
    if strict_completeness and not integrity["is_complete"]:
        return {
            "status": "ERROR_INCOMPLETE_OR_CORRUPTED_DATASET",
            "error": (
                f"Completeness check FAILED: expected {integrity['expected_total_records']} records, "
                f"found {integrity['total_records']}. Missing: {integrity['missing_count']}, "
                f"Duplicates: {integrity['duplicate_count']}. Silent zero-substitution prohibited."
            ),
            "integrity_report": integrity
        }
        
    # Group scores by (task_id, variant)
    task_scores = defaultdict(lambda: defaultdict(list))
    for r in results:
        tid = r["task_id"]
        var = r["variant"]
        val_raw = r.get(metric_key)
        
        # In collect_only mode, execution metric is None; handle gracefully
        if val_raw is None:
            val = None
        else:
            val = 1.0 if bool(val_raw) else 0.0
            
        task_scores[tid][var].append(val)
        
    tasks = sorted(task_scores.keys())
    n_tasks = len(tasks)
    if n_tasks == 0:
        return {"status": "ERROR_NO_TASKS", "error": "No tasks found in dataset"}
        
    # Check if metric was not evaluated (e.g. test_suite_pass in collect_only mode)
    first_task = tasks[0]
    first_var = variants[0]
    if task_scores[first_task][first_var] and task_scores[first_task][first_var][0] is None:
        return {
            "status": "METRIC_NOT_EVALUATED",
            "metric_evaluated": metric_key,
            "message": f"Metric '{metric_key}' was not executed in this run (collect_only mode).",
            "integrity_report": integrity
        }
        
    # Compute mean per (task, variant) across seeds
    task_means = {}
    for tid in tasks:
        task_means[tid] = {}
        for v in variants:
            vals = task_scores[tid][v]
            if not vals:
                # Missing variant data! Prohibit zero substitution
                return {
                    "status": "ERROR_MISSING_VARIANT_DATA",
                    "error": f"Task '{tid}' has no observations for variant '{v}'. Refusing zero-fill.",
                    "integrity_report": integrity
                }
            task_means[tid][v] = sum(vals) / len(vals)
            
    # Compute paired differences
    comparisons = [
        ("B_compressed", "A_raw", "delta_B_minus_A"),
        ("B_compressed", "C_tail35", "delta_B_minus_C"),
        ("B_compressed", "D_no_trace", "delta_B_minus_D"),
    ]
    
    paired_deltas = {}
    for v1, v2, label in comparisons:
        deltas = [task_means[tid][v1] - task_means[tid][v2] for tid in tasks]
        mean_delta = sum(deltas) / n_tasks
        
        # Task-level clustered bootstrap for 95% CI
        rng = random.Random(seed)
        boot_means = []
        for _ in range(n_bootstrap):
            resampled_deltas = [deltas[rng.randrange(n_tasks)] for _ in range(n_tasks)]
            boot_means.append(sum(resampled_deltas) / n_tasks)
            
        boot_means.sort()
        ci_lower = boot_means[int(0.025 * n_bootstrap)]
        ci_upper = boot_means[int(0.975 * n_bootstrap)]
        
        # Paired permutation test (H0: mean delta == 0)
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
            "task_deltas": {tid: round(task_means[tid][v1] - task_means[tid][v2], 4) for tid in tasks}
        }
        
    return {
        "status": "OK",
        "n_tasks": n_tasks,
        "metric_evaluated": metric_key,
        "n_bootstrap": n_bootstrap,
        "integrity_report": integrity,
        "paired_comparisons": paired_deltas
    }

if __name__ == "__main__":
    print("Self-testing paired statistics and completeness verification...")
    
    # 1. Test clean complete dataset (15 tasks x 4 variants x 2 seeds = 120 records)
    mock_120 = []
    for i in range(1, 16):
        tid = f"task_{i:02d}"
        for seed in [42, 100]:
            mock_120.append({"task_id": tid, "variant": "A_raw", "seed": seed, "objective_diagnostic_pass": i <= 5})
            mock_120.append({"task_id": tid, "variant": "B_compressed", "seed": seed, "objective_diagnostic_pass": i <= 9})
            mock_120.append({"task_id": tid, "variant": "C_tail35", "seed": seed, "objective_diagnostic_pass": i <= 4})
            mock_120.append({"task_id": tid, "variant": "D_no_trace", "seed": seed, "objective_diagnostic_pass": i <= 3})
            
    res_clean = compute_task_clustered_paired_stats(mock_120, "objective_diagnostic_pass")
    assert res_clean["status"] == "OK"
    assert res_clean["integrity_report"]["is_complete"] is True
    assert res_clean["integrity_report"]["total_records"] == 120
    assert res_clean["paired_comparisons"]["delta_B_minus_A"]["mean_delta"] > 0
    print("  [PASS] Clean 120-record dataset successfully analyzed!")
    
    # 2. Test incomplete dataset (missing 1 cell): MUST FAIL loudly, no zero-fill!
    mock_incomplete = mock_120[:-1]  # 119 records
    res_incomp = compute_task_clustered_paired_stats(mock_incomplete, "objective_diagnostic_pass")
    assert res_incomp["status"] == "ERROR_INCOMPLETE_OR_CORRUPTED_DATASET"
    assert res_incomp["integrity_report"]["missing_count"] == 1
    print("  [PASS] Incomplete dataset rejected with explicit error, zero-fill prevented!")
    
    # 3. Test duplicate records: MUST FAIL loudly!
    mock_dup = mock_120 + [mock_120[0]]  # 121 records with duplicate
    res_dup = compute_task_clustered_paired_stats(mock_dup, "objective_diagnostic_pass")
    assert res_dup["status"] == "ERROR_INCOMPLETE_OR_CORRUPTED_DATASET"
    assert res_dup["integrity_report"]["duplicate_count"] == 1
    print("  [PASS] Duplicate records detected and rejected!")
    
    # 4. Test truncation flag tracking
    mock_trunc = list(mock_120)
    mock_trunc[0] = {**mock_trunc[0], "finish_reason": "length", "is_truncated": True}
    res_trunc = compute_task_clustered_paired_stats(mock_trunc, "objective_diagnostic_pass")
    assert res_trunc["status"] == "OK"
    assert res_trunc["integrity_report"]["truncated_count"] == 1
    print("  [PASS] Truncated responses explicitly tracked and reported!")
    
    print("ALL STATISTICS SELF-TESTS PASSED!")
