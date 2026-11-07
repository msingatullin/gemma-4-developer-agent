#!/usr/bin/env python3
"""Empirical traceback compression benchmark on unmocked pytest execution logs.

Uses the canonical filter_pytest_log implementation from paper/traceback_compressor.py
(verified identical to paper/notebook.ipynb cell 7).
Measures:
1. Exact character, line, and heuristic token (len // 4) volume reduction.
2. Category-by-category diagnostic retention across 7 failed tests, section headers,
   source assertion sites, 32 multiline diff frames, and distinct exception causes.
3. CPU processing latency across 50 iterations plus 3 independent verification repeats.
4. Fail-closed negative control tests verifying that diagnostic corruptions cause
   oracle rejection with AssertionError.
"""

import re
import ast
import json
import time
import hashlib
from pathlib import Path
from collections import Counter

# Portable path discovery
EXPERIMENT_DIR = Path(__file__).resolve().parent
PAPER_DIR = EXPERIMENT_DIR.parent
REPO_ROOT = PAPER_DIR.parent
COMPRESSOR_FILE = PAPER_DIR / "traceback_compressor.py"
NOTEBOOK_FILE = PAPER_DIR / "notebook.ipynb"

# Import canonical implementation
import sys
sys.path.insert(0, str(PAPER_DIR))
from traceback_compressor import filter_pytest_log

def verify_canonical_code_parity():
    """Verify that filter_pytest_log in traceback_compressor.py matches notebook.ipynb cell 7."""
    assert NOTEBOOK_FILE.exists(), f"Notebook file not found at {NOTEBOOK_FILE}"
    assert COMPRESSOR_FILE.exists(), f"Compressor file not found at {COMPRESSOR_FILE}"
    
    with open(NOTEBOOK_FILE, "r") as f:
        nb = json.load(f)
        
    nb_dump = None
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        if "def filter_pytest_log" in src:
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "filter_pytest_log":
                    nb_dump = ast.dump(node)
                    break
                    
    with open(COMPRESSOR_FILE, "r") as f:
        tree_mod = ast.parse(f.read())
        
    mod_dump = None
    for node in ast.walk(tree_mod):
        if isinstance(node, ast.FunctionDef) and node.name == "filter_pytest_log":
            mod_dump = ast.dump(node)
            break
            
    assert nb_dump is not None, "filter_pytest_log not found in notebook.ipynb"
    assert mod_dump is not None, "filter_pytest_log not found in traceback_compressor.py"
    assert nb_dump == mod_dump, "AST parity check failed: traceback_compressor.py differs from notebook.ipynb!"
    
    # Compute SHA256 of canonical compressor file
    with open(COMPRESSOR_FILE, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    return sha256

# Baseline 1: Naive tail-capping
def naive_tail_cap(text: str, n_lines: int = 35) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n_lines:])

# Baseline 2: Naive regex extracting only lines beginning with E
def naive_e_lines_only(text: str) -> str:
    lines = text.splitlines()
    filtered = [l for l in lines if l.strip().startswith("E ") or l.strip().startswith("E\t")]
    return "\n".join(filtered)

