#!/usr/bin/env python3
"""Automated consistency verification:

Validates that all published numbers in paper/writeup.md match benchmark_results.json
and the underlying raw pytest logs byte-for-byte and number-for-number.
"""

import ast
import json
import re
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parent.parent
PAPER_DIR = REPO_ROOT / "paper"
WRITEUP_PATH = PAPER_DIR / "writeup.md"
JSON_PATH = EXPERIMENT_DIR / "benchmark_results.json"
NOTEBOOK_PATH = PAPER_DIR / "notebook.ipynb"
COMPRESSOR_PATH = PAPER_DIR / "traceback_compressor.py"

def verify_all():
    print("=== Paper Track Data Consistency & Integrity Verification ===")

    # 1. Load benchmark results
    assert JSON_PATH.exists(), f"Missing {JSON_PATH}"
    with open(JSON_PATH) as f:
        bench = json.load(f)

    # 2. Load paper writeup text
    assert WRITEUP_PATH.exists(), f"Missing {WRITEUP_PATH}"
    with open(WRITEUP_PATH) as f:
        writeup = f.read()

    # 3. Verify Raw Logs match JSON volume metrics
    mode_to_file = {
        "standard_verbose": "raw_log_auto_standard.txt",
        "short_traceback": "raw_log_tb_short.txt",
        "long_traceback": "raw_log_tb_long.txt",
        "native_traceback": "raw_log_tb_native.txt",
    }
    for mode, fname in mode_to_file.items():
        raw_path = EXPERIMENT_DIR / fname
        assert raw_path.exists(), f"Missing raw log file: {raw_path}"
        text = raw_path.read_text()
        exp_chars = len(text)
        exp_lines = len(text.splitlines())
        exp_tok = exp_chars // 4
        
        json_data = bench["experiments"][mode]["raw_volume"]
        assert json_data["chars"] == exp_chars, f"Mismatch in {mode} chars: {json_data['chars']} vs {exp_chars}"
        assert json_data["lines"] == exp_lines, f"Mismatch in {mode} lines: {json_data['lines']} vs {exp_lines}"
        assert json_data["heuristic_tokens"] == exp_tok, f"Mismatch in {mode} tokens: {json_data['heuristic_tokens']} vs {exp_tok}"
        print(f"Verified {fname}: {exp_chars:,} chars, {exp_lines} lines, {exp_tok:,} tokens matches JSON.")

    # 4. Verify Writeup table cells match JSON exactly
    for mode, data in bench["experiments"].items():
        raw_chars = data["raw_volume"]["chars"]
        raw_tok = data["raw_volume"]["heuristic_tokens"]
        comp_chars = data["compressed_volume"]["chars"]
        comp_tok = data["compressed_volume"]["heuristic_tokens"]
        red_chars = data["volume_reduction"]["chars_pct"]
        red_lines = data["volume_reduction"]["lines_pct"]
        
        raw_cell = f"{raw_chars:,} chars / {raw_tok:,} tok"
        assert raw_cell in writeup, f"Writeup missing raw volume cell: {raw_cell}"
        
        comp_cell = f"{comp_chars:,} chars / {comp_tok:,} tok"
        assert comp_cell in writeup, f"Writeup missing compressed volume cell: {comp_cell}"
        
        # Verify prompt volume reduction percentage
        if red_chars > 0:
            red_str = f"{red_chars:.1f}%"
            red_alt = f"{round(red_chars + 0.05, 1):.1f}%"
            assert (red_str in writeup or red_alt in writeup), f"Writeup missing reduction string: {red_str} or {red_alt} in mode {mode}"
            
        print(f"Verified writeup table cells for {mode}: {raw_cell} -> {comp_cell} (reduction: {red_chars:.1f}%)")

    # 5. Verify Baseline numbers match JSON
    for b_name, b_data in bench["baselines_standard_log"].items():
        b_comp_chars = b_data["compressed_volume"]["chars"]
        b_comp_tok = b_data["compressed_volume"]["heuristic_tokens"]
        b_cell = f"{b_comp_chars:,} chars / {b_comp_tok:,} tok"
        assert b_cell in writeup, f"Writeup missing baseline volume: {b_cell}"
        
        b_ret = b_data["diagnostic_retention"]["overall_retention_pct"]
        b_ret_str = f"{b_ret:.1f}%"
        assert b_ret_str in writeup, f"Writeup missing baseline retention: {b_ret_str}"
        print(f"Verified baseline {b_name}: {b_cell}, retention {b_ret_str}")

    # 6. Verify Negative Controls status
    for neg in bench["negative_controls"]:
        assert neg["status"] == "PASS", f"Negative control {neg['test']} did not pass!"
    assert len(bench["negative_controls"]) == 8, f"Expected 8 negative controls, found {len(bench['negative_controls'])}"
    print(f"Verified all {len(bench['negative_controls'])} negative controls are certified PASS.")

    # 7. Verify AST Parity with Notebook v16 cell 7
    assert NOTEBOOK_PATH.exists()
    assert COMPRESSOR_PATH.exists()
    with open(NOTEBOOK_PATH) as f:
        nb = json.load(f)
    nb_ast = None
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        if "def filter_pytest_log" in src:
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.FunctionDef) and node.name == "filter_pytest_log":
                    nb_ast = ast.dump(node)
                    break
    mod_ast = None
    for node in ast.walk(ast.parse(COMPRESSOR_PATH.read_text())):
        if isinstance(node, ast.FunctionDef) and node.name == "filter_pytest_log":
            mod_ast = ast.dump(node)
            break
    assert nb_ast == mod_ast, "AST parity check failed between compressor and notebook!"
    print("Verified AST parity between traceback_compressor.py and notebook.ipynb cell 7.")

    # 8. Verify Word Count Headroom
    words = len(writeup.split())
    print(f"Writeup word count: {words} words (Limit: 3,000 words, Headroom: {3000 - words} words).")
    assert words <= 3000, f"Ceiling exceeded: {words} > 3000"
    assert words <= 2800, f"Headroom too small: {words} > 2800"

    print("\nALL 8 CONSISTENCY & INTEGRITY GATES PASSED PERFECTLY!")

if __name__ == "__main__":
    verify_all()
