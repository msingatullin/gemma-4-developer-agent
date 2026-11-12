#!/usr/bin/env python3
"""G0-SEARCH-006: five-variant command-only ablation on frozen nine DEV cases.

Stage A reads ONLY search outputs and user-visible issue-derived tokens.
Stage B runs separately and imports gold paths for offline hit@1/5 scoring.
NO Gemma inference, Kaggle submission or GPU.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time

PLAN_SHA = "a0673b12d821907ba4391f7684a5eafd962c73ef5b4dc091eb443b78c4f06226"
PREVIOUS_RAW_SHA = "58b050b73a64c18cdd741b8c947bc19ec20a48975588ad1a001572870b69d69a"
MANIFEST_SHA = "8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf"
VARIANTS = ("v15_original", "quote_only", "quote_casefold",
            "quote_casefold_filtered", "exp001a_current")
FILTERS = " ':!tests/**' ':!**/tests/**' ':!**/test_*.py' ':!docs/**' ':!**/docs/**' ':!examples/**' ':!**/examples/**'"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked(path: Path, expected: str):
    data=path.read_bytes()
    actual=sha(data)
    if actual!=expected:raise ValueError(f"source checksum mismatch: {path}: {actual}")
    return json.loads(data)


def commands(token, file_token):
    q=shlex.quote(token)
    original='git grep -n "'+token+'" -- *.py | head -20'
    quote_only='git grep -n "'+token+'" -- '+"'*.py' | head -20"
    quote_case='git grep -n -i -F '+q+" -- '*.py' | head -20"
    filtered='git grep -n -i -F '+q+" -- '*.py'"+FILTERS+" | head -20"
    if file_token:
        candidate="git ls-files '*.py' | grep -i -F "+shlex.quote(file_token)+" | grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10"
        is_filename=True
    else:
        candidate=filtered
        is_filename=False
    return dict(zip(VARIANTS,(original,quote_only,quote_case,filtered,candidate))),is_filename


def stage_a(a):
    if a.out.exists():raise FileExistsError(a.out)
    plan=checked(a.plan,PLAN_SHA)
    old=checked(a.old_raw,PREVIOUS_RAW_SHA)
    if len(plan["queries"])!=9 or len(old["cases"])!=9:raise ValueError("expected 9 frozen dev cases")
    oldmap={x["instance_id"]:x for x in old["cases"]}
    report={"experiment":"G0-SEARCH-006",
            "phase":"A: original sources and frozen issue-derived search only; no gold paths",
            "plan_sha256":PLAN_SHA,
            "g0_005_raw_sha256":PREVIOUS_RAW_SHA,
            "variants":VARIANTS,
            "cases":[]}
    for idx,q in enumerate(plan["queries"]):
        sid=q["instance_id"];base=oldmap[sid]
        workdir=a.worktree_root/f"{idx:02d}_{sid.replace('/','_')}"/"source"
        assert workdir.is_dir(),workdir
        check=subprocess.run(["git","rev-parse","HEAD^{tree}"],cwd=workdir,capture_output=True,text=True,check=True).stdout.strip()
        if check!=base["historical_tree"]:
            raise ValueError("Historical source tree mismatch "+sid)
        first=subprocess.run(["git","status","--porcelain"],cwd=workdir,capture_output=True,text=True,check=True)
        if first.stdout.strip():raise ValueError("Unexpected dirty tree before queries")
        commands_map,filenames=commands(q["content_token"],q["filename_token"])
        outcomes={}
        for label in VARIANTS:
            cmd=commands_map[label]
            begin=time.perf_counter()
            p=subprocess.run(["/bin/bash","-c",cmd],cwd=workdir,capture_output=True,text=True,timeout=10)
            if p.returncode!=0:raise RuntimeError(f"Command failure {sid}/{label}: {p.stderr[:250]}")
            rows=p.stdout.splitlines()
            unique=[]
            for line in rows:
                path=line if label=="exp001a_current" and filenames else line.partition(":")[0]
                if path and path not in unique:unique.append(path)
            if label=="v15_original" and p.stdout!=base["search_runs"][0]["stdout"]:
                raise RuntimeError("Original v15 output not reproduced: "+sid)
            if label=="exp001a_current" and p.stdout!=base["search_runs"][1]["stdout"]:
                raise RuntimeError("001A output not reproduced: "+sid)
            outcomes[label]={
                "command":cmd, "stdout":p.stdout, "stderr":p.stderr,
                "returncode":p.returncode, "unique_paths":unique,
                "n_lines":len(rows), "latency_seconds":round(time.perf_counter()-begin,5)
            }
        last=subprocess.run(["git","status","--porcelain"],cwd=workdir,capture_output=True,text=True,check=True)
        if last.stdout.strip():raise RuntimeError("Dirty tree after commands")
        report["cases"].append({
            "instance_id":sid,"split":"dev","repo":base["repo"],
            "historical_git_tree":check,"content_token":q["content_token"],
            "filename_token":q["filename_token"],"candidate_uses_filename_first":filenames,
            "bash_glob_expanded":base["shell_unquoted_glob_expands"],
            "all_source_tree_bytes_unchanged":True,
            "stdout_reproduced_exactly_for_v15_and_001a":True,
            "variants":outcomes
        })
        print(sid, {k:len(v["unique_paths"]) for k,v in outcomes.items()},flush=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("STAGE_A_SHA256",sha(a.out.read_bytes()),flush=True)


def patch_paths(diff: str):
    out=[]
    for m in re.finditer(r"^diff --git a/(.+?) b/(.+?)\s*$",diff,re.M):
        path=m.group(2)
        if path.endswith(".py") and path not in out:out.append(path)
    return out


def stage_b(a):
    if a.score.exists() or a.md.exists():raise FileExistsError("Do not overwrite scoring result")
    raw=json.loads(a.out.read_text())
    if raw["phase"]!="A: original sources and frozen issue-derived search only; no gold paths":
        raise ValueError("Raw not from unscored phase")
    manifest=checked(a.manifest,MANIFEST_SHA)
    tasks={x["instance_id"]:x for x in manifest["tasks"]}
    report={"experiment":"G0-SEARCH-006","phase":"B: offline gold scoring only after A fully frozen",
            "raw_sha256":sha(a.out.read_bytes()),"manifest_sha256":MANIFEST_SHA,
            "scope":"same nine selected DEV, no independent heldout, no model inference",
            "cases":[]}
    for c in raw["cases"]:
        task=tasks[c["instance_id"]]
        if task["split"]!="dev":raise ValueError("Heldout must not be scored")
        gold=patch_paths(task["gold_patch"])
        if not gold:raise ValueError("No source gold paths")
        measured={}
        for name in VARIANTS:
            paths=c["variants"][name]["unique_paths"]
            measured[name]={
                "hit1":bool(set(paths[:1])&set(gold)),
                "hit5":bool(set(paths[:5])&set(gold)),
                "first_gold_rank":next((i+1 for i,path in enumerate(paths) if path in gold),None),
                "unique_paths":paths,
                "n_lines":c["variants"][name]["n_lines"],
                "seconds":c["variants"][name]["latency_seconds"],
            }
        report["cases"].append({
            "instance_id":c["instance_id"],"gold_source_paths_offline_only":gold,
            "shell_glob_expands":c["bash_glob_expanded"],"measurements":measured,
        })
        print(c["instance_id"],{v:("HIT" if measured[v]["hit5"] else "MISS") for v in VARIANTS},flush=True)
    totals={}
    for variant in VARIANTS:
        by=[c["measurements"] for c in report["cases"]]
        totals[variant]={
            "hit1":sum(m[variant]["hit1"] for m in by),
            "hit5":sum(m[variant]["hit5"] for m in by),
            "losses_vs_v15":sum(m["v15_original"]["hit5"] and not m[variant]["hit5"] for m in by),
            "gains_vs_v15":sum(not m["v15_original"]["hit5"] and m[variant]["hit5"] for m in by),
            "losses_vs_full_001a":sum(m["exp001a_current"]["hit5"] and not m[variant]["hit5"] for m in by),
        }
    report["summary"]={"n":len(report["cases"]),"totals":totals}
    # Diagnostic choice only; 1/9 slack as pre-registered, no authorization.
    full=totals["exp001a_current"]["hit5"]
    selected=next((v for v in VARIANTS[1:] if totals[v]["hit5"]>=full-1 and
                  totals[v]["losses_vs_full_001a"]<=1),"exp001a_current")
    report["exploratory_simplest_retrieval_candidate"]=selected
    report["verdict"]="CPU_ABLATION_ONLY_NO_AGENT_SOLVE_OR_KAGGLE_SCORE"
    a.score.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    rows=[
        "# G0-SEARCH-006 — nine DEV issue search instruction ablations",
        "",
        "**Important:** same previously used dev tasks and manually selected issue tokens; exploratory retrieval only, not independent heldout or model solve rate.",
        "",
        "| Variant | Gold source hit@1 | Gold source hit@5 | Gains vs v15 | Losses vs v15 |",
        "|---|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        v=totals[variant]
        rows.append("| "+variant+" | "+str(v["hit1"])+"/9 | "+str(v["hit5"])+"/9 | "+str(v["gains_vs_v15"])+
                    " | "+str(v["losses_vs_v15"])+" |")
    rows += [
        "",
        "Exploratory simplest retrieval expression within the pre-registered <=1/9 slack from full 001A: **"+selected+"**.",
        "",
        "## Per-task gold-source hit@5",
        "",
        "| Task | V15 | quote only | quote+case | quote+case+filters | 001A |",
        "|---|---|---|---|---|---|",
    ]
    for c in report["cases"]:
        rows.append("| "+c["instance_id"]+" | "+" | ".join("✓" if c["measurements"][v]["hit5"] else "—" for v in VARIANTS)+" |")
    rows += [
        "",
        "All original and 001A command stdout reproduced **exactly** from the frozen G0-005 raw record. CPU subprocesses operated on original immutable Git trees without gold/test patches. Gold filenames were accessed only in the separate offline Stage B process.",
        "",
        "Query plan [G0-SEARCH-005](G0_SEARCH_005_FROZEN_QUERY_PLAN.json); this stage's [preregistered protocol](G0_SEARCH_006_PROTOCOL.md), [search raw output](G0_SEARCH_006_RAW.json), [offline score metadata](G0_SEARCH_006_SCORED.json).",
        "",
        "Never infer E4B solve-rate or Kaggle score gains from these retrieval metrics. No Kaggle send, paid GPU/API, or original submission changes.",
    ]
    a.md.write_text("\n".join(rows)+"\n")
    print("SCORED_SHA256",sha(a.score.read_bytes()),flush=True)
    print("SUMMARY",json.dumps(totals),flush=True)
    print("SIMPLER_CHOICE",selected,flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["search","score"],required=True)
    p.add_argument("--plan",type=Path)
    p.add_argument("--old-raw",type=Path)
    p.add_argument("--manifest",type=Path)
    p.add_argument("--worktree-root",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--score",type=Path)
    p.add_argument("--md",type=Path)
    a=p.parse_args()
    if a.mode=="search":
        assert a.plan and a.old_raw and a.worktree_root
        stage_a(a)
    else:
        assert a.manifest and a.score and a.md
        stage_b(a)


if __name__=="__main__":
    main()
