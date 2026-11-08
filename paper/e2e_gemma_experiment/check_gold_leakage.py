#!/usr/bin/env python3
"""
Automated Gold Solution Leakage Auditor (Phase 1)
Certifies that none of the 15 frozen evaluation prompts contain any reference
solution code, added lines, or leaked implementation artifacts from gold_patch.diff.
Distinguishes genuine gold leakage from pre-existing base repository code,
problem statement descriptions, and test traceback frames.
"""

import re
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment" / "real_repo_sample"
PROMPTS_DIR = ARCHIVE_DIR / "frozen_prompts"
UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")

def extract_added_lines_from_patch(patch_path: Path) -> list:
    """Extract substantive lines added by the gold patch (lines starting with +)"""
    lines = []
    for line in patch_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            # Ignore empty lines, pure comments, docstrings, or single-token syntax like pass/else
            if len(stripped) > 4 and not stripped.startswith(("#", '"""', "'''")):
                lines.append(stripped)
    return lines

def get_base_source(repo_name: str, base_commit: str, target_file: str) -> str:
    bare_repo = UPSTREAM_CACHE / f"{repo_name.split('/')[1]}.git"
    cmd = ["git", f"--git-dir={bare_repo}", "show", f"{base_commit}:{target_file}"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

def main():
    print("[*] Starting Automated Gold Leakage Audit across all 15 frozen prompts...")
    prompt_files = sorted(PROMPTS_DIR.glob("*__*.json"))
    assert len(prompt_files) == 15, f"Expected 15 prompt files, found {len(prompt_files)}"

    audit_records = []
    total_violations = 0

    for pf in prompt_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        iid = data["instance_id"]
        variant = data["variant"]
        user_prompt = data["user_prompt"]
        repo = data["repo"]
        base_commit = data["base_commit"]
        target_file = data["target_file"]
        
        gold_patch_path = ARCHIVE_DIR / iid / "gold_patch.diff"
        stmt_path = ARCHIVE_DIR / iid / "problem_statement.txt"
        test_patch_path = ARCHIVE_DIR / iid / "test_patch.diff"
        assert gold_patch_path.exists(), f"Missing gold patch: {gold_patch_path}"

        added_lines = extract_added_lines_from_patch(gold_patch_path)
        base_source = get_base_source(repo, base_commit, target_file)
        problem_stmt = stmt_path.read_text(encoding="utf-8")
        test_patch_text = test_patch_path.read_text(encoding="utf-8")

        # Check exact line leakage that is UNIQUE to the gold patch
        leaked_lines = []
        for line in added_lines:
            # If the line was already in the base file, in problem statement, or in test patch, it's not a gold leak
            if line in base_source:
                continue
            if line in problem_stmt:
                continue
            if line in test_patch_text:
                continue

            # If it appears in the prompt outside of base_source, it is a genuine leakage!
            # (Note that base_source is embedded in the prompt inside ```python ... ```)
            # So check if this novel line appears anywhere in the prompt text
            if line in user_prompt:
                leaked_lines.append(line)

        is_clean = (len(leaked_lines) == 0)
        if not is_clean:
            total_violations += 1
            print(f"  [!] LEAKAGE DETECTED in {pf.name}: {leaked_lines}")
        else:
            print(f"  [✓] {pf.name}: ZERO LEAKAGE certified ({len(added_lines)} gold lines audited)")

        audit_records.append({
            "prompt_file": pf.name,
            "instance_id": iid,
            "variant": variant,
            "checked_gold_lines_count": len(added_lines),
            "leaked_lines": leaked_lines,
            "zero_leakage_certified": is_clean
        })

    report_file = ARCHIVE_DIR / "gold_leakage_audit_report.json"
    report_file.write_text(json.dumps(audit_records, indent=2), encoding="utf-8")

    assert total_violations == 0, f"Audit failed with {total_violations} leakage violations!"
    print(f"\n[✓] ALL 15 PROMPTS CERTIFIED CLEAN. Report written to {report_file.name}")

if __name__ == "__main__":
    main()
