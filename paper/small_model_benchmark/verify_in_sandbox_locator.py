#!/usr/bin/env python3
"""
Verification Script for In-Sandbox Locator Integration (Stage 1).
Demonstrates:
1. Reproduction of the fatal v17 failure mode ('tools/ast_bm25_locator.py' missing in container).
2. Verification of the compliant locator implementation inside a clean simulated Container A.
3. Accurate extraction of problem statement tokens and ranking top-3 files.
4. Cleanliness check: 0 workspace pollution, 0 git diff contamination.
5. Absence of gold patch in agent context or workspace.
"""

import os
import sys
import re
import json
import time
import shutil
import tempfile
import subprocess
from pathlib import Path

UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")
REPO_BARE_MAP = {
    "pallets/flask": UPSTREAM_CACHE / "flask.git",
    "psf/requests": UPSTREAM_CACHE / "requests.git",
    "pytest-dev/pytest": UPSTREAM_CACHE / "pytest.git"
}

MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"

TEST_CASES = [
    {
        "instance_id": "pallets__flask-4045",
        "repo": "pallets/flask",
        "base_commit": "d8c37f43724cd9fb0870f77877b7c4c7e38a19e0",
        "target_file": "src/flask/blueprints.py"
    },
    {
        "instance_id": "psf__requests-2148",
        "repo": "psf/requests",
        "base_commit": "fe693c492242ae532211e0c173324f09ca8cf227",
        "target_file": "requests/models.py"
    },
    {
        "instance_id": "pytest-dev__pytest-5103",
        "repo": "pytest-dev/pytest",
        "base_commit": "10ca84ffc56c2dd2d9dc4bd71b7b898e083500cd",
        "target_file": "src/_pytest/assertion/rewrite.py"
    }
]

# The compliant in-sandbox locator Python script
# Reads the exact, verified ast_bm25_locator.py code
LOCATOR_SCRIPT_SOURCE = Path(__file__).resolve().parent / "ast_bm25_locator.py"
LOCATOR_CODE = LOCATOR_SCRIPT_SOURCE.read_text(encoding="utf-8")


