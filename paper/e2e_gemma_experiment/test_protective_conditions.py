#!/usr/bin/env python3
"""
Comprehensive CPU Test Suite for Gemma 4 Evaluation Protective Conditions:
1. Two-Tier Diagnostic Evaluation (Tier 1 Objective Rubric vs Tier 2 Lexical Proxy)
2. Safe collect_only Mode (candidate code execution strictly disabled)
3. Pre-flight Static Syntax Compilation (static compile check without execution)
4. Strict Completeness Verification (15 x 4 x 2 = 120 cells; zero-fill prohibited)
5. Missing Cell & Duplicate Cell Rejection
6. Truncation Tracking (finish_reason == 'length')
7. Endpoint Health Abort on Unreachable Target
"""
import sys
import json
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from evaluator import evaluate_response, check_preflight_syntax, OBJECTIVE_DIAGNOSTIC_RUBRICS
from statistics import validate_dataset_integrity, compute_task_clustered_paired_stats
from run_e2e_inference import check_endpoint_health

def test_two_tier_evaluator():
    print("Running Test 1: Two-Tier Evaluator...")
    meta = {
        "id": "task_01_flask_blueprint_dot",
        "target_symbol": "Blueprint.__init__",
        "root_cause": "Blueprint names containing dots cause collision in nested blueprint endpoint resolution.",
        "expected_exception": "ValueError"
    }
    
    # Case A: Ideal response satisfying both Tier 1 and Tier 2
    resp_ideal = """DEFECT_LOCATION: Blueprint.__init__
ROOT_CAUSE: Blueprint names containing dots cause collision during nested blueprint route and endpoint resolution.
PROPOSED_CODE:
```python
class Blueprint:
    pass
```"""
    res_a = evaluate_response("task_01_flask_blueprint_dot", resp_ideal, meta, execute_candidate=False)
    assert res_a["objective_localization_pass"] is True
    assert res_a["objective_root_cause_pass"] is True
    assert res_a["objective_diagnostic_pass"] is True
    assert res_a["heuristic_lexical_localization_pass"] is True
    assert res_a["heuristic_lexical_root_cause_pass"] is True
    assert res_a["test_suite_pass"] is None
    assert res_a["execution_status"] == "COLLECT_ONLY_SKIPPED"
    
    # Case B: Response with vague root cause that games lexical proxy (mentions ValueError) but misses required concept sets
    resp_lexical_gaming = """DEFECT_LOCATION: Blueprint.__init__
ROOT_CAUSE: A ValueError occurred in the module when checking inputs.
PROPOSED_CODE:
```python
pass
```"""
    res_b = evaluate_response("task_01_flask_blueprint_dot", resp_lexical_gaming, meta, execute_candidate=False)
    assert res_b["objective_localization_pass"] is True
    assert res_b["objective_root_cause_pass"] is False  # Tier 1 correctly catches failure!
    assert res_b["objective_diagnostic_pass"] is False
    assert res_b["heuristic_lexical_root_cause_pass"] is True  # Tier 2 was gamed because it mentions ValueError!
    
    # Case C: Response with forbidden misdiagnosis (e.g. claiming circular import)
    resp_forbidden = """DEFECT_LOCATION: Blueprint.__init__
ROOT_CAUSE: A circular import occurred between blueprint and flask app with dots.
PROPOSED_CODE:
```python
pass
```"""
    res_c = evaluate_response("task_01_flask_blueprint_dot", resp_forbidden, meta, execute_candidate=False)
    assert res_c["objective_root_cause_pass"] is False
    assert res_c["objective_diagnostic_pass"] is False
    
    print("  [PASS] Test 1 passed: Two-Tier diagnostics accurately separate objective criteria from lexical proxy.")

def test_static_syntax_check():
    print("Running Test 2: Static Syntax Compilation Check...")
    # Valid syntax
    ok, err = check_preflight_syntax("def foo(x):\n    return x + 1")
    assert ok is True
    assert err == ""
    
    # Syntax error
    ok, err = check_preflight_syntax("def foo(x):\n    return x +")
    assert ok is False
    assert "SyntaxError" in err
    
    # Empty code
    ok, err = check_preflight_syntax("")
    assert ok is False
    assert "Empty" in err
    print("  [PASS] Test 2 passed: Pre-flight syntax compiles statically without execution.")

