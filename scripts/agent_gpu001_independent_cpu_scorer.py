#!/usr/bin/env python3
"""Independent CPU F2P/P2P scorer for REAL model-generated patch bundles only.

Requires external Kaggle GPU001 F1 result bundle with model-generated patches.
NO gold source patch is read or applied. Gold is used only in prior G1 oracle.
Never runs a model, never submits Kaggle, no network in test Docker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

TASK_ID = "pytest-dev__pytest-11143"
HISTORIC_SOURCE_COMMIT = "6995257cf470d2143ad1683824962de4071c0eb7"
HISTORIC_TREE = "5e87fec76a0ead331441eaf05a1510c6c6efe6cf"
ARMS = {
    "v15": "f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a",
    "exp002_quote_only": "90601ff0fbcd805e6e4a72b9767a464c5b56c4657d09897a8770ee475777882f",
    "exp001a_search_rewrite": "5a93228a86397ae247e3b3395ae82cc31d4f724f23a083ca18a0926dfc79cde0",
}
F2P = ("testing/test_assertrewrite.py::TestIssue11140::test_constant_not_picked_as_module_docstring",)
P2P = (
    "testing/test_assertrewrite.py::TestAssertionRewrite::test_place_initial_imports",
    "testing/test_assertrewrite.py::TestAssertionRewrite::test_location_is_set",
)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 30):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def source_tree(p: Path):
    q=run(["git","rev-parse","HEAD^{tree}"],cwd=p)
    if q.returncode:raise RuntimeError("Cannot read original historical Git tree")
    return q.stdout.strip()


def safe_patch(raw: str):
    if not isinstance(raw,str) or not raw.strip():
        return None,"EMPTY_MODEL_PATCH"
    diff=raw.replace("\r\n","\n")
    if not diff.startswith("diff --git a/"):
        return None,"NOT_A_GIT_DIFF"
    parts=re.findall(r"^diff --git a/(.+?) b/(.+?)\s*$",diff,re.M)
    if not parts:
        return None,"NO_DIFF_FILES"
    for src,dst in parts:
        if src != dst:
            return None,"RENAMING_NOT_ALLOWED_IN_FIRST_PILOT"
        path=Path(src)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0]==".git":
            return None,"UNSAFE_PATH"
        if str(path).startswith(("testing/","tests/","test/")) or path.name.startswith(("test_","conftest.")):
            return None,"PROTECTED_TEST_FILE"
        if path.suffix != ".py":
            return None,"ONLY_PYTHON_SOURCE_CHANGES_ALLOWED_IN_FIRST_PILOT"
    if len(diff.encode())>250_000:
        return None,"PATCH_TOO_LARGE"
    return diff,None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu-output",type=Path,required=True)
    parser.add_argument("--original-source",type=Path,required=True)
    parser.add_argument("--test-patch",type=Path,required=True)
    parser.add_argument("--original-version-artifact",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    if args.output_dir.exists():raise FileExistsError("Refuse to overwrite prior score")
    bundle=json.loads(args.gpu_output.read_text())
    if bundle.get("task_id")!=TASK_ID:raise ValueError("Unexpected dev issue")
    entries=bundle.get("arms",[])
    labels=[x.get("arm") for x in entries]
    if len(set(labels))!=len(labels) or not set(labels).issubset(ARMS):
        raise ValueError("Unregistered arms")
    if source_tree(args.original_source)!=HISTORIC_TREE:raise ValueError("Historical Git tree mismatch")
    if run(["git","status","--porcelain"],cwd=args.original_source).stdout.strip():
        raise ValueError("Original source unexpectedly dirty")
    if not args.test_patch.is_file() or not args.original_version_artifact.is_file():
        raise ValueError("Missing private evaluator fixtures")
    args.output_dir.mkdir(mode=0o700,parents=True)
    results={
        "id":"EXP-AGENT-GPU-001-OFFLINE-CPU-PATCH-SCORE",
        "gpu_bundle_sha256":sha(args.gpu_output.read_bytes()),
        "task_id":TASK_ID,
        "original_source_sha":HISTORIC_TREE,
        "test_patch_sha256":sha(args.test_patch.read_bytes()),
        "original_generated_version_artifact_sha256":sha(args.original_version_artifact.read_bytes()),
        "model_calls":0,
        "kaggle_submissions":0,
        "no_gold_source_patch_applied":True,
        "arms":[],
    }
    for item in entries:
        arm=item["arm"]
        row={
            "arm":arm,"baseline_submission_zip_sha256":ARMS[arm],
            "gpu_patch_sha256_declared":item.get("patch_sha256"),
            "gpu_model_name":item.get("model_name"),
            "source":"MODEL_GENERATED_PATCH_ONLY",
        }
        results["arms"].append(row)
        if item.get("source_zip_sha256")!=ARMS[arm]:
            row["status"]="REJECT_WRONG_SOURCE_ARCHIVE";continue
        if not item.get("model_generated",False):
            row["status"]="REJECT_NOT_MODEL_GENERATED";continue
        patch,problem=safe_patch(item.get("patch",""))
        if problem:
            row["status"]="REJECT_"+problem;continue
        digest=sha(patch.encode())
        if item.get("patch_sha256")!=digest:
            row["status"]="REJECT_MODEL_PATCH_SHA_MISMATCH";continue
        workspace=args.output_dir/arm
        shutil.copytree(args.original_source,workspace,symlinks=True)
        if source_tree(workspace)!=HISTORIC_TREE:raise ValueError("Scratch tree mismatch")
        temp=workspace.parent/(arm+".model.patch")
        temp.write_text(patch)
        check=run(["git","apply","--check",str(temp)],cwd=workspace)
        if check.returncode!=0:
            row["status"]="REJECT_UNAPPLICABLE_MODEL_PATCH"
            row["error"]=check.stderr[:500]
            continue
        applied=run(["git","apply",str(temp)],cwd=workspace)
        if applied.returncode:
            row["status"]="REJECT_APPLY_FAILED";continue
        # Only after model patch frozen and applied, add OFFLINE test patch;
        # gold-patch source is intentionally never supplied or accessed here.
        test_check=run(["git","apply","--check",str(args.test_patch)],cwd=workspace)
        if test_check.returncode:
            row["status"]="TEST_PATCH_CONFLICT"
            row["error"]=test_check.stderr[:500]
            continue
        patch_result=run(["git","apply",str(args.test_patch)],cwd=workspace)
        if patch_result.returncode:
            row["status"]="TEST_PATCH_APPLY_FAILED";continue
        artifact=workspace/"src/_pytest/_version.py"
        if artifact.exists() and artifact.read_bytes()!=args.original_version_artifact.read_bytes():
            row["status"]="MODEL_CHANGED_BUILD_METADATA";continue
        if not artifact.exists():
            artifact.write_bytes(args.original_version_artifact.read_bytes())
        row["tests"]=[]
        for label,selectors in [("F2P",F2P),("P2P",P2P)]:
            cmd=[
                "docker","run","--rm","--network","none","--read-only","--cpus","1",
                "--memory","768m","--pids-limit","64","--tmpfs","/tmp:rw,size=128m",
                "--mount",f"type=bind,src={workspace},dst=/workspace,readonly",
                "-w","/workspace","-e","PYTHONPATH=/workspace/src:/workspace",
                "-e","PYTHONDONTWRITEBYTECODE=1","--entrypoint","python",
                "gemma-paper-cpu:py311-20261110","-m","pytest","-p","no:cacheprovider",
                "-q","--tb=short",*selectors,
            ]
            started=time.monotonic()
            try:
                p=run(cmd,timeout=70)
                rc=p.returncode;stdout=p.stdout;stderr=p.stderr;timeout=False
            except subprocess.TimeoutExpired as e:
                rc=124;stdout=e.stdout.decode(errors="replace") if isinstance(e.stdout,bytes) else e.stdout or ""
                stderr=e.stderr.decode(errors="replace") if isinstance(e.stderr,bytes) else e.stderr or ""
                timeout=True
            evidence=args.output_dir/(arm+"_"+label+".log")
            evidence.write_text(f"EXIT={rc}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            row["tests"].append({
                "suite":label,"selectors":selectors,"exit":rc,"timed_out":timeout,
                "elapsed_seconds":round(time.monotonic()-started,3),
                "log_sha256":sha(evidence.read_bytes()),
                "stdout_tail":stdout[-1400:],"stderr_tail":stderr[-600:],
            })
        row["status"]="SOLVED_SELECTED_F2P_P2P" if all(x["exit"]==0 for x in row["tests"]) else "NOT_SOLVED_SELECTED_F2P_P2P"
    results["paired_complete"]=sorted(labels)==sorted(ARMS) and len(entries)==len(ARMS)
    results["n_solved"]=sum(x["status"]=="SOLVED_SELECTED_F2P_P2P" for x in results["arms"])
    path=args.output_dir/"GPU001_OFFLINE_SCORING.json"
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")
    print("RESULTS",[(r["arm"],r["status"]) for r in results["arms"]])
    print("PAIRED_COMPLETE",results["paired_complete"],"N_SOLVED",results["n_solved"])
    print("RESULT_SHA256",sha(path.read_bytes()))


if __name__=="__main__":
    main()
