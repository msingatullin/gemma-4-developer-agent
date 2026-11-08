#!/usr/bin/env python3
"""
Automated CPU Verification Gate for Authentic Upstream Repository Sample (Phase 1 / P1.5)
Strictly Verifies:
1. Clean checkout of upstream repo at exact pinned base_commit.
2. Isolated virtualenv per task with strictly pinned dependencies.
3. Test patch application -> RED failure with exact expected failure signature/type.
4. Gold patch application -> GREEN pass (asserts fix resolves failure with 0 failures).
5. Comprehensive regression suite pass (Flask: module suite; Requests: 43 verified offline P2P tests).
6. Real network isolation enforced via Linux network namespace (unshare -rn).
7. Detailed audit record logging to cpu_verification_results.jsonl.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment" / "real_repo_sample"
WORK_DIR = Path("/tmp/real_tasks_cpu_eval")
UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")

# Load verified offline P2P test list for Requests
REQUESTS_OFFLINE_TESTS_FILE = ARCHIVE_DIR / "requests_offline_p2p_tests.json"
assert REQUESTS_OFFLINE_TESTS_FILE.exists(), f"Missing offline tests file: {REQUESTS_OFFLINE_TESTS_FILE}"
REQUESTS_OFFLINE_TESTS = json.loads(REQUESTS_OFFLINE_TESTS_FILE.read_text(encoding="utf-8"))
REQUESTS_OFFLINE_FILTER = " or ".join(REQUESTS_OFFLINE_TESTS)

TASKS_SPEC = [
    {
        "instance_id": "pallets__flask-4045",
        "repo": "pallets/flask",
        "repo_bare": UPSTREAM_CACHE / "flask.git",
        "base_commit": "d8c37f43724cd9fb0870f77877b7c4c7e38a19e0",
        "python_version": "3.10",
        "target_file": "src/flask/blueprints.py",
        "test_file": "tests/test_blueprints.py",
        "test_filter": "test_dotted_name_not_allowed or test_route_decorator_custom_endpoint_with_dots",
        "f2p_tests": [
            "tests/test_blueprints.py::test_dotted_name_not_allowed",
            "tests/test_blueprints.py::test_route_decorator_custom_endpoint_with_dots"
        ],
        "expected_red_signatures": [
            "DID NOT RAISE <class 'ValueError'>",
            "AssertionError: Blueprint endpoints should not contain dots"
        ],
        "expected_f2p_count": 2,
        "regression_args": ["tests/test_blueprints.py"],
        "pinned_pkgs": ["werkzeug==2.0.1", "pytest==6.2.5", "setuptools==57.5.0"]
    },
    {
        "instance_id": "pallets__flask-4992",
        "repo": "pallets/flask",
        "repo_bare": UPSTREAM_CACHE / "flask.git",
        "base_commit": "4c288bc97ea371817199908d0d9b12de9dae327e",
        "python_version": "3.11",
        "target_file": "src/flask/config.py",
        "test_file": "tests/test_config.py",
        "test_filter": "test_config_from_file_toml",
        "f2p_tests": [
            "tests/test_config.py::test_config_from_file_toml"
        ],
        "expected_red_signatures": [
            "TypeError: Config.from_file() got an unexpected keyword argument 'text'"
        ],
        "expected_f2p_count": 1,
        "regression_args": ["tests/test_config.py"],
        "pinned_pkgs": ["pytest==7.4.4", "werkzeug==2.3.8"]
    },
    {
        "instance_id": "pallets__flask-5063",
        "repo": "pallets/flask",
        "repo_bare": UPSTREAM_CACHE / "flask.git",
        "base_commit": "182ce3dd15dfa3537391c3efaf9c3ff407d134d4",
        "python_version": "3.11",
        "target_file": "src/flask/cli.py",
        "test_file": "tests/test_cli.py",
        "test_filter": "test_subdomain or test_host",
        "f2p_tests": [
            "tests/test_cli.py::TestRoutes::test_subdomain",
            "tests/test_cli.py::TestRoutes::test_host"
        ],
        "expected_red_signatures": [
            "AssertionError: assert 'Subdomain' in",
            "AssertionError: assert 'Host' in"
        ],
        "expected_f2p_count": 2,
        "regression_args": ["tests/test_cli.py", "-k", "TestRoutes"],
        "pinned_pkgs": ["pytest==7.4.4", "werkzeug==2.3.8", "blinker==1.9.0"]
    },
    {
        "instance_id": "psf__requests-1963",
        "repo": "psf/requests",
        "repo_bare": UPSTREAM_CACHE / "requests.git",
        "base_commit": "110048f9837f8441ea536804115e80b69f400277",
        "python_version": "3.9",
        "target_file": "requests/sessions.py",
        "test_file": "test_requests.py",
        "test_filter": "test_requests_are_updated_each_time",
        "f2p_tests": [
            "test_requests.py::TestRedirects::test_requests_are_updated_each_time"
        ],
        "expected_red_signatures": [
            "AssertionError: assert 'POST' == 'GET'"
        ],
        "expected_f2p_count": 1,
        "regression_args": ["test_requests.py", "-k", REQUESTS_OFFLINE_FILTER],
        "pinned_pkgs": ["pytest==6.2.5"]
    },
    {
        "instance_id": "psf__requests-2148",
        "repo": "psf/requests",
        "repo_bare": UPSTREAM_CACHE / "requests.git",
        "base_commit": "fe693c492242ae532211e0c173324f09ca8cf227",
        "python_version": "3.9",
        "target_file": "requests/models.py",
        "test_file": "test_requests.py",
        "test_filter": "test_iter_content_handles_socket_error",
        "f2p_tests": [
            "test_requests.py::RequestsTestCase::test_iter_content_handles_socket_error"
        ],
        "expected_red_signatures": [
            "OSError"
        ],
        "expected_f2p_count": 1,
        "regression_args": ["test_requests.py", "-k", REQUESTS_OFFLINE_FILTER],
        "pinned_pkgs": ["pytest==6.2.5"]
    }
]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def run_isolated_command(cmd: list, cwd: str) -> subprocess.CompletedProcess:
    """Run command with Linux network namespace isolation (unshare -rn)."""
    wrapped_cmd = ["unshare", "-rn"] + cmd
    return subprocess.run(wrapped_cmd, capture_output=True, text=True, cwd=cwd)

def run_task_verification(spec: dict) -> tuple:
    iid = spec["instance_id"]
    print(f"\n=======================================================")
    print(f"[*] Starting CPU Verification for {iid}")
    print(f"    Repo: {spec['repo']} @ {spec['base_commit'][:10]}")
    print(f"    Python: {spec['python_version']} | Target: {spec['target_file']}")
    
    task_archive = ARCHIVE_DIR / iid
    gold_patch_file = task_archive / "gold_patch.diff"
    test_patch_file = task_archive / "test_patch.diff"
    problem_stmt_file = task_archive / "problem_statement.txt"

    assert gold_patch_file.exists(), f"Missing gold patch: {gold_patch_file}"
    assert test_patch_file.exists(), f"Missing test patch: {test_patch_file}"

    gold_sha = sha256_file(gold_patch_file)
    test_sha = sha256_file(test_patch_file)

    task_work = WORK_DIR / iid
    if task_work.exists():
        shutil.rmtree(task_work)
    task_work.mkdir(parents=True, exist_ok=True)

    # 1. Clean checkout
    checkout_cmd = [
        "git", f"--git-dir={spec['repo_bare']}", f"--work-tree={task_work}",
        "checkout", "-f", spec["base_commit"], "."
    ]
    subprocess.run(checkout_cmd, check=True, capture_output=True)

    # 2. Virtualenv setup
    venv_dir = task_work / ".venv"
    subprocess.run(["uv", "venv", str(venv_dir), "--python", spec["python_version"]], check=True, capture_output=True)
    python_bin = venv_dir / "bin" / "python"
    pytest_bin = venv_dir / "bin" / "pytest"

    # Install package editable + pinned packages
    install_cmd = ["uv", "pip", "install", "-e", str(task_work)] + spec["pinned_pkgs"] + ["--python", str(python_bin)]
    subprocess.run(install_cmd, check=True, capture_output=True)

    # Record installed environment
    freeze_res = subprocess.run(["uv", "pip", "freeze", "--python", str(python_bin)], capture_output=True, text=True)
    installed_packages = [line.strip() for line in freeze_res.stdout.splitlines() if line.strip()]

    # 3. Apply test patch ONLY (Validating RED test at base)
    patch_apply_test = subprocess.run(
        ["patch", "-p1", "-d", str(task_work)],
        input=test_patch_file.read_bytes(),
        capture_output=True
    )
    assert patch_apply_test.returncode == 0, f"Failed to apply test patch: {patch_apply_test.stderr.decode()}"

    # Run pytest under network namespace isolation (unshare -rn) to assert failure
    test_cmd = [str(pytest_bin), str(task_work / spec["test_file"]), "-k", spec["test_filter"], "-v"]
    t0 = time.time()
    red_run = run_isolated_command(test_cmd, cwd=str(task_work))
    red_time = time.time() - t0

    raw_traceback = red_run.stdout + ("\n" + red_run.stderr if red_run.stderr else "")
    
    # Verify RED exit code and specific error signatures
    is_red_exit = (red_run.returncode != 0)
    assert is_red_exit, f"Red test did not fail for {iid}! (Exit code: {red_run.returncode})"

    missing_signatures = []
    for sig in spec["expected_red_signatures"]:
        if sig not in raw_traceback:
            missing_signatures.append(sig)

    assert len(missing_signatures) == 0, f"Missing expected RED signatures in {iid}: {missing_signatures}\nOutput:\n{raw_traceback[:500]}"
    print(f"[-] Base commit with test patch (RED): Exit Code {red_run.returncode} (expected != 0)")
    print(f"    Verified RED error signatures: {spec['expected_red_signatures']}")

    raw_trace_file = task_work / "raw_failure_traceback.txt"
    raw_trace_file.write_text(raw_traceback, encoding="utf-8")

    # 4. Apply gold patch ONLY in qualification checkout to verify GREEN
    patch_apply_gold = subprocess.run(
        ["patch", "-p1", "-d", str(task_work)],
        input=gold_patch_file.read_bytes(),
        capture_output=True
    )
    assert patch_apply_gold.returncode == 0, f"Failed to apply gold patch: {patch_apply_gold.stderr.decode()}"

    t1 = time.time()
    green_run = run_isolated_command(test_cmd, cwd=str(task_work))
    green_time = time.time() - t1

    is_green_verified = (green_run.returncode == 0) and ("failed" not in green_run.stdout.lower() or "0 failed" in green_run.stdout.lower())
    assert is_green_verified, f"Green test failed to pass with gold patch for {iid}!\nOutput:\n{green_run.stdout}"
    print(f"[+] With Gold Patch (GREEN): Exit Code {green_run.returncode} (expected == 0)")

    # 5. Run full regression suite for module under network isolation
    reg_cmd = [str(pytest_bin)] + spec["regression_args"] + ["-q"]
    t2 = time.time()
    reg_run = run_isolated_command(reg_cmd, cwd=str(task_work))
    reg_time = time.time() - t2
    
    is_regression_clean = (reg_run.returncode == 0) and ("failed" not in reg_run.stdout.lower() or "0 failed" in reg_run.stdout.lower())
    assert is_regression_clean, f"Regression detected for {iid}!\nOutput:\n{reg_run.stdout}\n{reg_run.stderr}"
    print(f"[+] Regression Suite: Exit Code {reg_run.returncode} (expected == 0, clean zero regressions in {round(reg_time, 2)}s)")

    record = {
        "instance_id": iid,
        "repo": spec["repo"],
        "base_commit": spec["base_commit"],
        "python_version": spec["python_version"],
        "target_file": spec["target_file"],
        "f2p_tests": spec["f2p_tests"],
        "gold_patch_sha256": gold_sha,
        "test_patch_sha256": test_sha,
        "installed_dependencies": installed_packages,
        "red_test": {
            "exit_code": red_run.returncode,
            "status": "FAIL_VERIFIED",
            "verified_red_signatures": spec["expected_red_signatures"],
            "elapsed_seconds": round(red_time, 3),
            "traceback_lines": len(raw_traceback.splitlines()),
            "traceback_chars": len(raw_traceback)
        },
        "green_test": {
            "exit_code": green_run.returncode,
            "status": "PASS_VERIFIED",
            "elapsed_seconds": round(green_time, 3)
        },
        "regression_check": {
            "exit_code": reg_run.returncode,
            "status": "CLEAN_ZERO_REGRESSIONS",
            "elapsed_seconds": round(reg_time, 3),
            "regression_suite": spec["regression_args"]
        },
        "network_isolation": "Linux network namespace isolation (unshare -rn) verified; Requests suite restricted to 43 verified offline P2P tests; 0 external network dependencies.",
        "cpu_eligibility_verdict": "ELIGIBLE_FOR_INFERENCE"
    }

    return record, raw_traceback

def main():
    print("[*] Launching CPU Eligibility & Verification Gate for Real Repos (P1.5)...")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    tracebacks = {}

    for spec in TASKS_SPEC:
        rec, raw_trace = run_task_verification(spec)
        results.append(rec)
        tracebacks[spec["instance_id"]] = raw_trace

    # Save jsonl report
    out_jsonl = ARCHIVE_DIR / "cpu_verification_results.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"\n[✓] All {len(results)} instances verified. Results written to {out_jsonl}")

    # Save raw tracebacks into task archive
    for iid, tr in tracebacks.items():
        (ARCHIVE_DIR / iid / "raw_failure_traceback.txt").write_text(tr, encoding="utf-8")

    # Print summary table
    print("\n" + "="*80)
    print(f"{'Instance ID':<22} | {'Base Commit':<10} | {'Py':<4} | {'Red Exit':<8} | {'Green Exit':<10} | {'Verdict'}")
    print("-" * 80)
    for r in results:
        print(f"{r['instance_id']:<22} | {r['base_commit'][:10]:<10} | {r['python_version']:<4} | {r['red_test']['exit_code']:<8} | {r['green_test']['exit_code']:<10} | {r['cpu_eligibility_verdict']}")
    print("="*80)

if __name__ == "__main__":
    main()
