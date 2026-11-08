#!/usr/bin/env python3
"""
Generate Frozen Evaluation Prompts for Authentic Upstream Holdout (Phase 1/2)
Generates 15 blinded, frozen prompts (5 tasks x 3 variants: A_raw, B2_assertion_aware, C_tail35).
CRITICAL: Guarantees zero reference solution (gold patch) leakage into prompt text.
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PAPER_DIR = REPO_ROOT / "paper"
TRACEBACK_EXP_DIR = PAPER_DIR / "traceback_experiment"
sys.path.insert(0, str(PAPER_DIR))
sys.path.insert(0, str(TRACEBACK_EXP_DIR))

from real_traceback_benchmark import naive_tail_cap
from traceback_compressor import filter_pytest_log_v2

ARCHIVE_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment" / "real_repo_sample"
PROMPTS_DIR = ARCHIVE_DIR / "frozen_prompts"
WORK_DIR = Path("/tmp/real_tasks_cpu_eval")
UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")

SYSTEM_PROMPT = """You are an expert autonomous software engineer working with Gemma 4.
Your goal is to inspect the repository defect description, the source code of the affected module, and the failing test traceback, determine the exact root cause of the defect, and provide the minimal correct code fix.

Respond strictly in the following format:
DEFECT_LOCATION: <exact function, method, or class name where the defect resides>
ROOT_CAUSE: <a concise 1-3 sentence explanation of the defect and why the test failed>
PROPOSED_CODE:
```python
<complete revised implementation of the target function or file>
```"""

def get_base_source_code(repo_name: str, base_commit: str, target_rel_path: str) -> str:
    # Read target file directly from bare git repository at base_commit (GUARANTEED ZERO PATCHES)
    bare_repo = UPSTREAM_CACHE / f"{repo_name.split('/')[1]}.git"
    assert bare_repo.exists(), f"Bare repo not found: {bare_repo}"
    cmd = ["git", f"--git-dir={bare_repo}", "show", f"{base_commit}:{target_rel_path}"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout

def main():
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = ARCHIVE_DIR / "cpu_verification_results.jsonl"
    assert jsonl_path.exists(), f"Missing verification results: {jsonl_path}"

    with open(jsonl_path, "r", encoding="utf-8") as f:
        tasks = [json.loads(line) for line in f if line.strip()]

    print(f"[*] Generating frozen prompts for {len(tasks)} verified upstream tasks...")
    records = []
    comparison_stats = []

    for t in tasks:
        iid = t["instance_id"]
        task_dir = ARCHIVE_DIR / iid
        stmt = (task_dir / "problem_statement.txt").read_text(encoding="utf-8").strip()
        raw_traceback = (task_dir / "raw_failure_traceback.txt").read_text(encoding="utf-8").strip()
        source_code = get_base_source_code(t["repo"], t["base_commit"], t["target_file"])

        # Traceback variants
        var_a = raw_traceback
        var_b2 = filter_pytest_log_v2(raw_traceback)
        var_c = naive_tail_cap(raw_traceback, 35)

        variants = [
            ("A_raw", var_a),
            ("B2_assertion_aware", var_b2),
            ("C_tail35", var_c)
        ]

        # Calculate token / char compression stats
        red_pct = (1 - len(var_b2) / len(var_a)) * 100
        comparison_stats.append({
            "instance_id": iid,
            "raw_chars": len(var_a),
            "raw_lines": len(var_a.splitlines()),
            "b2_chars": len(var_b2),
            "b2_lines": len(var_b2.splitlines()),
            "c_chars": len(var_c),
            "c_lines": len(var_c.splitlines()),
            "b2_char_reduction_pct": round(red_pct, 2)
        })

        for variant_name, trace_text in variants:
            user_prompt = f"""# Task: {iid}
## Upstream Repository: {t['repo']} (base commit: {t['base_commit']})
## Affected Source File: `{t['target_file']}`

## Problem Statement:
{stmt}

## Source Code (`{t['target_file']}`):
```python
{source_code}
```

## Test Failure Traceback ({variant_name}):
```text
{trace_text}
```

Analyze the failure and traceback, identify the exact defect location, explain the root cause, and provide the corrected implementation for `{t['target_file']}`.
"""
            prompt_sha = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()
            record = {
                "instance_id": iid,
                "variant": variant_name,
                "repo": t["repo"],
                "base_commit": t["base_commit"],
                "target_file": t["target_file"],
                "f2p_tests": t["f2p_tests"],
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "user_prompt_sha256": prompt_sha,
                "prompt_char_len": len(user_prompt),
                "trace_char_len": len(trace_text),
                "trace_line_count": len(trace_text.splitlines())
            }
            records.append(record)

            out_file = PROMPTS_DIR / f"{iid}__{variant_name}.json"
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
            print(f"  [+] Saved {out_file.name} (SHA256: {prompt_sha[:10]}..., {len(user_prompt)} chars)")

    # Save prompt manifest
    manifest_file = PROMPTS_DIR / "frozen_prompts_manifest.json"
    manifest_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    # Save variant statistics
    stats_file = ARCHIVE_DIR / "variant_compression_stats.json"
    stats_file.write_text(json.dumps(comparison_stats, indent=2), encoding="utf-8")

    print(f"\n[✓] Successfully generated {len(records)} frozen prompts in {PROMPTS_DIR}")
    print("\n--- Traceback Compression Stats on Real Repos ---")
    for s in comparison_stats:
        print(f"  {s['instance_id']:<22} | Raw: {s['raw_chars']}c ({s['raw_lines']}L) | B2: {s['b2_chars']}c ({s['b2_lines']}L) -> -{s['b2_char_reduction_pct']}% | C: {s['c_chars']}c ({s['c_lines']}L)")

if __name__ == "__main__":
    main()
