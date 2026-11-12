#!/usr/bin/env python3
"""EXP-AGENT-GPU-001 F0: private bounded E4B W4A16 Kaggle T4x2 GPU feasibility.

This script never submits a competition entry, never publishes, never calls a
paid API, and does not load gold/test patches. Performs ONE short local E4B
completion from official attached model weights. This is NOT an agent solve.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

MODEL_SLUG = "gemma-4-e4b-it-qat-w4a16-ct"
MODEL_ID = "gemma-4-e4b-it-qat-w4a16-ct"
EXP = "EXP-AGENT-GPU-001-F0"
# Bound total T4 runtime: less than 900s of normal-rate GPU quota.
MAX_WALL_SECONDS = 850
OUTPUT = Path("/kaggle/working/gemma_agent_e4b_gpu001_f0.json")
PREFLIGHT = Path("/kaggle/working/gemma_agent_e4b_gpu001_f0_preflight.json")
START_FILE = Path("/kaggle/working/gemma_agent_e4b_gpu001_f0_start.txt")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json_atomic(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    draft=path.with_suffix(path.suffix+".tmp")
    draft.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(draft,path)


def start_time():
    if START_FILE.exists():
        return float(START_FILE.read_text())
    t=time.time()
    START_FILE.parent.mkdir(parents=True,exist_ok=True)
    START_FILE.write_text(str(t))
    return t


def seconds_left(t0):
    return MAX_WALL_SECONDS-(time.time()-t0)


def check_budget(t0, margin=20):
    remaining=seconds_left(t0)
    if remaining < margin:
        raise TimeoutError(f"F0 wall-clock budget exceeded; remaining={remaining:.1f}s")
    return remaining


def search_model_dir():
    root=Path("/kaggle/input")
    if not root.is_dir():raise RuntimeError("NO_KAGGLE_MODEL_ATTACHMENT")
    found=[]
    # Kaggle may nest models as /kaggle/input/models/google/gemma-4/other/<slug>/2/...
    for conf in root.rglob("config.json"):
        parent=str(conf.parent).lower()
        if MODEL_SLUG.lower() in parent and list(conf.parent.glob("*.safetensors")):
            found.append(conf.parent)
    if len(found)!=1:
        raise RuntimeError(f"EXPECTED_ONE_OFFICIAL_ATTACHED_E4B_W4A16_DIR found={len(found)} candidates={list(map(str,found[:4]))}")
    return found[0]


def check_gpu():
    import torch
    specs=[]
    for i in range(torch.cuda.device_count()):
        prop=torch.cuda.get_device_properties(i)
        specs.append({"name":prop.name,"memory_gib":round(prop.total_memory/2**30,2),"capability":list(torch.cuda.get_device_capability(i))})
    print("F0_T4_GPU_SPEC",json.dumps(specs),flush=True)
    if len(specs)!=2 or any("T4" not in row["name"] for row in specs):
        raise RuntimeError("Expected two ordinary T4 GPUs, do not switch to charged L4x4")
    return specs


def ensure_vllm(t0):
    from packaging.version import Version
    try:
        v=importlib.metadata.version("vllm")
    except importlib.metadata.PackageNotFoundError:
        v=None
    if v is not None and Version(v)>=Version("0.29.0"):
        print("F0_EXISTING_VLLM",v,flush=True)
        return False
    # Internet-enabled standard T4 only, pip package install; no paid model APIs.
    # Prior private owner T4 notebook successfully used this exact vLLM range
    # in a separate clean interpreter due old torch ABI.
    timeout=min(int(check_budget(t0,450)-110),460)
    if timeout < 120:raise RuntimeError("Not enough budget for vLLM install")
    print("F0_PIP_VLLM_START",v,timeout,flush=True)
    subprocess.run([sys.executable,"-m","pip","install","-q","--no-input","--disable-pip-version-check",
                    "vllm>=0.29.0,<0.31.0"],check=True,timeout=timeout)
    print("F0_PIP_VLLM_INSTALLED_EXEC_CLEAN_PROCESS",flush=True)
    os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),"--after-bootstrap"])


def optional_t4_triton_fix():
    import sysconfig
    target=Path(sysconfig.get_path("purelib"))/"vllm/v1/attention/ops/triton_unified_attention.py"
    if not target.is_file():
        print("F0_T4_TRITON_FILE_MISSING_SKIPPING",flush=True)
        return "SKIPPED"
    data=target.read_text()
    old_a="    # Default behavior\n    if is_prefill:\n        return 32\n"
    new_a="    # Default behavior\n    if is_prefill:\n        return 16  # T4 prefill shared-memory limit\n"
    old_b="    launch_kwargs: dict[str, int] = {}\n"
    new_b='    launch_kwargs: dict[str, int] = {"num_stages": 1}\n'
    if data.count(old_a)!=1 or data.count(old_b)!=1:
        print("F0_T4_TRITON_PATCH_NOT_APPLICABLE_NO_SOURCE_MODIFICATION",flush=True)
        return "NOT_APPLICABLE"
    modified=data.replace(old_a,new_a,1).replace(old_b,new_b,1)
    compile(modified,str(target),"exec")
    target.write_text(modified)
    print("F0_T4_TRITON_PATCH_APPLIED_EPHEMERAL",flush=True)
    return "APPLIED"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--after-bootstrap",action="store_true")
    args=ap.parse_args()
    t0=start_time()
    # This alarm persists across clean execv because it is a process timer.
    def kill_runtime(_signum,_frame):raise TimeoutError("F0 hard 850s wall cap")
    signal.signal(signal.SIGALRM,kill_runtime)
    signal.alarm(max(1,int(seconds_left(t0))))
    evidence={
        "experiment":EXP,"started_at_utc":utc(),
        "bound_seconds":MAX_WALL_SECONDS,"requested_model":MODEL_ID,
        "actual_model_generation":"NOT_DONE",
        "kaggle_competition_submission":"NEVER",
        "paid_api_calls":0,"status":"STARTED",
    }
    try:
        if OUTPUT.exists():raise FileExistsError("Refuse previous run result")
        gpus=check_gpu()
        model=search_model_dir()
        config_path=model/"config.json"
        print("F0_OFFICIAL_MODEL_MOUNT_FOUND",str(model),flush=True)
        evidence.update({
            "hardware":gpus,"model_mount":str(model),
            "model_config_sha256":digest(config_path),
            "model_weight_shards_count":len(list(model.glob("*.safetensors"))),
            "model_weights_names":[p.name for p in sorted(model.glob("*.safetensors"))][:30],
        })
        write_json_atomic(PREFLIGHT,evidence)
        check_budget(t0,margin=220)
        if not args.after_bootstrap:
            ensure_vllm(t0)
        import vllm
        from vllm import LLM,SamplingParams
        evidence["vllm_version"]=vllm.__version__
        evidence["ephemeral_t4_kernel_workaround"]=optional_t4_triton_fix()
        check_budget(t0,margin=180)
        before=time.monotonic()
        print("F0_E4B_LOADING",flush=True)
        llm=LLM(model=str(model),tokenizer=str(model),tensor_parallel_size=2,
                dtype="float16",max_model_len=8192,max_num_seqs=1,
                gpu_memory_utilization=0.88,enforce_eager=True,
                trust_remote_code=False,disable_log_stats=True)
        evidence["model_load_seconds"]=round(time.monotonic()-before,2)
        print("F0_E4B_LOAD_SUCCESS",evidence["model_load_seconds"],flush=True)
        check_budget(t0,margin=60)
        start=time.monotonic()
        messages=[
            {"role":"system","content":"You are a software engineering assistant. Answer briefly."},
            {"role":"user","content":"In one short sentence, explain why an unquoted *.py glob can restrict a git grep command to top-level Python files."},
        ]
        samples=llm.chat(messages,SamplingParams(temperature=0.0,max_tokens=120,top_p=1.0),
                         use_tqdm=False)
        text=samples[0].outputs[0].text
        evidence["generation_seconds"]=round(time.monotonic()-start,2)
        evidence["generated_text"]=text[:1400]
        evidence["generated_token_count"]=len(samples[0].outputs[0].token_ids)
        evidence["actual_model_generation"]="TRUE_LOCAL_E4B"
        evidence["status"]="PASS_GPU_REAL_E4B_ONE_SHORT_COMPLETION_NOT_AGENT_PATCH"
        print("F0_REAL_E4B_GENERATION",repr(text[:700]),flush=True)
    except Exception as ex:
        evidence["status"]="BLOCKED_F0_NO_AGENT_PATCH"
        evidence["error_type"]=type(ex).__name__
        evidence["error"]=str(ex)[:1500]
        print("F0_ERROR",type(ex).__name__,str(ex)[:700],flush=True)
    finally:
        evidence["ended_at_utc"]=utc()
        evidence["elapsed_wall_seconds"]=round(time.time()-t0,2)
        write_json_atomic(OUTPUT,evidence)
        print("F0_FINAL_STATUS",evidence["status"],flush=True)
        print("F0_RESULT_JSON_SHA256",digest(OUTPUT),flush=True)
        # At process termination child vLLM workers should be stopped by Kaggle kernel.


if __name__=="__main__":main()