def test_strict_completeness_and_zero_fill_rejection():
    print("Running Test 3: Strict Dataset Completeness & Rejection of Zero-Fill...")
    # Build complete 120-cell dataset (15 tasks x 4 variants x 2 seeds)
    complete_dataset = []
    for i in range(1, 16):
        tid = f"task_{i:02d}"
        for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
            for seed in [42, 100]:
                complete_dataset.append({
                    "task_id": tid,
                    "variant": var,
                    "seed": seed,
                    "objective_diagnostic_pass": (var == "B_compressed" and i <= 10) or (var == "A_raw" and i <= 6),
                    "finish_reason": "stop",
                    "is_truncated": False
                })
    assert len(complete_dataset) == 120
    
    # Verify complete dataset succeeds
    rep = validate_dataset_integrity(complete_dataset)
    assert rep["is_complete"] is True
    assert rep["missing_count"] == 0
    assert rep["duplicate_count"] == 0
    
    stats = compute_task_clustered_paired_stats(complete_dataset, metric_key="objective_diagnostic_pass")
    assert stats["status"] == "OK"
    assert stats["paired_comparisons"]["delta_B_minus_A"]["mean_delta"] > 0
    
    # Test missing record: remove 1 record (119 records remaining)
    incomplete_dataset = complete_dataset[:-1]
    stats_incomp = compute_task_clustered_paired_stats(incomplete_dataset, metric_key="objective_diagnostic_pass")
    assert stats_incomp["status"] == "ERROR_INCOMPLETE_OR_CORRUPTED_DATASET"
    assert "Completeness check FAILED" in stats_incomp["error"]
    assert stats_incomp["integrity_report"]["missing_count"] == 1
    
    # Test duplicate record: duplicate 1 record (121 records)
    duplicate_dataset = complete_dataset + [complete_dataset[0]]
    stats_dup = compute_task_clustered_paired_stats(duplicate_dataset, metric_key="objective_diagnostic_pass")
    assert stats_dup["status"] == "ERROR_INCOMPLETE_OR_CORRUPTED_DATASET"
    assert stats_dup["integrity_report"]["duplicate_count"] == 1
    
    print("  [PASS] Test 3 passed: Incomplete datasets and duplicates are rejected; zero-fill is prohibited.")

def test_truncation_tracking():
    print("Running Test 4: Truncation Flag Tracking...")
    records = []
    for i in range(1, 16):
        tid = f"task_{i:02d}"
        for var in ["A_raw", "B_compressed", "C_tail35", "D_no_trace"]:
            for seed in [42, 100]:
                records.append({
                    "task_id": tid,
                    "variant": var,
                    "seed": seed,
                    "objective_diagnostic_pass": True,
                    "finish_reason": "length" if (tid == "task_01" and var == "A_raw") else "stop",
                    "is_truncated": (tid == "task_01" and var == "A_raw")
                })
    rep = validate_dataset_integrity(records)
    assert rep["is_complete"] is True
    assert rep["truncated_count"] == 2  # 2 seeds of task_01__A_raw
    assert "task_01__A_raw__seed42" in rep["truncated_keys"]
    assert "task_01__A_raw__seed100" in rep["truncated_keys"]
    print("  [PASS] Test 4 passed: Truncated responses are tracked and identified explicitly.")

def test_endpoint_health_abort():
    print("Running Test 5: Endpoint Health Check Abort...")
    # Passing an unreachable port should raise ConnectionError immediately
    try:
        check_endpoint_health("http://127.0.0.1:59999", "google/gemma-4-31B-it-qat-w4a16-ct")
        assert False, "Expected ConnectionError was not raised!"
    except ConnectionError as e:
        assert "Cannot reach inference endpoint" in str(e)
    print("  [PASS] Test 5 passed: Runner aborts immediately on unreachable endpoint.")

if __name__ == "__main__":
    test_two_tier_evaluator()
    test_static_syntax_check()
    test_strict_completeness_and_zero_fill_rejection()
    test_truncation_tracking()
    test_endpoint_health_abort()
    print("\nALL PROTECTIVE CONDITION TESTS PASSED (5/5)!")
