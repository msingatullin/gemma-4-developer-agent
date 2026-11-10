#!/usr/bin/env python3
"""Gemma Paper: free Kaggle T4 x2, authentic upstream inference, COLLECT ONLY.

This script NEVER executes model output. It reads only 15 preregistered
frozen A/B2/C prompts, uses attached official Kaggle Gemma 4 31B QAT
W4A16 compressed-tensors model, and writes incremental JSONL.

Hard stop: missing 2 GPUs, missing model, unsupported vLLM, expired budget,
invalid prompt SHA, or any inference error. No Kaggle competition submission.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import Request, urlopen

MODEL_ID = "google/gemma-4-31B-it-qat-w4a16-ct"
FROZEN_COMMIT = "1ccd44df721b9f3b4af14824e90544f6cdba4a9e"
CASES = (
    "pallets__flask-4045",
    "pallets__flask-4992",
    "pallets__flask-5063",
    "psf__requests-1963",
    "psf__requests-2148",
)
VARIANTS = ("A_raw", "B2_assertion_aware", "C_tail35")
MAX_NEW_TOKENS = 2048
CONTEXT_LIMIT = 16384
TIME_BUDGET_SECONDS = 50 * 60
OUTPUT = Path("/kaggle/working/gemma4_real5_collect_only.jsonl") if Path("/kaggle").exists() else Path("/tmp/gemma4_real5_collect_only.jsonl")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(x):
    return hashlib.sha256(x).hexdigest()


def read_frozen(case, variant, local_root=None):
    name = f"{case}__{variant}.json"
    if local_root is not None:
        file = Path(local_root) / name
        if file.is_file():
            return json.loads(file.read_text(encoding="utf-8"))
    url = ("https://raw.githubusercontent.com/msingatullin/"
           "gemma-4-developer-agent/" + FROZEN_COMMIT +
           "/paper/e2e_gemma_experiment/real_repo_sample/frozen_prompts/" + name)
    with urlopen(Request(url, headers={"User-Agent": "Gemma4PaperAudit/1.0"}), timeout=35) as r:
        return json.loads(r.read().decode("utf-8"))


def load_inputs(local_root=None):
    result = {}
    for case in CASES:
        for variant in VARIANTS:
            x = read_frozen(case, variant, local_root)
            assert x.get("instance_id") == case, (case, variant, "bad instance")
            assert x.get("variant") == variant, (case, variant, "bad variant")
            user = x.get("user_prompt", "")
            system = x.get("system_prompt", "")
            assert user and system, (case, variant, "empty input")
            assert sha256(user.encode("utf-8")) == x.get("user_prompt_sha256"), (
                case, variant, "frozen input SHA256 mismatch")
            result[(case, variant)] = x
    assert len(result) == 15
    return result


def model_dir():
    root = Path("/kaggle/input")
    if not root.is_dir():
        raise RuntimeError("Expected an attached Kaggle Model under /kaggle/input")
    matches = []
    for config in root.rglob("config.json"):
        path = str(config.parent).lower()
        if "gemma-4-31b-it-qat-w4a16-ct" in path:
            matches.append(config.parent)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one Kaggle-attached 31B W4A16 model directory; got {matches[:5]}")
    if not list(matches[0].glob("*.safetensors")):
        raise RuntimeError("Model config present, but safetensor weights not mounted")
    return matches[0]


def verify_gpus():
    import torch
    count = torch.cuda.device_count()
    specs = []
    for i in range(count):
        p = torch.cuda.get_device_properties(i)
        specs.append({"name": p.name, "memory_gib": round(p.total_memory / 2**30, 2),
                      "compute_capability": list(torch.cuda.get_device_capability(i))})
    print("GPU_CHECK", json.dumps(specs), flush=True)
    if count != 2:
        raise RuntimeError("Require exactly two GPUs for TP=2, got " + str(count))
    if any(x["memory_gib"] < 14.0 for x in specs):
        raise RuntimeError("GPU VRAM insufficient for tested 2xT4 configuration")
    return specs


def load_backend(path):
    try:
        import vllm
        from packaging.version import Version
        if Version(vllm.__version__) < Version("0.29.0"):
            raise ImportError("vLLM too old for this Gemma 4 trial")
    except ImportError:
        # Only inside the user's free Kaggle notebook; never on the host VPS.
        print("VLLM_INSTALL_START: free Kaggle runtime only", flush=True)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--no-input",
             "--disable-pip-version-check", "vllm>=0.29.0,<0.31.0"],
            check=True, timeout=540,
        )
        import importlib
        importlib.invalidate_caches()
        import vllm
    from vllm import LLM, SamplingParams
    print("VLLM_VERSION", vllm.__version__, flush=True)
    llm = LLM(
        model=str(path),
        tokenizer=str(path),
        tensor_parallel_size=2,
        dtype="float16",  # T4 does not support bfloat16
        max_model_len=CONTEXT_LIMIT,
        max_num_seqs=1,
        gpu_memory_utilization=0.88,
        enforce_eager=True,
        trust_remote_code=False,
        disable_log_stats=True,
    )
    return llm, SamplingParams(temperature=0.0, top_p=1.0, max_tokens=MAX_NEW_TOKENS)


def checked_append(record):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def completed_keys():
    if not OUTPUT.exists():
        return set()
    seen = set()
    for line in OUTPUT.read_text(encoding="utf-8").splitlines():
        x = json.loads(line)
        if x.get("status") == "ok":
            seen.add((x["instance_id"], x["variant"]))
    return seen


def run(local_root):
    signal.alarm(TIME_BUDGET_SECONDS + 120)
    started = time.monotonic()
    inputs = load_inputs(local_root)
    print("FROZEN_INPUTS_VERIFIED", len(inputs), "COMMIT", FROZEN_COMMIT, flush=True)
    gpus = verify_gpus()
    path = model_dir()
    print("ATTACHED_OFFICIAL_MODEL", str(path), flush=True)
    llm, sampling = load_backend(path)
    done = completed_keys()
    print("CHECKPOINT_ALREADY_COMPLETED", len(done), flush=True)
    total = 0
    for i, case in enumerate(CASES):
        # Rotating order avoids a systematic variant-vs-warm-up confound.
        rotation = VARIANTS[i % len(VARIANTS):] + VARIANTS[:i % len(VARIANTS)]
        for variant in rotation:
            if (case, variant) in done:
                continue
            if time.monotonic() - started > TIME_BUDGET_SECONDS:
                raise TimeoutError("Budget of 50m exceeded. Stop before another prompt")
            x = inputs[(case, variant)]
            messages = [{"role": "system", "content": x["system_prompt"]},
                        {"role": "user", "content": x["user_prompt"]}]
            call_start = time.monotonic()
            try:
                output = llm.chat(messages, sampling_params=sampling,
                                  use_tqdm=False, chat_template_kwargs={"enable_thinking": False})[0]
                seq = output.outputs[0]
                prompt_tokens = len(output.prompt_token_ids or [])
                completion_tokens = len(seq.token_ids or [])
                record = {
                    "schema_version": 1, "status": "ok",
                    "collect_only": True, "candidate_executed": False,
                    "recorded_at_utc": now(),
                    "model_name": MODEL_ID,
                    "model_local_path": str(path),
                    "source_commit": FROZEN_COMMIT,
                    "instance_id": case, "variant": variant,
                    "system_prompt_sha256": sha256(x["system_prompt"].encode("utf-8")),
                    "user_prompt_sha256": x["user_prompt_sha256"],
                    "seed": 0, "temperature": 0.0, "max_tokens": MAX_NEW_TOKENS,
                    "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "finish_reason": seq.finish_reason,
                    "elapsed_sec": round(time.monotonic() - call_start, 3),
                    "response_text": seq.text,
                    "hardware": gpus,
                }
            except Exception as ex:
                checked_append({"schema_version": 1, "status": "error", "collect_only": True,
                                "instance_id": case, "variant": variant,
                                "recorded_at_utc": now(), "error_type": type(ex).__name__,
                                "error_message": str(ex)[:800]})
                raise
            checked_append(record)
            total += 1
            print(f"CHECKPOINT_OK {case} {variant} output_tokens={completion_tokens} "
                  f"elapsed={record['elapsed_sec']}s total_new={total}", flush=True)
    print("ALL_15_REAL_UPSTREAM_INFERENCE_COMPLETED", len(completed_keys()) == 15, flush=True)
    print("OUTPUT_JSONL", OUTPUT, "SHA256", sha256(OUTPUT.read_bytes()), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--local-frozen-root", default=None)
    args = parser.parse_args()
    if args.preflight_only:
        x = load_inputs(args.local_frozen_root)
        print("PASS: frozen prompt manifest", len(x), "at", FROZEN_COMMIT)
        return
    try:
        run(args.local_frozen_root)
    except Exception as e:
        print("EXPERIMENT_STOPPED", type(e).__name__, str(e)[:1100], flush=True)
        raise


if __name__ == "__main__":
    main()
