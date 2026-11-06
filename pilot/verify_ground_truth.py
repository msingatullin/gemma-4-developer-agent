#!/usr/bin/env python3
"""Hermetic patch applicator check for Gemma 4 E2E Pilot Ground Truth Manifest.

Verifies that for each of the 10 tasks in frozen_task_manifest.json:
1. Cryptographic hashes match recorded test_patch_sha256 and gold_patch_sha256.
2. The base_commit is a valid git revision.
3. Test patch applies cleanly (git apply --check).
4. Gold patch applies cleanly (git apply --check).
"""

import json
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "frozen_task_manifest.json"


def check_task(task: dict, temp_dir: Path) -> dict:
    iid = task["instance_id"]
    repo_url = task["repo_url"]
    base = task["base_commit"]
    test_patch = task["test_patch"]
    gold_patch = task["gold_patch"]

    tp_sha = hashlib.sha256(test_patch.encode("utf-8")).hexdigest()
    gp_sha = hashlib.sha256(gold_patch.encode("utf-8")).hexdigest()

    if tp_sha != task["test_patch_sha256"]:
        return {"instance_id": iid, "status": "FAIL_HASH", "error": "test_patch sha mismatch"}
    if gp_sha != task["gold_patch_sha256"]:
        return {"instance_id": iid, "status": "FAIL_HASH", "error": "gold_patch sha mismatch"}

    task_dir = temp_dir / iid
    task_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(["git", "init"], cwd=task_dir, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=task_dir, check=True, capture_output=True)
        subprocess.run(["git", "fetch", "--depth", "1", "origin", base], cwd=task_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "FETCH_HEAD"], cwd=task_dir, check=True, capture_output=True)

        tp_file = task_dir / "test_patch.diff"
        tp_file.write_text(test_patch, encoding="utf-8")
        res_tp = subprocess.run(["git", "apply", "--check", str(tp_file)], cwd=task_dir, capture_output=True, text=True)
        if res_tp.returncode != 0:
            return {"instance_id": iid, "status": "FAIL_TEST_PATCH_APPLY", "error": res_tp.stderr}

        gp_file = task_dir / "gold_patch.diff"
        gp_file.write_text(gold_patch, encoding="utf-8")
        res_gp = subprocess.run(["git", "apply", "--check", str(gp_file)], cwd=task_dir, capture_output=True, text=True)
        if res_gp.returncode != 0:
            return {"instance_id": iid, "status": "FAIL_GOLD_PATCH_APPLY", "error": res_gp.stderr}

        return {"instance_id": iid, "status": "PASS", "repo": task["repo"], "base": base[:8]}
    except Exception as e:
        return {"instance_id": iid, "status": "ERROR", "error": str(e)}


def main():
    if not MANIFEST_PATH.exists():
        print(f"Error: {MANIFEST_PATH} not found.")
        sys.exit(1)

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"Loaded {len(tasks)} tasks from {MANIFEST_PATH}")
    with tempfile.TemporaryDirectory(prefix="gemma_gt_") as tmp:
        temp_dir = Path(tmp)
        results = []
        for t in tasks:
            print(f"Verifying {t['instance_id']}...", end=" ", flush=True)
            res = check_task(t, temp_dir)
            results.append(res)
            print(res["status"])

    all_pass = all(r["status"] == "PASS" for r in results)
    print("\nSummary:")
    for r in results:
        print(f"  {r['instance_id']}: {r['status']}")
    print(f"\nFinal Ground Truth Verification: {'PASS' if all_pass else 'FAIL'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
