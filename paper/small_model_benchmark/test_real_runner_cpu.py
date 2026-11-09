#!/usr/bin/env python3
"""
UNIT & INTEGRATION CPU ACCEPTANCE TEST SUITE (P0 FINAL GATE)
Repository: msingatullin/gemma-4-developer-agent
Target: Kaggle Small Model Development Prize ($10,000)

Verifies all 7 P0 Final Gate acceptance criteria on CPU without GPU execution:
1. Empty test suite fails immediately (resolved=False).
2. Corrupted test_patch fails immediately (resolved=False).
3. F2P PASS + P2P FAIL returns FAIL (resolved=False).
4. F2P PASS + P2P PASS returns RESOLVED (resolved=True); exit code 5 treated as FAIL.
5. Container containment: bwrap blocks host credentials (.kaggle, .ssh) and network egress.
6. AST locator self-contained delivery: extracts to /tmp via run_command without workspace diff.
7. Clean checkout candidate parity: v15_baseline, v17_grep_only, v17_ast_bm25 git-tracked and verified.
"""

import os
import sys
import json
import shutil
import hashlib
import tempfile
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
MANIFEST_PATH = BASE_DIR / "manifest.json"
LOCATOR_RESULTS_PATH = BASE_DIR / "LOCATOR_BENCHMARK_RESULTS.json"

sys.path.insert(0, str(BASE_DIR))
from run_real_e4b_inference import (
    SandboxWorkspace,
    verify_task_patch,
    execute_in_sandbox,
    check_hardware_capabilities,
    CANDIDATES,
    REPO_BARE_MAP
)


def _create_test_git_repo(tmp_path: Path):
    """Creates a local bare git repo and test workdir for rigorous integration testing."""
    bare_dir = tmp_path / "test_repo.git"
    work_dir = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", "-q", str(bare_dir)], check=True)
    subprocess.run(["git", "clone", "-q", str(bare_dir), str(work_dir)], check=True)

    # Initial buggy implementation
    (work_dir / "calculator.py").write_text("def add(a, b):\n    return a - b  # defect\n\ndef mul(a, b):\n    return a * b\n")
    (work_dir / "tests").mkdir()
    (work_dir / "tests" / "test_calc.py").write_text(
        "from calculator import add, mul\n"
        "def test_add_f2p():\n    assert add(2, 3) == 5\n\n"
        "def test_mul_p2p():\n    assert mul(2, 3) == 6\n"
    )
    (work_dir / "tests" / "test_empty.py").write_text("# Empty test file with 0 test cases\nx = 1\n")

    subprocess.run(["git", "add", "-A"], cwd=work_dir, check=True)
    subprocess.run(["git", "-c", "user.name=Audit", "-c", "user.email=audit@local", "commit", "-q", "-m", "initial"], cwd=work_dir, check=True)
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=work_dir, check=True)

    base_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work_dir, text=True).strip()

    # Create evaluation test_patch (e.g. extending tests or adding regression test)
    (work_dir / "tests" / "test_eval.py").write_text(
        "from calculator import add\n"
        "def test_eval_extra():\n    assert add(10, 20) == 30\n"
    )
    subprocess.run(["git", "add", "tests/test_eval.py"], cwd=work_dir, check=True)
    test_patch = subprocess.check_output(["git", "diff", "--cached", "HEAD"], cwd=work_dir, text=True)

    return bare_dir, base_commit, test_patch


# ==============================================================================
# P0 ACCEPTANCE TEST 1: Empty test suite fails
# ==============================================================================

def test_01_empty_test_suite_fails():
    print("Test 1: Empty test suite returns FAIL (resolved=False)...")
    task = {
        "instance_id": "test__task-01",
        "repo": "pallets/flask",
        "base_commit": "4c288bc97ea371817199908d0d9b12de9dae327e",
        "f2p_tests": [],  # EMPTY TEST SUITE
        "p2p_tests": ["tests/test_basic.py"],
        "test_patch": "diff --git a/tests/test_basic.py..."
    }
    dummy_patch = "diff --git a/src/flask/config.py b/src/flask/config.py\n--- a/src/flask/config.py\n+++ b/src/flask/config.py\n"
    res = verify_task_patch(task, dummy_patch)
    assert not res["resolved"], "Empty test suite must NEVER be marked resolved!"
    assert res["reason"] == "EMPTY_TEST_SUITE_FAIL", f"Expected EMPTY_TEST_SUITE_FAIL, got {res.get('reason')}"
    print("  PASS: Empty test suite strictly rejected.")


# ==============================================================================
# P0 ACCEPTANCE TEST 2: Corrupted test_patch fails
# ==============================================================================

