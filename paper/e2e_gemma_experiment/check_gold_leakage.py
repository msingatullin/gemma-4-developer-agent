#!/usr/bin/env python3
"""
Automated Gold Solution Leakage Auditor (Phase 1 / P1.5)
Verifies:
1. Absence of literal novel gold-patch added lines in all 15 frozen prompts.
2. Absence of contiguous multi-line code blocks / hunks copied from gold patches.
3. Explicit scope declaration: Syntactic verification certifying zero literal gold code
   copying. Does NOT claim absolute semantic isolation or absence of domain hints
   in upstream problem statements or failing test tracebacks.
"""

import re
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment" / "real_repo_sample"
PROMPTS_DIR = ARCHIVE_DIR / "frozen_prompts"
UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")

def extract_added_hunks_from_patch(patch_path: Path) -> tuple:
    """
    Extract:
    1. Single substantive lines added by gold patch (+ prefix, length > 4, non-comment).
    2. Multi-line hunk blocks (consecutive added lines >= 2).
    """
    lines = []
    current_hunk_lines = []
    hunks = []
    
    for raw_line in patch_path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            stripped = raw_line[1:].strip()
            # Ignore empty lines, pure comments, docstrings, or single-token syntax like pass/else
            if len(stripped) > 4 and not stripped.startswith(("#", '"""', "'''")):
                lines.append(stripped)
                current_hunk_lines.append(stripped)
            else:
                if len(current_hunk_lines) >= 2:
                    hunks.append("\n".join(current_hunk_lines))
                current_hunk_lines = []
        else:
            if len(current_hunk_lines) >= 2:
                hunks.append("\n".join(current_hunk_lines))
            current_hunk_lines = []
            
    if len(current_hunk_lines) >= 2:
        hunks.append("\n".join(current_hunk_lines))
        
    return lines, hunks

def get_base_source(repo_name: str, base_commit: str, target_file: str) -> str:
    bare_repo = UPSTREAM_CACHE / f"{repo_name.split('/')[1]}.git"
    cmd = ["git", f"--git-dir={bare_repo}", "show", f"{base_commit}:{target_file}"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

def main():
    print("[*] Starting Syntactic Gold Leakage & Multi-Line Block Audit across 15 frozen prompts...")
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

        added_lines, multi_line_hunks = extract_added_hunks_from_patch(gold_patch_path)
        base_source = get_base_source(repo, base_commit, target_file)
        problem_stmt = stmt_path.read_text(encoding="utf-8")
        test_patch_text = test_patch_path.read_text(encoding="utf-8")

        # 1. Check exact single line leakage unique to the gold patch
        leaked_lines = []
        for line in added_lines:
            if line in base_source or line in problem_stmt or line in test_patch_text:
                continue
            if line in user_prompt:
                leaked_lines.append(line)

        # 2. Check multi-line hunk block leakage
        leaked_blocks = []
        for hunk in multi_line_hunks:
            if hunk in base_source:
                continue
            if hunk in user_prompt:
                leaked_blocks.append(hunk)

        is_clean = (len(leaked_lines) == 0 and len(leaked_blocks) == 0)
        if not is_clean:
            total_violations += 1
            print(f"  [!] LEAKAGE DETECTED in {pf.name}: lines={leaked_lines}, blocks={len(leaked_blocks)}")
        else:
            print(f"  [✓] {pf.name}: 0 novel gold lines ({len(added_lines)} checked), 0 multi-line blocks ({len(multi_line_hunks)} checked)")

        audit_records.append({
            "prompt_file": pf.name,
            "instance_id": iid,
            "variant": variant,
            "checked_gold_lines_count": len(added_lines),
            "checked_multi_line_hunks_count": len(multi_line_hunks),
            "leaked_lines": leaked_lines,
            "leaked_blocks_count": len(leaked_blocks),
            "syntactic_leakage_verdict": "CLEAN_ZERO_EXACT_GOLD_CODE_MATCHES" if is_clean else "LEAKAGE_DETECTED",
            "scope_disclaimer": "Syntactic check certifies 0 exact single-line or multi-line gold code matches. Does not claim complete semantic isolation from natural language problem statements or test traceback frames."
        })

    report_file = ARCHIVE_DIR / "gold_leakage_audit_report.json"
    report_file.write_text(json.dumps(audit_records, indent=2), encoding="utf-8")

    assert total_violations == 0, f"Audit failed with {total_violations} leakage violations!"
    print(f"\n[✓] ALL 15 PROMPTS CERTIFIED: 0 exact gold code matches. Report written to {report_file.name}")

if __name__ == "__main__":
    main()