# Ground-truth diagnostic categories
def build_ground_truth():
    headers = [
        "__________________________ test_single_verbose_stdout __________________________",
        "________________________ test_multiline_assertion_diff _________________________",
        "_____ test_parametrized_cases[alpha_case-100-ALPHA_PARAMETRIZED_CAUSE_KEY] _____",
        "_____ test_parametrized_cases[gamma_case-300-GAMMA_PARAMETRIZED_CAUSE_KEY] _____",
        "__________________________ test_independent_cause_one __________________________",
        "__________________________ test_independent_cause_two __________________________",
        "_________________________ test_independent_cause_three _________________________"
    ]
    summaries = [
        "FAILED test_real_fixtures.py::test_single_verbose_stdout",
        "FAILED test_real_fixtures.py::test_multiline_assertion_diff",
        "FAILED test_real_fixtures.py::test_parametrized_cases[alpha_case-100-ALPHA_PARAMETRIZED_CAUSE_KEY]",
        "FAILED test_real_fixtures.py::test_parametrized_cases[gamma_case-300-GAMMA_PARAMETRIZED_CAUSE_KEY]",
        "FAILED test_real_fixtures.py::test_independent_cause_one",
        "FAILED test_real_fixtures.py::test_independent_cause_two",
        "FAILED test_real_fixtures.py::test_independent_cause_three"
    ]
    source_sites = [
        '>       assert 42 == 99, "EXACT_DIAGNOSTIC_ROOT_CAUSE: single_failure_target_marker"',
        r'>       assert False, "\n".join(diagnostics)',
        '>           assert False, f"FAILED_CASE: {audit_marker}"',
        '>           raise ValueError(f"CRITICAL_EXCEPTION: {audit_marker}")',
        '>       assert False, "INDEPENDENT_CAUSE_ONE_ASSERTION_MARKER"',
        '>       raise ValueError("INDEPENDENT_CAUSE_TWO_VALUE_ERROR_MARKER")',
        '>       val = d["missing_route_target_INDEPENDENT_CAUSE_THREE_MARKER"]'
    ]
    multiline_frames = [f"diagnostic_frame_detail_{i:02d}: payload_state_verification_active" for i in range(32)]
    causes = [
        "EXACT_DIAGNOSTIC_ROOT_CAUSE: single_failure_target_marker",
        "MULTILINE_HEADER_MARKER",
        "ALPHA_PARAMETRIZED_CAUSE_KEY",
        "GAMMA_PARAMETRIZED_CAUSE_KEY",
        "INDEPENDENT_CAUSE_ONE_ASSERTION_MARKER",
        "INDEPENDENT_CAUSE_TWO_VALUE_ERROR_MARKER",
        "missing_route_target_INDEPENDENT_CAUSE_THREE_MARKER"
    ]
    parametrized_ids = [
        "alpha_case-100-ALPHA_PARAMETRIZED_CAUSE_KEY",
        "gamma_case-300-GAMMA_PARAMETRIZED_CAUSE_KEY"
    ]
    return {
        "headers": headers,
        "summaries": summaries,
        "source_sites": source_sites,
        "multiline_frames": multiline_frames,
        "causes": causes,
        "parametrized_ids": parametrized_ids,
    }

GROUND_TRUTH = build_ground_truth()

def evaluate_diagnostic_categories(compressed_text: str, raw_text: str, ground_truth: dict) -> dict:
    """Evaluate diagnostic retention broken down by specific semantic category,
    measured strictly against elements that actually exist in raw_text.
    """
    def match_rate(items):
        items_in_raw = [item for item in items if item in raw_text]
        if not items_in_raw:
            return {"retained": 0, "total": 0, "retention_pct": 100.0, "status": "NOT_PRESENT_IN_FORMAT"}
        retained = sum(1 for item in items_in_raw if item in compressed_text)
        pct = (retained / len(items_in_raw) * 100.0) if len(items_in_raw) > 0 else 0.0
        return {"retained": retained, "total": len(items_in_raw), "retention_pct": round(pct, 2)}
        
    cats = {
        "section_headers": match_rate(ground_truth["headers"]),
        "failure_summaries": match_rate(ground_truth["summaries"]),
        "source_assertion_sites": match_rate(ground_truth["source_sites"]),
        "multiline_assertion_frames": match_rate(ground_truth["multiline_frames"]),
        "root_cause_exceptions": match_rate(ground_truth["causes"]),
        "parametrized_node_ids": match_rate(ground_truth["parametrized_ids"]),
    }
    
    total_retained = sum(c["retained"] for c in cats.values())
    total_items = sum(c["total"] for c in cats.values())
    overall_pct = (total_retained / total_items * 100.0) if total_items > 0 else 0.0
    
    return {
        "categories": cats,
        "total_retained": total_retained,
        "total_items": total_items,
        "overall_retention_pct": round(overall_pct, 2)
    }

CAT_KEY_MAP = {
    "section_headers": "headers",
    "failure_summaries": "summaries",
    "source_assertion_sites": "source_sites",
    "multiline_assertion_frames": "multiline_frames",
    "root_cause_exceptions": "causes",
    "parametrized_node_ids": "parametrized_ids",
}

