#!/usr/bin/env python3
"""Autonomous background orchestrator & telemetry engine for Gemma 4 Developer Agent sprint."""

import os
import sys
import json
import shutil
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

def get_submission_limits():
    check_code = """
from kaggle.api.kaggle_api_extended import KaggleApi
import json
api = KaggleApi()
api.authenticate()
lim = api.competition_get_submission_limits('gemma-4-developer-agent')
print(json.dumps(lim.to_dict()))
"""
    res = subprocess.run([KAGGLE_PYTHON, "-c", check_code], capture_output=True, text=True)
    if res.returncode == 0:
        for line in res.stdout.strip().splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
    return {"numAllowedNow": 0, "numToday": 1, "error": res.stderr}

def run_cycle():
    now_iso = datetime.now(timezone.utc).isoformat()
    report = [f"=== Gemma 4 AutoPilot Cycle at {now_iso} ==="]

    # 1. Validation check of latest candidate (v10_candidate)
    candidate_dir = WORKDIR / "v10_candidate"
    v_out, v_err, v_code = run_cmd(["python3", str(WORKDIR / "tools" / "validate_submission.py"), str(candidate_dir)])
    if v_code == 0:
        report.append("✓ v10_candidate submission candidate validated: PASS")
    else:
        report.append(f"✗ v10_candidate validation failed: {v_err or v_out}")

    # 2. Check main competition submissions status
    main_subs = check_main_submissions()
    report.append(f"\n--- Main Track Submissions ---\n{main_subs}")

    # 3. Check quota and automated daily submission queue
    target_zip = WORKDIR / "submission_v10_candidate.zip"
    staged_zip = WORKDIR / "submission.zip"
    limits = get_submission_limits()
    report.append(f"\n--- Quota Status ---\n{json.dumps(limits)}")

    if target_zip.exists():
        version_tag = "v10_candidate"
        allowed_now = limits.get("numAllowedNow", 0)
        if allowed_now > 0:
            print(f"[AutoPilot] Quota available! Staging {target_zip.name} as submission.zip for deployment...")
            shutil.copyfile(target_zip, staged_zip)
            sub_out, sub_err, sub_code = run_cmd([
                KAGGLE_CLI, "competitions", "submit", "-c", COMPETITION_MAIN,
                "-f", str(staged_zip),
                "-m", "v10: lean 6-tool SWE agent, 6m budget cap, eval_config.yaml, Thinking mode (4096 budget), python heredoc fallback, anti-loop discipline"
            ])
            if sub_code == 0 and "Successfully submitted" in sub_out:
                report.append(f"\n[AUTO-DEPLOY] Successfully deployed {target_zip.name}: {sub_out}")
                log_to_mmw_spool(f"AutoPilot Auto-Deployment {version_tag}", f"Deployed {version_tag} on quota reset:\n{sub_out}")
            else:
                report.append(f"\n[AUTO-DEPLOY-WAIT] Submitter response: {sub_out or sub_err}")
        else:
            report.append(f"\n[STAGED] {target_zip.name} staged as submission.zip. Awaiting daily quota reset at 00:00:00 UTC (allowed now: 0).")

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
