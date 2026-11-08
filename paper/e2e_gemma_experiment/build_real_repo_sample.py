#!/usr/bin/env python3
"""
Extract and serialize 5 authentic, pinned upstream repository defect tasks
from the frozen SWE benchmark manifest (pallets/flask, psf/requests).
Preserves authentic git commits, full problem statements, gold patches, and tests.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MANIFEST_SOURCE = BASE_DIR.parent.parent / "pilot" / "frozen_task_manifest.json"
REAL_SAMPLE_DIR = BASE_DIR / "real_repo_sample"

def main():
    REAL_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    all_tasks = json.loads(MANIFEST_SOURCE.read_text(encoding="utf-8"))
    
    # Pick 5 authentic instances
    target_ids = [
        "pallets__flask-4045",
        "pallets__flask-4992",
        "pallets__flask-5063",
        "psf__requests-1963",
        "psf__requests-2148"
    ]
    
    selected = [t for t in all_tasks if t["instance_id"] in target_ids]
    print(f"Extracting {len(selected)} authentic upstream tasks into {REAL_SAMPLE_DIR}...")
    
    records = []
    for t in selected:
        iid = t["instance_id"]
        tdir = REAL_SAMPLE_DIR / iid
        tdir.mkdir(parents=True, exist_ok=True)
        
        # Save gold patch
        (tdir / "gold_patch.diff").write_text(t["gold_patch"], encoding="utf-8")
        
        # Save test patch
        (tdir / "test_patch.diff").write_text(t["test_patch"], encoding="utf-8")
        
        # Save problem statement
        (tdir / "problem_statement.txt").write_text(t["problem_statement"], encoding="utf-8")
        
        meta = {
            "instance_id": iid,
            "repo": t["repo"],
            "repo_url": t["repo_url"],
            "base_commit": t["base_commit"],
            "created_at": t["created_at"],
            "fail_to_pass": t["fail_to_pass"],
            "pass_to_pass_count": len(t.get("pass_to_pass", [])),
            "gold_patch_sha256": t["gold_patch_sha256"],
            "test_patch_sha256": t["test_patch_sha256"]
        }
        (tdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        records.append(meta)
        print(f"  [SAVED] {iid}: Repo={t['repo']} Commit={t['base_commit'][:10]}")
        
    (REAL_SAMPLE_DIR / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\nReal repository sample successfully created at {REAL_SAMPLE_DIR}!")

if __name__ == "__main__":
    main()
