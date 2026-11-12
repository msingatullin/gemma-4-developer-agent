#!/usr/bin/env python3
"""G0-SEARCH-005: frozen 9-dev search diagnostics, then offline gold-path scoring.

This is NOT Gemma inference / SWE solving. Stage A records all search results
and exits. Stage B is a separate process and reads gold patch filenames
ONLY AFTER stage-A raw output has been saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import tarfile
import time
from pathlib import Path
from collections import Counter

MANIFEST_SHA256 = "8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf"
DEV_REPOS = {"pallets/flask", "psf/requests", "pytest-dev/pytest"}
CACHE = {
    "pallets/flask": "/opt/kaggle/gemma-paper-upstream/flask.git",
    "psf/requests": "/opt/kaggle/gemma-paper-upstream/requests.git",
    "pytest-dev/pytest": "/opt/kaggle/gemma-agent-g0-20261112-audit/g1_006_pytest_source/.git",
}
ORIGINAL_ANCHOR = 'git grep -n "SPECIFIC_TOKEN" -- *.py | head -20'
CANDIDATE_FILE_ANCHOR = "git ls-files '*.py' | grep -i -F"
CANDIDATE_CONTENT_ANCHOR = "git grep -n -i -F"


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get_manifest(path: Path):
    assert digest(path.read_bytes()) == MANIFEST_SHA256
    return {a["instance_id"]: a for a in json.loads(path.read_text())["tasks"]}


def command_out(cmd: list[str], cwd=None, timeout=30, strict=True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if strict and p.returncode:
        raise RuntimeError(f"Failed {cmd[:5]} code {p.returncode} {p.stderr[:450]}")
    return p


def check_clean(root: Path) -> None:
    p = command_out(["git", "status", "--porcelain"], root)
    if p.stdout.strip():
        raise RuntimeError(f"Source worktree became dirty: {p.stdout[:350]}")


def stage_search(a) -> None:
    if a.raw.exists() or a.output_dir.exists():
        raise FileExistsError("Refuse existing raw experiment or output directory")
    plan = json.loads(a.plan.read_text())
    if plan["experiment_id"] != "G0-SEARCH-005":
        raise ValueError("Plan ID mismatch")
    original_prompt = a.v15_prompt.read_text()
    candidate_prompt = a.candidate_prompt.read_text()
    assert ORIGINAL_ANCHOR in original_prompt
    assert CANDIDATE_FILE_ANCHOR in candidate_prompt
    assert CANDIDATE_CONTENT_ANCHOR in candidate_prompt
    manifest = get_manifest(a.manifest)
    assert len(plan["queries"]) == 9
    ids = [q["instance_id"] for q in plan["queries"]]
    assert len(set(ids)) == 9
    a.output_dir.mkdir(mode=0o700, parents=False)
    raw = {
        "id": "G0-SEARCH-005",
        "phase": "A: only issue-text queries and original source; do NOT read gold/test patches",
        "query_plan_sha256": digest(a.plan.read_bytes()),
        "manifest_sha256": MANIFEST_SHA256,
        "original_v15_prompt_sha256": digest(a.v15_prompt.read_bytes()),
        "candidate_001a_prompt_sha256": digest(a.candidate_prompt.read_bytes()),
        "cases": [],
    }
    for i, q in enumerate(plan["queries"]):
        sid = q["instance_id"]
        t = manifest[sid]
        if t["split"] != "dev" or t["repo"] not in DEV_REPOS:
            raise ValueError("Non-dev task or invalid source repo")
        statement = t["problem_statement"]
        token = q["content_token"]
        file_token = q["filename_token"]
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", token):
            raise ValueError("Unsafe token")
        if token.lower() not in statement.lower():
            raise ValueError(f"Content token not in issue statement: {sid} {token}")
        if file_token is not None:
            if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", file_token):
                raise ValueError("Unsafe filename token")
            if file_token.lower() not in statement.lower():
                raise ValueError(f"Filename token not in issue text: {sid} {file_token}")
        pin = t["base_commit"]
        repo = t["repo"]
        bare = CACHE[repo]
        historical_tree = command_out(
            ["git", "--git-dir=" + bare, "rev-parse", pin + "^{tree}"]
        ).stdout.strip()
        cwd = a.output_dir / f"{i:02d}_{sid.replace('/', '_')}"
        cwd.mkdir(mode=0o700)
        archived = cwd / "historical_source.tar"
        with archived.open("xb") as f:
            r = subprocess.run(["git", "--git-dir="+bare, "archive", pin], stdout=f, stderr=subprocess.PIPE, timeout=40)
            if r.returncode:
                raise RuntimeError("Pinned archive not found: " + repr(r.stderr[:350]))
        with tarfile.open(archived) as tar:
            infos = tar.getmembers()
            if any(Path(x.name).is_absolute() or ".." in Path(x.name).parts for x in infos):
                raise ValueError("Unsafe source archive")
            tar.extractall(cwd, filter="data")
        command_out(["git", "init", "-q"], cwd)
        command_out(["git", "add", "--force", "--all"], cwd)
        command_out(["git", "-c", "user.name=G0", "-c", "user.email=g0@example.invalid",
                     "commit", "-q", "-m", "Frozen source tree"], cwd)
        exact_tree = command_out(["git", "rev-parse", "HEAD^{tree}"], cwd).stdout.strip()
        if exact_tree != historical_tree:
            raise RuntimeError(f"Tracked source SHA mismatch {sid}: {exact_tree} != {historical_tree}")
        original_cmd = 'git grep -n "' + token + '" -- *.py | head -20'
        if file_token:
            candidate_cmd = (
                "git ls-files '*.py' | grep -i -F " + shlex.quote(file_token)
                + " | grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10"
            )
            candidate_mode = "filename_first"
        else:
            candidate_cmd = (
                "git grep -n -i -F " + shlex.quote(token) +
                " -- '*.py' ':!tests/**' ':!**/tests/**' ':!**/test_*.py' "
                "':!docs/**' ':!**/docs/**' ':!examples/**' ':!**/examples/**' | head -20"
            )
            candidate_mode = "filtered_content"
        out = []
        for label, cmd in [("baseline_v15", original_cmd), ("candidate_001a", candidate_cmd)]:
            time_start = time.perf_counter()
            p = command_out(["/bin/bash", "-c", cmd], cwd, timeout=10, strict=True)
            rows = p.stdout.splitlines()
            # Unique file paths returned in order (line count may include duplicates).
            paths = []
            for row in rows:
                path = (row.partition(":")[0] if label == "baseline_v15"
                        or candidate_mode == "filtered_content" else row)
                if path and path not in paths:
                    paths.append(path)
            out.append({
                "name": label, "command": cmd, "returncode": p.returncode,
                "output_lines": len(rows), "unique_paths": paths,
                "stdout": p.stdout, "stderr": p.stderr,
                "elapsed_seconds": round(time.perf_counter()-time_start, 5),
            })
        check_clean(cwd)
        # Shell's unquoted *.py can expand to root Python files in some repos.
        root_files = sorted(p.name for p in cwd.glob("*.py") if p.is_file())
        entry = {
            "instance_id": sid,
            "split": t["split"],
            "repo": repo,
            "pin": pin,
            "historical_tree": historical_tree,
            "source_tar_sha256": digest(archived.read_bytes()),
            "issue_content_token": token,
            "issue_filename_token": file_token,
            "candidate_mode": candidate_mode,
            "root_py_files": root_files,
            "shell_unquoted_glob_expands": bool(root_files),
            "search_runs": out,
            "workspace_clean": True,
        }
        raw["cases"].append(entry)
        print(sid, candidate_mode, "base",len(out[0]["unique_paths"]), "candidate",len(out[1]["unique_paths"]),flush=True)
    a.raw.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    print("STAGE_A_RAW_SHA256", digest(a.raw.read_bytes()), flush=True)


def patch_paths(patch: str) -> list[str]:
    paths = []
    for match in re.finditer(r"^diff --git a/(.+?) b/(.+?)\s*$", patch, re.M):
        name = match.group(2)
        if name.endswith(".py") and name not in paths:
            paths.append(name)
    return paths


def stage_score(a) -> None:
    if a.score.exists() or a.markdown.exists():
        raise FileExistsError("Refuse overwrite scored run")
    raw = json.loads(a.raw.read_text())
    if raw["phase"] != "A: only issue-text queries and original source; do NOT read gold/test patches":
        raise ValueError("Expected unscored stage A")
    manifest = get_manifest(a.manifest)
    scored = {
        "id": "G0-SEARCH-005",
        "phase": "B: offline gold path evaluation AFTER stage A frozen",
        "unscored_raw_sha256": digest(a.raw.read_bytes()),
        "manifest_sha256": MANIFEST_SHA256,
        "dev_scope_only": True,
        "model_calls": 0,
        "kaggle_submissions": 0,
        "cases": [],
    }
    counts = Counter()
    for case in raw["cases"]:
        instance_id = case["instance_id"]
        t = manifest[instance_id]
        if t["split"] != "dev":
            raise ValueError("Heldout in developer benchmark")
        targets = patch_paths(t["gold_patch"])
        if not targets:
            raise ValueError("No Gold Python source paths for " + instance_id)
        if [x["name"] for x in case["search_runs"]] != ["baseline_v15", "candidate_001a"]:
            raise ValueError("Unexpected retrieval cases")
        outcomes = []
        for r in case["search_runs"]:
            all_paths = r["unique_paths"]
            found = [p for p in all_paths if p in targets]
            outcomes.append({
                "name": r["name"],
                "gold_target_paths": targets,
                "top1_any_gold": bool(all_paths[:1] and set(all_paths[:1]) & set(targets)),
                "top5_any_gold": bool(set(all_paths[:5]) & set(targets)),
                "top10_any_gold": bool(set(all_paths[:10]) & set(targets)),
                "top5_all_gold": set(targets).issubset(set(all_paths[:5])),
                "first_gold_rank_in_unique_paths":
                    min((all_paths.index(p)+1 for p in found), default=None),
                "returned_unique_paths": all_paths,
                "raw_line_count": r["output_lines"],
                "elapsed_seconds": r["elapsed_seconds"],
            })
        b = outcomes[0]["top5_any_gold"]
        c = outcomes[1]["top5_any_gold"]
        tag = "gain" if (not b and c) else ("regression" if (b and not c) else "tie")
        counts[tag] += 1
        scored["cases"].append({
            "instance_id": instance_id,
            "repo": case["repo"],
            "historical_tree": case["historical_tree"],
            "content_token": case["issue_content_token"],
            "filename_token": case["issue_filename_token"],
            "candidate_mode": case["candidate_mode"],
            "baseline_shell_unquoted_py_glob_expands": case["shell_unquoted_glob_expands"],
            "gold_path_offline_only": targets,
            "retrieval_outcomes": outcomes,
            "pairwise_hit_at5": tag,
        })
        print(instance_id, "gold",targets, "baseline@5",b, "candidate@5",c,tag,flush=True)
    scored["summary"] = {
        "n": len(scored["cases"]),
        "hit5_baseline": sum(c["retrieval_outcomes"][0]["top5_any_gold"] for c in scored["cases"]),
        "hit5_candidate": sum(c["retrieval_outcomes"][1]["top5_any_gold"] for c in scored["cases"]),
        "hit1_baseline": sum(c["retrieval_outcomes"][0]["top1_any_gold"] for c in scored["cases"]),
        "hit1_candidate": sum(c["retrieval_outcomes"][1]["top1_any_gold"] for c in scored["cases"]),
        "gains": counts["gain"], "regressions": counts["regression"], "ties": counts["tie"],
        "net_hit5_delta": counts["gain"] - counts["regression"],
        "root_glob_expansion_count": sum(c["baseline_shell_unquoted_py_glob_expands"] for c in scored["cases"]),
    }
    s = scored["summary"]
    scored["preregistered_pilot_gate"] = {
        "condition": "net hit@5 delta >=2 AND regressions <=1 across all 9 DEV cases",
        "passed": s["net_hit5_delta"] >= 2 and s["regressions"] <= 1,
        "decision": "PROMISING_RETRIEVAL_ONLY" if s["net_hit5_delta"] >= 2 and s["regressions"] <= 1
            else "HOLD_REWORK_RETRIEVAL_ONLY",
    }
    a.score.write_text(json.dumps(scored, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# G0-SEARCH-005 — 9 pinned real DEV issue retrieval comparison",
        "",
        "**This is file retrieval, not E4B inference, SWE solve rate, public score, or an approval to submit.**",
        "",
        "The issue-only queries were committed before gold-path scoring. [Protocol](G0_SEARCH_005_PROTOCOL.md), [frozen queries](G0_SEARCH_005_FROZEN_QUERY_PLAN.json).",
        "",
        "| Task | Gold source path(s), offline only | v15 top5 | 001A top5 | Delta |",
        "|---|---|---|---|---|",
    ]
    for c in scored["cases"]:
        outcomes = c["retrieval_outcomes"]
        lines.append("| " + c["instance_id"] + " | " + ", ".join(c["gold_path_offline_only"]) +
         " | " + ("HIT" if outcomes[0]["top5_any_gold"] else "MISS") +
         " | " + ("HIT" if outcomes[1]["top5_any_gold"] else "MISS") +
         " | " + c["pairwise_hit_at5"] + " |")
    lines += [
        "",
        "## Frozen metric summary",
        "",
        "- v15 hit@5: **"+str(s["hit5_baseline"])+"/9**; candidate hit@5: **"+str(s["hit5_candidate"])+"/9**.",
        "- v15 hit@1: **"+str(s["hit1_baseline"])+"/9**; candidate hit@1: **"+str(s["hit1_candidate"])+"/9**.",
        "- Wins/ties/losses at hit@5: **"+str(s["gains"])+"/"+str(s["ties"])+"/"+str(s["regressions"])+"**.",
        "- Cases where shell unquoted \`*.py\` expanded to root filenames: **"+str(s["root_glob_expansion_count"])+"/9**.",
        "- Pre-registered pilot gate: **"+scored["preregistered_pilot_gate"]["decision"]+"**.",
        "",
        "Gold path filenames are used solely in this OFFLINE scoring stage after CPU search outputs were saved; all nine cases are DEV. Tokens manually chosen from issue statements, not model-generated; these diagnostics cannot substitute for actual paired E4B patch solve validation. Raw stdout/runtime and Git tree checks: [G0_SEARCH_005_RAW.json](G0_SEARCH_005_RAW.json); gold-scored metadata: [G0_SEARCH_005_SCORED.json](G0_SEARCH_005_SCORED.json).",
        "",
        "Original Kaggle E4B v15 score 0.06 preserved, candidate 001A not submitted. No GPU/API/spend/submission.",
    ]
    a.markdown.write_text("\n".join(lines) + "\n")
    print("STAGE_B_SCORED_SHA256", digest(a.score.read_bytes()), flush=True)
    print("SUMMARY",json.dumps(scored["summary"]),flush=True)
    print("VERDICT",scored["preregistered_pilot_gate"]["decision"],flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["search","score"], required=True)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--v15-prompt", type=Path)
    ap.add_argument("--candidate-prompt", type=Path)
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--score", type=Path)
    ap.add_argument("--markdown", type=Path)
    a = ap.parse_args()
    if a.stage=="search":
        for x in (a.plan,a.v15_prompt,a.candidate_prompt,a.output_dir):
            if x is None:raise ValueError("Missing search prerequisite")
        stage_search(a)
    else:
        for x in (a.score,a.markdown):
            if x is None:raise ValueError("Missing scoring output")
        stage_score(a)


if __name__ == "__main__":
    main()