def verify_diagnostic_integrity(compressed_text: str, raw_text: str, ground_truth: dict) -> None:
    """Verification Oracle: Validates that a compressed traceback preserves the complete
    diagnostic ground-truth for all elements present in raw_text.
    Raises AssertionError if ANY category loses required elements.
    """
    eval_res = evaluate_diagnostic_categories(compressed_text, raw_text, ground_truth)
    cats = eval_res["categories"]
    
    for cat_name, cat_data in cats.items():
        if cat_data["retained"] < cat_data["total"]:
            items_in_raw = [x for x in ground_truth[CAT_KEY_MAP[cat_name]] if x in raw_text]
            missing = [x for x in items_in_raw if x not in compressed_text]
            raise AssertionError(f"Integrity breach: dropped {len(missing)} {cat_name}: {missing}")

def run_timing_benchmark(func, text: str, iterations: int = 50, repeats: int = 3):
    """Run timing benchmark with multiple repeats and iterations."""
    repeat_results = []
    for r in range(repeats):
        # Warmup
        for _ in range(5):
            func(text)
        t0 = time.perf_counter()
        for _ in range(iterations):
            func(text)
        t1 = time.perf_counter()
        avg_ms = ((t1 - t0) / iterations) * 1000.0
        repeat_results.append(avg_ms)
        
    mean_ms = sum(repeat_results) / len(repeat_results)
    variance = sum((x - mean_ms) ** 2 for x in repeat_results) / len(repeat_results)
    std_ms = variance ** 0.5
    
    return {
        "mean_latency_ms": round(mean_ms, 3),
        "std_latency_ms": round(std_ms, 3),
        "min_latency_ms": round(min(repeat_results), 3),
        "max_latency_ms": round(max(repeat_results), 3),
        "repeats_ms": [round(x, 3) for x in repeat_results]
    }

