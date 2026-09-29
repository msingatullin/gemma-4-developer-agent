#!/usr/bin/env python3
"""Autonomous background orchestrator & telemetry engine for Gemma 4 Developer Agent sprint."""

import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone

KAGGLE_PYTHON = "/home/mikhail/Projects/kaggle-venv/bin/python"
KAGGLE_CLI = "/home/mikhail/Projects/kaggle-venv/bin/kaggle"
WORKDIR = Path("/home/mikhail/gemma-4-developer-agent")
SPOOL_DB = Path("/home/mikhail/.config/mmw/spool.db")

COMPETITION_MAIN = "gemma-4-developer-agent"
COMPETITION_PAPER = "gemma-4-developer-agent-paper"

ACTIVE_SUBMISSION_REF = "56660578"  # v1 baseline

def run_cmd(cmd, cwd=WORKDIR):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def log_to_mmw_spool(title, content):
    try:
        if not SPOOL_DB.parent.exists():
            SPOOL_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(SPOOL_DB)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("INSERT INTO local_memories (title, content) VALUES (?, ?)", (title, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[AutoPilot] MMW spool write error: {e}", file=sys.stderr)

def check_main_submissions():
    out, err, code = run_cmd([KAGGLE_CLI, "competitions", "submissions", "-c", COMPETITION_MAIN])
    if code != 0:
        return f"[Status] Error fetching submissions: {err}"
    return out

def run_cycle():
    now_iso = datetime.now(timezone.utc).isoformat()
    report = [f"=== Gemma 4 AutoPilot Cycle at {now_iso} ==="]

    # 1. Validation check of v2_dev candidate
    v_out, v_err, v_code = run_cmd(["python3", str(WORKDIR / "tools" / "validate_submission.py"), str(WORKDIR / "v2_dev")])
    if v_code == 0:
        report.append("✓ v2_dev submission candidate validated: PASS")
    else:
        report.append(f"✗ v2_dev validation failed: {v_err}")

    # 2. Check main competition submissions status
    main_subs = check_main_submissions()
    report.append(f"\n--- Main Track Submissions ---\n{main_subs}")

    # 3. Check automated daily submission queue for v2
    v2_zip = WORKDIR / "submission_v2.zip"
    if v2_zip.exists():
        v2_already = "v2" in main_subs
        if not v2_already:
            print(f"[AutoPilot] Checking if daily quota allows submission of {v2_zip.name}...")
            sub_out, sub_err, sub_code = run_cmd([
                KAGGLE_CLI, "competitions", "submit", "-c", COMPETITION_MAIN,
                "-f", str(v2_zip),
                "-m", "v2: bug_localizer subagent, thinking_budget 4096, eval_config budget expansion"
            ])
            if sub_code == 0 and "Successfully submitted" in sub_out:
                report.append(f"\n[AUTO-DEPLOY] Successfully deployed {v2_zip.name}: {sub_out}")
                log_to_mmw_spool("AutoPilot Auto-Deployment v2", f"Deployed v2 on quota reset:\n{sub_out}")
            else:
                report.append(f"\n[AUTO-DEPLOY-WAIT] Daily quota exhausted or waiting. Submitter response: {sub_out or sub_err}")

    # 4. Paper Track status
    report.append(f"\n--- Paper Track Status ---")
    report.append("Writeup: AST-Guided Loops: Deterministic Verification for Gemma 4 SWE Agents")
    report.append("URL: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/ast-guided-deterministic-gemma4-agent")
    report.append("Repo: https://github.com/msingatullin/gemma-4-developer-agent")

    content = "\n".join(report)
    print(content)
    log_to_mmw_spool("Gemma 4 Developer Agent Telemetry", content)
    return content

if __name__ == "__main__":
    run_cycle()