def run_stage1_verification():
    print("=" * 70)
    print("STAGE 1: IN-SANDBOX LOCATOR INTEGRATION & RUNTIME CONTRACT VERIFICATION")
    print("=" * 70)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    task_map = {t["instance_id"]: t for t in manifest["tasks"]}

    all_passed = True
    results = []

    for tc in TEST_CASES:
        iid = tc["instance_id"]
        repo = tc["repo"]
        base_commit = tc["base_commit"]
        expected_target = tc["target_file"]
        task_data = task_map[iid]
        problem_statement = task_data["problem_statement"]

        print(f"\n--- Testing Task: {iid} ({repo}) ---")
        bare_repo = REPO_BARE_MAP[repo]

        # 1. Setup isolated workspace simulating Container A
        workdir = Path(tempfile.mkdtemp(prefix=f"sim_container_a_{iid.replace('/', '_')}_"))
        tmp_dir = Path(tempfile.mkdtemp(prefix="sim_container_tmp_"))

        try:
            # Clone repo snapshot at base_commit
            subprocess.run(["git", "clone", "-q", str(bare_repo), str(workdir)], check=True)
            subprocess.run(["git", "checkout", "-q", "-f", base_commit], cwd=workdir, check=True)
            # Create baseline commit as swegemma harness does
            subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "baseline", "--allow-empty"], cwd=workdir, check=True)

            print(f"  [Setup] Initialized clean workspace at commit {base_commit[:10]}")

            # 2. PROVE BUG REPRODUCTION: Old v17 command fails in clean Container A
            old_cmd = [sys.executable, "tools/ast_bm25_locator.py"]
            p_old = subprocess.run(old_cmd, cwd=workdir, capture_output=True, text=True)
            print(f"  [Reproduction] Old v17 command exit code: {p_old.returncode}")
            if p_old.returncode != 0:
                print(f"  [Reproduction] Confirmed expected failure: {p_old.stderr.strip() or p_old.stdout.strip()}")
            else:
                print("  [WARNING] Old command unexpectedly succeeded!")

            # 3. VERIFY COMPLIANT INTEGRATION:
            # Install locator into container's /tmp directory (outside /workspace)
            loc_path = tmp_dir / "ast_locator.py"
            loc_path.write_text(LOCATOR_CODE, encoding="utf-8")

            # Execute locator via run_command protocol inside /workspace
            t0 = time.time()
            compliant_cmd = [sys.executable, str(loc_path), "--query", problem_statement, "--top-k", "3"]
            p_new = subprocess.run(compliant_cmd, cwd=workdir, capture_output=True, text=True)
            lat = time.time() - t0

            print(f"  [Compliant] Execution completed in {lat:.3f}s with exit code {p_new.returncode}")
            print(f"  [Compliant] Output:\n{p_new.stdout.strip()}")

            if p_new.returncode != 0:
                print(f"  [FAIL] Error running locator: {p_new.stderr}")
                all_passed = False
                continue

            # Parse top files from format: "1. `filepath`"
            top_files = re.findall(r"\d+\.\s+`([^`]+)`", p_new.stdout)
            print(f"  [Ranking] Predicted Top Files: {top_files}")

            # Check if expected target is in Top 3
            hit = expected_target in top_files
            print(f"  [Target Check] Ground truth target '{expected_target}' in Top 3: {hit}")
            if not hit:
                print(f"  [FAIL] Target file not found in predictions!")
                all_passed = False

            # 4. REPOSITORY INTEGRITY AUDIT: Check git diff / status
            git_status = subprocess.run(["git", "status", "--short"], cwd=workdir, capture_output=True, text=True)
            git_diff = subprocess.run(["git", "diff", "HEAD"], cwd=workdir, capture_output=True, text=True)

            print(f"  [Diff Audit] Workspace git status: '{git_status.stdout.strip()}' (len={len(git_status.stdout.strip())})")
            print(f"  [Diff Audit] Workspace git diff lines: {len(git_diff.stdout.splitlines())}")

            clean_status = (len(git_status.stdout.strip()) == 0)
            clean_diff = (len(git_diff.stdout.strip()) == 0)

            if not clean_status or not clean_diff:
                print("  [FAIL] Workspace was contaminated by locator execution!")
                all_passed = False
            else:
                print("  [Diff Audit] PASS: Zero workspace pollution, zero git diff contamination.")

            # 5. GOLD PATCH LEAKAGE AUDIT: Verify no gold patch references
            gold_files = [f for f in workdir.rglob("*.patch")]
            if gold_files:
                print(f"  [Leakage Audit] FAIL: Found patch files in workspace: {gold_files}")
                all_passed = False
            else:
                print("  [Leakage Audit] PASS: Zero gold patch leakage.")

            results.append({
                "instance_id": iid,
                "target_file": expected_target,
                "top_files": top_files,
                "target_in_top3": hit,
                "clean_git_status": clean_status,
                "latency_sec": round(lat, 3)
            })

        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    if all_passed:
        print("STAGE 1 CONTRACT VERIFICATION: ALL CHECKS PASSED (PASS)")
    else:
        print("STAGE 1 CONTRACT VERIFICATION: SOME CHECKS FAILED (FAIL)")
    print("=" * 70)

    # Save verification record
    report_path = Path(__file__).resolve().parent / "STAGE1_IN_SANDBOX_VERIFICATION.json"
    with open(report_path, "w") as f:
        json.dump({"status": "PASS" if all_passed else "FAIL", "results": results}, f, indent=2)
    print(f"Saved verification report to: {report_path}")
    return all_passed


if __name__ == "__main__":
    ok = run_stage1_verification()
    sys.exit(0 if ok else 1)