def main():
    print("=== Empirical Traceback Compression Benchmark (Canonical Suite) ===")
    
    # 1. Verify code parity with notebook v16
    compressor_hash = verify_canonical_code_parity()
    print(f"Verified AST parity with paper/notebook.ipynb cell 7.")
    print(f"Canonical compressor SHA256: {compressor_hash}")

    log_files = {
        "standard_verbose": EXPERIMENT_DIR / "raw_log_auto_standard.txt",
        "short_traceback": EXPERIMENT_DIR / "raw_log_tb_short.txt",
        "long_traceback": EXPERIMENT_DIR / "raw_log_tb_long.txt",
        "native_traceback": EXPERIMENT_DIR / "raw_log_tb_native.txt",
    }

    # Verify all raw logs exist
    for name, path in log_files.items():
        assert path.exists(), f"Raw log {path} does not exist. Run generate_real_pytest_logs.py first."

    raw_logs = {name: path.read_text() for name, path in log_files.items()}
    
    results = {
        "meta": {
            "compressor_file": str(COMPRESSOR_FILE.relative_to(REPO_ROOT)),
            "compressor_sha256": compressor_hash,
            "pytest_format_modes": list(log_files.keys()),
            "iterations_per_run": 50,
            "independent_repeats": 3,
        },
        "experiments": {},
        "baselines_standard_log": {},
        "negative_controls": []
    }

    print("\n--- Evaluating 4 Pytest Log Formats with Canonical Suite ---")
    for mode, raw_text in raw_logs.items():
        compressed = filter_pytest_log(raw_text)
        
        raw_chars = len(raw_text)
        raw_lines = len(raw_text.splitlines())
        raw_est_tokens = raw_chars // 4
        
        comp_chars = len(compressed)
        comp_lines = len(compressed.splitlines())
        comp_est_tokens = comp_chars // 4
        
        reduction_chars_pct = round((1.0 - (comp_chars / raw_chars)) * 100.0, 2)
        reduction_lines_pct = round((1.0 - (comp_lines / raw_lines)) * 100.0, 2)
        
        timing = run_timing_benchmark(filter_pytest_log, raw_text, iterations=50, repeats=3)
        cat_eval = evaluate_diagnostic_categories(compressed, raw_text, GROUND_TRUTH)
        
        # Verify oracle on our output for non-native logs
        verify_diagnostic_integrity(compressed, raw_text, GROUND_TRUTH)
        
        results["experiments"][mode] = {
            "raw_volume": {
                "chars": raw_chars,
                "lines": raw_lines,
                "heuristic_tokens": raw_est_tokens
            },
            "compressed_volume": {
                "chars": comp_chars,
                "lines": comp_lines,
                "heuristic_tokens": comp_est_tokens
            },
            "volume_reduction": {
                "chars_pct": reduction_chars_pct,
                "lines_pct": reduction_lines_pct
            },
            "timing_ms": timing,
            "diagnostic_retention": cat_eval
        }
        
        print(f"Mode: {mode}")
        print(f"  Volume: {raw_chars} chars ({raw_est_tokens} tok) -> {comp_chars} chars ({comp_est_tokens} tok) [{reduction_chars_pct}% char reduction]")
        print(f"  Lines:  {raw_lines} -> {comp_lines} [{reduction_lines_pct}% line reduction]")
        print(f"  Timing: {timing['mean_latency_ms']} ms ± {timing['std_latency_ms']} ms")
        print(f"  Retention: {cat_eval['total_retained']}/{cat_eval['total_items']} items ({cat_eval['overall_retention_pct']}%)")
        print(f"    - Headers: {cat_eval['categories']['section_headers']['retained']}/{cat_eval['categories']['section_headers']['total']}")
        print(f"    - Summaries: {cat_eval['categories']['failure_summaries']['retained']}/{cat_eval['categories']['failure_summaries']['total']}")
        print(f"    - Source Sites: {cat_eval['categories']['source_assertion_sites']['retained']}/{cat_eval['categories']['source_assertion_sites']['total']}")
        print(f"    - Multiline Frames: {cat_eval['categories']['multiline_assertion_frames']['retained']}/{cat_eval['categories']['multiline_assertion_frames']['total']}")
        print(f"    - Root Causes: {cat_eval['categories']['root_cause_exceptions']['retained']}/{cat_eval['categories']['root_cause_exceptions']['total']}")

    # Evaluate Baselines on Standard Verbose Log
    print("\n--- Evaluating Baselines on Standard Verbose Pytest Log ---")
    std_raw = raw_logs["standard_verbose"]
    
    baselines = {
        "naive_tail_cap_35": naive_tail_cap(std_raw, 35),
        "naive_e_lines_only": naive_e_lines_only(std_raw),
    }
    
    for b_name, b_text in baselines.items():
        b_fn = (lambda t: naive_tail_cap(t, 35)) if "tail" in b_name else naive_e_lines_only
        timing = run_timing_benchmark(b_fn, std_raw, iterations=50, repeats=3)
        cat_eval = evaluate_diagnostic_categories(b_text, std_raw, GROUND_TRUTH)
        
        chars = len(b_text)
        lines = len(b_text.splitlines())
        tokens = chars // 4
        red_chars = round((1.0 - (chars / len(std_raw))) * 100.0, 2)
        
        results["baselines_standard_log"][b_name] = {
            "compressed_volume": {"chars": chars, "lines": lines, "heuristic_tokens": tokens},
            "volume_reduction_chars_pct": red_chars,
            "timing_ms": timing,
            "diagnostic_retention": cat_eval
        }
        print(f"Baseline: {b_name}")
        print(f"  Volume: {chars} chars ({tokens} tok) [{red_chars}% reduction]")
        print(f"  Timing: {timing['mean_latency_ms']} ms ± {timing['std_latency_ms']} ms")
        print(f"  Retention: {cat_eval['total_retained']}/{cat_eval['total_items']} items ({cat_eval['overall_retention_pct']}%)")
        print(f"    - Headers: {cat_eval['categories']['section_headers']['retained']}/{cat_eval['categories']['section_headers']['total']}")
        print(f"    - Summaries: {cat_eval['categories']['failure_summaries']['retained']}/{cat_eval['categories']['failure_summaries']['total']}")
        print(f"    - Source Sites: {cat_eval['categories']['source_assertion_sites']['retained']}/{cat_eval['categories']['source_assertion_sites']['total']}")
        print(f"    - Multiline Frames: {cat_eval['categories']['multiline_assertion_frames']['retained']}/{cat_eval['categories']['multiline_assertion_frames']['total']}")
        print(f"    - Root Causes: {cat_eval['categories']['root_cause_exceptions']['retained']}/{cat_eval['categories']['root_cause_exceptions']['total']}")

    # 4. Fail-Closed Negative Controls
    print("\n--- Running Fail-Closed Negative Controls ---")
    valid_compressed = filter_pytest_log(std_raw)
    
    # Negative Test 1: Dropping a Section Header causes Oracle Rejection
    neg1_text = valid_compressed.replace(
        "__________________________ test_single_verbose_stdout __________________________",
        ""
    )
    neg1_caught = False
    try:
        verify_diagnostic_integrity(neg1_text, std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg1_caught = True
        assert "Integrity breach: dropped 1 section_headers" in str(e)
    assert neg1_caught, "Fail-closed check failed: Oracle accepted log missing section header!"
    results["negative_controls"].append({
        "test": "neg1_drop_section_header",
        "description": "Mutant with dropped failure section header must trigger AssertionError in oracle",
        "caught": neg1_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 1 (dropped section header caught by oracle with AssertionError)")

    # Negative Test 2: Dropping a Failure Summary Line causes Oracle Rejection
    neg2_text = valid_compressed.replace(
        "FAILED test_real_fixtures.py::test_single_verbose_stdout",
        ""
    )
    neg2_caught = False
    try:
        verify_diagnostic_integrity(neg2_text, std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg2_caught = True
        assert "Integrity breach: dropped 1 failure_summaries" in str(e)
    assert neg2_caught, "Fail-closed check failed: Oracle accepted log missing failure summary!"
    results["negative_controls"].append({
        "test": "neg2_drop_failure_summary",
        "description": "Mutant with dropped failure summary line must trigger AssertionError in oracle",
        "caught": neg2_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 2 (dropped summary line caught by oracle with AssertionError)")

    # Negative Test 3: Dropping a Source Code Assertion Site causes Oracle Rejection
    neg3_text = valid_compressed.replace(
        '>       assert 42 == 99, "EXACT_DIAGNOSTIC_ROOT_CAUSE: single_failure_target_marker"',
        ""
    )
    neg3_caught = False
    try:
        verify_diagnostic_integrity(neg3_text, std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg3_caught = True
        assert "Integrity breach: dropped 1 source_assertion_sites" in str(e)
    assert neg3_caught, "Fail-closed check failed: Oracle accepted log missing source assertion site!"
    results["negative_controls"].append({
        "test": "neg3_drop_source_assertion_site",
        "description": "Mutant with dropped source code assertion line must trigger AssertionError in oracle",
        "caught": neg3_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 3 (dropped source assertion site caught by oracle with AssertionError)")

    # Negative Test 4: Corrupting/Dropping Multiline Detail Frame causes Oracle Rejection
    neg4_text = valid_compressed.replace(
        "diagnostic_frame_detail_15: payload_state_verification_active",
        ""
    )
    neg4_caught = False
    try:
        verify_diagnostic_integrity(neg4_text, std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg4_caught = True
        assert "Integrity breach: dropped 1 multiline_assertion_frames" in str(e)
    assert neg4_caught, "Fail-closed check failed: Oracle accepted log with missing multiline frame!"
    results["negative_controls"].append({
        "test": "neg4_drop_multiline_diff_frame",
        "description": "Mutant with dropped multiline detail frame must trigger AssertionError in oracle",
        "caught": neg4_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 4 (corrupted multiline frame caught by oracle with AssertionError)")

    # Negative Test 5: Dropping Root Cause Exception causes Oracle Rejection
    neg5_text = valid_compressed.replace(
        "missing_route_target_INDEPENDENT_CAUSE_THREE_MARKER",
        "corrupted_key_placeholder"
    )
    neg5_caught = False
    try:
        verify_diagnostic_integrity(neg5_text, std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg5_caught = True
        assert "Integrity breach" in str(e)
    assert neg5_caught, "Fail-closed check failed: Oracle accepted log with corrupted exception cause!"
    results["negative_controls"].append({
        "test": "neg5_corrupted_root_cause_exception",
        "description": "Mutant with corrupted root cause exception marker must trigger AssertionError in oracle",
        "caught": neg5_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 5 (corrupted root cause caught by oracle with AssertionError)")

    # Negative Test 6: Naive Tail-Cap output fails Oracle Rejection
    neg6_caught = False
    try:
        verify_diagnostic_integrity(baselines["naive_tail_cap_35"], std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg6_caught = True
        assert "Integrity breach" in str(e)
    assert neg6_caught, "Fail-closed check failed: Oracle accepted naive tail-cap baseline!"
    results["negative_controls"].append({
        "test": "neg6_naive_tail_cap_oracle_rejection",
        "description": "Naive tail-cap output must be rejected by integrity oracle due to dropped headers/frames",
        "caught": neg6_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 6 (naive tail-cap baseline rejected by oracle with AssertionError)")

    # Negative Test 7: Naive E-lines output fails Oracle Rejection
    neg7_caught = False
    try:
        verify_diagnostic_integrity(baselines["naive_e_lines_only"], std_raw, GROUND_TRUTH)
    except AssertionError as e:
        neg7_caught = True
        assert "Integrity breach" in str(e)
    assert neg7_caught, "Fail-closed check failed: Oracle accepted naive e-lines baseline!"
    results["negative_controls"].append({
        "test": "neg7_naive_e_lines_oracle_rejection",
        "description": "Naive e-lines output must be rejected by integrity oracle due to dropped headers/code sites",
        "caught": neg7_caught,
        "status": "PASS"
    })
    print("PASS: Negative Control 7 (naive e-lines baseline rejected by oracle with AssertionError)")

    # Negative Test 8: Fail-Closed Internal Fallback Gate (Evidence & Header Loss Rejection)
    # Step 1: Construct adversarial log where diagnostic error is inside captured stdout buffer
    adversarial_evidence_log = """=== FAILURES ===
______ test_worker_crash ______
    def test_worker_crash():
>       assert False, "PRIMARY_FAILURE_ROOT_CAUSE"
E       AssertionError: PRIMARY_FAILURE_ROOT_CAUSE
----------------------------- Captured stdout call -----------------------------
[WORKER_STDOUT] Initializing background task worker pool...
E       RuntimeError: UNEXPECTED_SUBPROCESS_CRASH_IN_CAPTURED_STDOUT
=== short test summary info ===
FAILED test_worker.py::test_worker_crash - AssertionError: PRIMARY_FAILURE_ROOT_CAUSE
"""
    # Verify Step 1: Demonstrate that unprotected block compression proposes a string that loses this line
    target_evidence_line = "E       RuntimeError: UNEXPECTED_SUBPROCESS_CRASH_IN_CAPTURED_STDOUT"
    # Run the exact block extractor logic to obtain the lossy proposed candidate
    adv_lines = adversarial_evidence_log.splitlines()
    adv_summary = [l for l in adv_lines if re.match(r'^(FAILED|ERROR)\s+', l.strip())]
    adv_blocks, adv_curr = [], []
    in_zone, in_cap = False, False
    for l in adv_lines:
        s = l.strip()
        if re.search(r'^=+\s*(FAILURES|ERRORS)\s*=+', s): in_zone = True; continue
        if not in_zone: continue
        if re.search(r'^=+\s*short test summary info\s*=+', s):
            if adv_curr: adv_blocks.append(adv_curr); adv_curr = []
            break
        if re.match(r'^_{3,}\s*.*?\s*_{3,}$', s):
            if adv_curr: adv_blocks.append(adv_curr); adv_curr = []
            adv_curr.append(l); in_cap = False; continue
        if re.search(r'^-+\s*Captured (stdout|stderr)\s*', s):
            in_cap = True; adv_curr.append('    --- [Captured output collapsed] ---'); continue
        if in_cap:
            if re.match(r'^(=|_|-){3,}', s) or re.match(r'^(FAILED|ERROR)\s+', s): in_cap = False
            else: continue
        if not re.match(r'^[=_-]{10,}$', s): adv_curr.append(l)
    if adv_curr: adv_blocks.append(adv_curr)
    
    cand_header = adv_blocks[0][:1]
    cand_body = [l for l in adv_blocks[0][1:] if l.strip().startswith(('>', 'E ', 'E\t')) and 'Captured output' not in l]
    cand_comp = cand_header + cand_body + ['    --- [Captured output collapsed] ---']
    proposed_lossy = '\n'.join(['\n'.join(cand_comp)] + adv_summary)
    
    # 1. Confirm that the proposed compression dropped the critical error line
    assert target_evidence_line not in proposed_lossy, "Test precondition failed: proposed candidate did not drop line!"
    
    # 2. Confirm that the Counter-based evidence guard flags the loss
    def count_diag(val):
        return Counter(
            line.strip() for line in val.splitlines()
            if (line.lstrip().startswith(('E ', 'E\t', '> ', 'FAILED ', 'ERROR '))
                or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):', line.strip()))
        )
    orig_diag = count_diag(adversarial_evidence_log)
    prop_diag = count_diag(proposed_lossy)
    assert orig_diag[target_evidence_line] == 1
    assert prop_diag[target_evidence_line] == 0
    assert any(prop_diag[l] < c for l, c in orig_diag.items()), "Counter guard did not trip on proposed lossy text!"
    
    # 3. Confirm that filter_pytest_log activates fallback and returns the original log byte-for-byte
    adv_res = filter_pytest_log(adversarial_evidence_log)
    assert adv_res == adversarial_evidence_log, "Fallback failure: returned string differs from original log!"
    assert adv_res.encode("utf-8") == adversarial_evidence_log.encode("utf-8"), "Fallback failure: byte-for-byte mismatch!"
    assert len(adv_res) == len(adversarial_evidence_log), "Fallback failure: length mismatch!"
    assert target_evidence_line in adv_res, "Fallback failure: target evidence line missing in returned log!"
    
    # Also verify positive control: when captured stdout contains no diagnostic errors, compression succeeds
    clean_log = adversarial_evidence_log.replace(target_evidence_line, "[WORKER_STDOUT] Task completed cleanly")
    clean_res = filter_pytest_log(clean_log)
    assert clean_res != clean_log, "Clean control log should have compressed successfully!"
    assert len(clean_res) < len(clean_log), "Clean compressed log must be smaller than raw log!"
    assert "--- [Captured output collapsed] ---" in clean_res
    
    # Step 4: Adversarial header loss fallback test
    adversarial_header_log = """platform linux -- Python 3.12
________________________ test_pre_failure_header ________________________
=== FAILURES ===
______ test_case ______
>       assert False
E       AssertionError: primary_cause
=== short test summary info ===
FAILED test.py::test_case
"""
    adv_header_res = filter_pytest_log(adversarial_header_log)
    assert adv_header_res == adversarial_header_log, "Header fallback failed: output differs from raw input!"
    assert adv_header_res.encode("utf-8") == adversarial_header_log.encode("utf-8")
    
    results["negative_controls"].append({
        "test": "neg8_internal_fallback_gate_validation",
        "description": "filter_pytest_log Counter guard rejects proposed lossy compression and returns raw log byte-for-byte (verified for dropped evidence lines and headers)",
        "evidence_loss_detected": True,
        "byte_for_byte_fallback_verified": True,
        "status": "PASS"
    })
    print("PASS: Negative Control 8 (internal Counter fallback gate verified with byte-for-byte raw log return)")

    # Save results to JSON
    json_path = EXPERIMENT_DIR / "benchmark_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved structured benchmark results to {json_path}")

if __name__ == "__main__":
    main()
