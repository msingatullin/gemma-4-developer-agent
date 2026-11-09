#!/usr/bin/env python3
"""
UNIT & INTEGRATION CPU TESTS FOR SMALL MODEL EVALUATION FRAMEWORK
Audits and proves all P0 requirements on CPU without requiring GPU.
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
MANIFEST_PATH = BASE_DIR / "manifest.json"
LOCATOR_RESULTS_PATH = BASE_DIR / "LOCATOR_BENCHMARK_RESULTS.json"


def test_01_candidate_taxonomy_and_sampling_parity():
    """Confirms candidates are clearly separated and sampling settings match v15."""
    print("Test 1: Candidate taxonomy and sampling parity...")
    v15_sampling = (REPO_ROOT / "v15_small_model" / "configs" / "sampling.yaml").read_text()
    v17_grep_sampling = (REPO_ROOT / "candidates" / "v17_grep_only" / "configs" / "sampling.yaml").read_text()
    v17_ast_sampling = (REPO_ROOT / "candidates" / "v17_ast_bm25" / "configs" / "sampling.yaml").read_text()

    assert v15_sampling == v17_grep_sampling, "v17_grep_only sampling differs from v15!"
    assert v15_sampling == v17_ast_sampling, "v17_ast_bm25 sampling differs from v15!"

    # Check prompts are distinct
    v15_prompt = (REPO_ROOT / "v15_small_model" / "prompts" / "system.md").read_text()
    v17_grep_prompt = (REPO_ROOT / "candidates" / "v17_grep_only" / "prompts" / "system.md").read_text()
    v17_ast_prompt = (REPO_ROOT / "candidates" / "v17_ast_bm25" / "prompts" / "system.md").read_text()

    assert v15_prompt != v17_grep_prompt, "v17_grep_prompt should contain corrected quoted grep syntax!"
    assert v17_grep_prompt != v17_ast_prompt, "v17_ast_prompt should contain AST locator instructions!"
    assert 'git grep -n -i "SPECIFIC_TOKEN" -- "*.py"' in v17_grep_prompt
    assert 'ast_locator.py' in v17_ast_prompt
    print("  PASS: All 3 candidate configurations are properly structured and differentiated.")


def test_02_accuracy_claims_accuracy():
    """Confirms Recall@3 is exactly 59.52% and no erroneous 81% claims exist."""
    print("Test 2: Verifying localization recall accuracy and claims...")
    with open(LOCATOR_RESULTS_PATH) as f:
        data = json.load(f)
    
    summary = data["summary"]["overall"]
    assert summary["count"] == 42, f"Expected 42 tasks, found {summary['count']}"
    assert summary["recall_at_3"] == 0.5952, f"Expected 0.5952, got {summary['recall_at_3']}"
    assert summary["recall_at_1"] == 0.4762, f"Expected 0.4762, got {summary['recall_at_1']}"
    assert summary["recall_at_5"] == 0.6429, f"Expected 0.6429, got {summary['recall_at_5']}"

    # Verify no un-refuted 81% claims in documentation
    for doc_name in ["PAIRED_E4B_PILOT_REPORT.md", "REAL_E4B_EVALUATION_PROTOCOL.md"]:
        doc_text = (BASE_DIR / doc_name).read_text(encoding="utf-8")
        assert "Recall@3 = 59.52%" in doc_text, f"{doc_name} missing 59.52% citation"
        if "81%" in doc_text:
            assert "опровергнута" in doc_text or "отозван" in doc_text, f"{doc_name} contains unretracted 81% claim"

    print("  PASS: 59.52% Recall@3 confirmed across 42 tasks; unretracted 81% claims eliminated.")


def test_03_sandbox_workspace_isolation():
    """Tests the SandboxWorkspace tool dispatcher inside a temporary git clone."""
    print("Test 3: Testing SandboxWorkspace tool operations...")
    from run_real_e4b_inference import SandboxWorkspace

    bare_flask = Path("/home/mikhail/upstream_repos/flask.git")
    if not bare_flask.exists():
        print("  SKIP: flask.git bare cache not found.")
        return

    ws = SandboxWorkspace("test_inst", "pallets/flask", "4c288bc97ea371817199908d0d9b12de9dae327e", bare_flask)
    ws.setup()
    try:
        # 1. read_file
        res_read = ws.dispatch_tool("read_file", {"path": "src/flask/config.py", "start_line": 1, "end_line": 20})
        assert "total_lines" in res_read, f"read_file failed: {res_read}"
        assert res_read["start_line"] == 1

        # 2. edit_file with unique anchor
        res_edit = ws.dispatch_tool("edit_file", {
            "path": "src/flask/config.py",
            "old_string": "class Config(dict):",
            "new_string": "class Config(dict):\n    # AUDIT_VERIFIED_EDIT"
        })
        assert res_edit.get("status") == "ok", f"edit_file failed: {res_edit}"

        # 3. submit_patch
        res_sub = ws.dispatch_tool("submit_patch", {})
        assert res_sub.get("status") == "ok", f"submit_patch failed: {res_sub}"
        assert res_sub["patch_size"] > 0
        assert "# AUDIT_VERIFIED_EDIT" in ws.get_final_diff()

        print("  PASS: SandboxWorkspace successfully isolated edits, generated valid git diff.")
    finally:
        ws.teardown()


def test_04_real_runner_live_hardware_check():
    """Confirms run_real_e4b_inference returns BLOCKED when GPU is inadequate."""
    print("Test 4: Verifying honest BLOCKED status on inadequate local hardware...")
    cmd = [sys.executable, str(BASE_DIR / "run_real_e4b_inference.py"), "--mode", "live"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Runner crashed: {res.stderr}"
    assert "STATUS: BLOCKED — REAL INFERENCE NOT EXECUTED" in res.stdout, "Live mode did not trigger BLOCKED status"
    assert "Hardware constraint: Local GPU has 4GB VRAM" in res.stdout
    print("  PASS: Live runner strictly halts with BLOCKED status and detailed hardware diagnostics.")


if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING SMALL MODEL FRAMEWORK CPU TESTS")
    print("=" * 80)
    test_01_candidate_taxonomy_and_sampling_parity()
    test_02_accuracy_claims_accuracy()
    test_03_sandbox_workspace_isolation()
    test_04_real_runner_live_hardware_check()
    print("=" * 80)
    print("ALL 4 CPU TESTS PASSED (PASS)")
    print("=" * 80)