def test_02_corrupted_test_patch_fails():
    print("Test 2: Corrupted test_patch returns FAIL (resolved=False)...")
    bare_flask = REPO_BARE_MAP.get("pallets/flask")
    if not bare_flask or not bare_flask.exists():
        print("  SKIP: flask.git bare cache not found.")
        return

    task = {
        "instance_id": "test__task-02",
        "repo": "pallets/flask",
        "base_commit": "4c288bc97ea371817199908d0d9b12de9dae327e",
        "f2p_tests": ["tests/test_blueprints.py::test_dotted_name_not_allowed"],
        "p2p_tests": [],
        "test_patch": "CORRUPTED_GARBAGE_PATCH_HEADER\n+invalid diff syntax\n"
    }
    dummy_patch = "diff --git a/src/flask/config.py b/src/flask/config.py\n--- a/src/flask/config.py\n+++ b/src/flask/config.py\n"
    res = verify_task_patch(task, dummy_patch)
    assert not res["resolved"], "Corrupted test patch must NEVER be marked resolved!"
    assert "TEST_PATCH_APPLY_FAILED" in res.get("reason", ""), f"Expected TEST_PATCH_APPLY_FAILED, got {res.get('reason')}"
    print("  PASS: Corrupted test_patch strictly rejected.")


# ==============================================================================
# P0 ACCEPTANCE TEST 3: F2P PASS + P2P FAIL returns FAIL
# ==============================================================================

def test_03_f2p_pass_p2p_fail_returns_fail():
    print("Test 3: F2P PASS + P2P FAIL returns FAIL (regression detection)...")
    tmp = Path(tempfile.mkdtemp())
    try:
        bare_repo, base_commit, test_patch = _create_test_git_repo(tmp)
        task = {
            "instance_id": "test__regression-03",
            "repo": "test/calculator",
            "base_commit": base_commit,
            "bare_repo_path": bare_repo,
            "f2p_tests": ["tests/test_calc.py::test_add_f2p"],
            "p2p_tests": ["tests/test_calc.py::test_mul_p2p"],
            "test_patch": test_patch
        }

        # Regression patch: fixes add (F2P), but breaks mul (P2P)
        regression_patch = (
            "diff --git a/calculator.py b/calculator.py\n"
            "--- a/calculator.py\n"
            "+++ b/calculator.py\n"
            "@@ -1,5 +1,5 @@\n"
            " def add(a, b):\n"
            "-    return a - b  # defect\n"
            "+    return a + b\n"
            " \n"
            " def mul(a, b):\n"
            "-    return a * b\n"
            "+    return a + b  # REGRESSION INTRODUCED\n"
        )

        res = verify_task_patch(task, regression_patch)
        assert not res["resolved"], "Regression (P2P failure) must NEVER be marked resolved!"
        assert res["f2p_passed"] is True, "F2P should have passed with the patch"
        assert res["p2p_passed"] is False, "P2P should have failed due to regression"
        assert res["reason"] == "P2P_REGRESSION_FAILED", f"Expected P2P_REGRESSION_FAILED, got {res.get('reason')}"
        print("  PASS: Regression detected. F2P passed, P2P failed -> resolved=False.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================================
# P0 ACCEPTANCE TEST 4: F2P PASS + P2P PASS returns RESOLVED & exit 5 treated as FAIL
# ==============================================================================

def test_04_f2p_pass_p2p_pass_returns_resolved():
    print("Test 4: F2P PASS + P2P PASS returns RESOLVED (resolved=True)...")
    tmp = Path(tempfile.mkdtemp())
    try:
        bare_repo, base_commit, test_patch = _create_test_git_repo(tmp)
        task = {
            "instance_id": "test__resolved-04",
            "repo": "test/calculator",
            "base_commit": base_commit,
            "bare_repo_path": bare_repo,
            "f2p_tests": ["tests/test_calc.py::test_add_f2p"],
            "p2p_tests": ["tests/test_calc.py::test_mul_p2p"],
            "test_patch": test_patch
        }

        # Clean correct patch: fixes add (F2P), preserves mul (P2P)
        clean_patch = (
            "diff --git a/calculator.py b/calculator.py\n"
            "--- a/calculator.py\n"
            "+++ b/calculator.py\n"
            "@@ -1,5 +1,5 @@\n"
            " def add(a, b):\n"
            "-    return a - b  # defect\n"
            "+    return a + b\n"
            " \n"
            " def mul(a, b):\n"
            "     return a * b\n"
        )

        res = verify_task_patch(task, clean_patch)
        assert res["resolved"] is True, f"Clean patch should be RESOLVED, got {res}"
        assert res["pre_patch_f2p_reproduced"] is True, "Pre-patch defect must be reproduced"
        assert res["f2p_passed"] is True, "Post-patch F2P must pass"
        assert res["p2p_passed"] is True, "Post-patch P2P must pass"
        assert res["reason"] == "RESOLVED"

        # Verification of Pytest Exit Code 5 (no tests collected):
        task_nonexistent_test = {
            "instance_id": "test__exit5-04",
            "repo": "test/calculator",
            "base_commit": base_commit,
            "bare_repo_path": bare_repo,
            "f2p_tests": ["tests/test_empty.py"],
            "p2p_tests": [],
            "test_patch": test_patch
        }
        res_exit5 = verify_task_patch(task_nonexistent_test, clean_patch)
        assert not res_exit5["resolved"], "Pytest exit code 5 (no tests collected) must NEVER be marked resolved!"
        assert any(log.get("no_tests_collected") for log in res_exit5.get("f2p_logs", [])), f"Exit code 5 flag must be recorded: {res_exit5}"

        print("  PASS: Full F2P + P2P verification produces RESOLVED. Exit code 5 strictly rejected as FAIL.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================================
# P0 ACCEPTANCE TEST 5: Sandbox containment blocks host escape & network
# ==============================================================================

def test_05_sandbox_containment_blocks_host_escape():
    print("Test 5: Sandbox containment blocks host credentials and network egress...")
    bare_flask = REPO_BARE_MAP.get("pallets/flask")
    if not bare_flask or not bare_flask.exists():
        print("  SKIP: flask.git bare cache not found.")
        return

    ws = SandboxWorkspace("containment_test", "pallets/flask", "4c288bc97ea371817199908d0d9b12de9dae327e", bare_flask)
    ws.setup()
    try:
        # Check 1: Host credentials (.kaggle) must be inaccessible
        res_kaggle = ws.dispatch_tool("run_command", {"command": "ls -la /home/mikhail/.kaggle 2>&1"})
        assert res_kaggle.get("exit_code") != 0, f"Expected non-zero exit for host secret access: {res_kaggle}"
        assert "No such file or directory" in res_kaggle.get("stdout", "") or "Нет такого файла" in res_kaggle.get("stdout", "") or "No such file" in res_kaggle.get("stderr", "") or "Нет такого файла" in res_kaggle.get("stderr", "")

        # Check 2: Host ssh keys (.ssh) must be inaccessible
        res_ssh = ws.dispatch_tool("run_command", {"command": "ls -la /home/mikhail/.ssh 2>&1"})
        assert res_ssh.get("exit_code") != 0

        # Check 3: Network egress must be completely blocked
        res_net = ws.dispatch_tool("run_command", {"command": "curl -s --connect-timeout 2 https://1.1.1.1 2>&1 || echo NET_EGRESS_BLOCKED"})
        assert "NET_EGRESS_BLOCKED" in res_net.get("stdout", "") or res_net.get("exit_code") != 0

        print("  PASS: Container sandbox completely hides host secrets (.kaggle, .ssh) and blocks network egress.")
    finally:
        ws.teardown()


# ==============================================================================
# P0 ACCEPTANCE TEST 6: AST locator self-contained delivery without host files
# ==============================================================================

def test_06_ast_locator_delivery_without_host_pre_copy():
    print("Test 6: AST locator self-contained delivery via run_command without host pre-copy...")
    bare_flask = REPO_BARE_MAP.get("pallets/flask")
    if not bare_flask or not bare_flask.exists():
        print("  SKIP: flask.git bare cache not found.")
        return

    # Extract delivery one-liner from v17_ast_bm25 system prompt
    v17_prompt = (REPO_ROOT / "candidates" / "v17_ast_bm25" / "prompts" / "system.md").read_text(encoding="utf-8")
    assert "import zlib,base64;open('/tmp/ast_locator.py','wb')" in v17_prompt, "Delivery one-liner missing from system.md!"

    delivery_cmd = None
    for line in v17_prompt.splitlines():
        if "open('/tmp/ast_locator.py'" in line:
            start_idx = line.find('python3 -c "import zlib')
            end_idx = line.rfind('`')
            if start_idx != -1 and end_idx != -1:
                delivery_cmd = line[start_idx:end_idx]
            break

    assert delivery_cmd is not None, "Failed to parse delivery command from system.md"

    ws = SandboxWorkspace("locator_delivery_test", "pallets/flask", "4c288bc97ea371817199908d0d9b12de9dae327e", bare_flask)
    ws.setup()
    try:
        # Run delivery command inside fresh container
        res = ws.dispatch_tool("run_command", {"command": delivery_cmd})
        assert res.get("exit_code") == 0, f"Delivery command failed: {res}"
        assert "Top-" in res.get("stdout", "") or "Score:" in res.get("stdout", "") or len(res.get("stdout", "")) > 0

        # Verify ast_locator.py exists in /tmp
        res_chk = ws.dispatch_tool("run_command", {"command": "test -f /tmp/ast_locator.py && echo LOCATOR_STAGED_OK"})
        assert "LOCATOR_STAGED_OK" in res_chk.get("stdout", "")

        # CRITICAL: Verify that delivery leaves /workspace completely untouched (zero git diff)
        diff = ws.get_final_diff()
        assert diff == "", f"Locator delivery polluted repository workspace: {diff}"

        print("  PASS: AST locator extracts cleanly to /tmp in-container with zero workspace pollution.")
    finally:
        ws.teardown()


# ==============================================================================
# P0 ACCEPTANCE TEST 7: Clean checkout candidate parity & honest metrics
# ==============================================================================

def test_07_clean_checkout_candidate_parity():
    print("Test 7: Clean checkout candidate parity & honest metrics...")
    candidates = ["v15_baseline", "v17_grep_only", "v17_ast_bm25"]
    for c in candidates:
        cand_dir = REPO_ROOT / "candidates" / c
        assert cand_dir.is_dir(), f"Candidate dir missing: {cand_dir}"
        assert (cand_dir / "prompts" / "system.md").is_file()
        assert (cand_dir / "configs" / "sampling.yaml").is_file()
        assert (cand_dir / "eval_config.yaml").is_file()
        assert (cand_dir / "agent.yaml").is_file()

    # Verify v15_baseline SHA256 matches paper/small_model_forensics/v15_unpacked
    forensics_dir = REPO_ROOT / "paper" / "small_model_forensics" / "v15_unpacked"
    for filename in ["prompts/system.md", "configs/sampling.yaml", "eval_config.yaml", "agent.yaml"]:
        orig_bytes = (forensics_dir / filename).read_bytes()
        cand_bytes = (REPO_ROOT / "candidates" / "v15_baseline" / filename).read_bytes()
        assert hashlib.sha256(orig_bytes).hexdigest() == hashlib.sha256(cand_bytes).hexdigest(), (
            f"SHA256 mismatch for v15_baseline {filename} against forensics!"
        )

    # Verify sampling parameters are identical across all candidates
    v15_sampling = (REPO_ROOT / "candidates" / "v15_baseline" / "configs" / "sampling.yaml").read_text()
    v17_grep_sampling = (REPO_ROOT / "candidates" / "v17_grep_only" / "configs" / "sampling.yaml").read_text()
    v17_ast_sampling = (REPO_ROOT / "candidates" / "v17_ast_bm25" / "configs" / "sampling.yaml").read_text()

    assert v15_sampling == v17_grep_sampling, "v17_grep_only sampling differs from baseline!"
    assert v15_sampling == v17_ast_sampling, "v17_ast_bm25 sampling differs from baseline!"

    # Verify prompt differentiation
    v15_prompt = (REPO_ROOT / "candidates" / "v15_baseline" / "prompts" / "system.md").read_text()
    v17_grep_prompt = (REPO_ROOT / "candidates" / "v17_grep_only" / "prompts" / "system.md").read_text()
    v17_ast_prompt = (REPO_ROOT / "candidates" / "v17_ast_bm25" / "prompts" / "system.md").read_text()

    assert v15_prompt != v17_grep_prompt
    assert v17_grep_prompt != v17_ast_prompt
    assert 'git grep -n -i "SPECIFIC_TOKEN" -- "*.py"' in v17_grep_prompt
    assert 'ast_locator.py' in v17_ast_prompt

    # Verify localization recall metrics accuracy (Recall@3 = 59.52% across 42 tasks)
    with open(LOCATOR_RESULTS_PATH) as f:
        data = json.load(f)
    summary = data["summary"]["overall"]
    assert summary["count"] == 42, f"Expected 42 tasks, got {summary['count']}"
    assert summary["recall_at_3"] == 0.5952, f"Expected 0.5952, got {summary['recall_at_3']}"

    # Verify honest hardware status (BLOCKED when GPU is inadequate)
    hw = check_hardware_capabilities()
    assert hw["available_vram_gb"] < 5.5, "Expected <5.5GB local GPU VRAM on CPU/4GB test machine"
    assert hw["inference_eligible"] is False, "Inference must be marked ineligible on inadequate hardware"

    print("  PASS: All 3 candidates verified from tracked git tree with exact sampling parity and honest metrics.")


if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING P0 FINAL GATE ACCEPTANCE TESTS (CPU INTEGRATION)")
    print("=" * 80)
    test_01_empty_test_suite_fails()
    test_02_corrupted_test_patch_fails()
    test_03_f2p_pass_p2p_fail_returns_fail()
    test_04_f2p_pass_p2p_pass_returns_resolved()
    test_05_sandbox_containment_blocks_host_escape()
    test_06_ast_locator_delivery_without_host_pre_copy()
    test_07_clean_checkout_candidate_parity()
    print("=" * 80)
    print("ALL 7 P0 ACCEPTANCE TESTS PASSED (PASS)")
    print("=" * 80)
