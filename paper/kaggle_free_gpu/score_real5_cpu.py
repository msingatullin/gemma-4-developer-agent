#!/usr/bin/env python3
"""Strict read-only intake and CPU scoring of Kaggle free-GPU Gemma4 real5 outputs.

Requires prior successful golden control validation. Never reads gold patches
for model scoring; the evaluator uses only frozen task tests and baseline.
Does not mutate Kaggle or start GPU. Writes evidence under report directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "e2e_gemma_experiment"))
from evaluate_real_repo_patches import evaluate_patch_on_task, ARCHIVE_DIR, TASKS_MAP

MODEL = "google/gemma-4-31B-it-qat-w4a16-ct"
COMMIT = "1ccd44df721b9f3b4af14824e90544f6cdba4a9e"
VARIANTS = ("A_raw", "B2_assertion_aware", "C_tail35")
CASES = (
    "pallets__flask-4045", "pallets__flask-4992",
    "pallets__flask-5063", "psf__requests-1963",
    "psf__requests-2148",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate(path):
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    expected = {(c, v) for c in CASES for v in VARIANTS}
    seen = {}
    errors = []
    for row in rows:
        key = (row.get("instance_id"), row.get("variant"))
        if key in seen:
            errors.append(f"duplicate {key}"); continue
        seen[key] = row
        if key not in expected:
            errors.append(f"unexpected key {key}"); continue
        if row.get("status") != "ok" or row.get("collect_only") is not True:
            errors.append(f"non-completed row {key}"); continue
        if row.get("candidate_executed") is not False:
            errors.append(f"candidate was already executed {key}"); continue
        if row.get("model_name") != MODEL or row.get("source_commit") != COMMIT:
            errors.append(f"model/source mismatch {key}"); continue
        if not row.get("response_text", "").strip():
            errors.append(f"empty response {key}")
        if row.get("total_tokens", -1) != row.get("prompt_tokens", 0) + row.get("completion_tokens", 0):
            errors.append(f"invalid usage counters {key}")
        frozen = json.loads(
            (ARCHIVE_DIR / "frozen_prompts" / f"{key[0]}__{key[1]}.json").read_text(encoding="utf-8")
        )
        if row.get("user_prompt_sha256") != frozen["user_prompt_sha256"]:
            errors.append(f"prompt mismatch {key}")
        if row.get("system_prompt_sha256") != sha(frozen["system_prompt"].encode("utf-8")):
            errors.append(f"system prompt mismatch {key}")
    missing = expected - set(seen)
    if missing:
        errors.append(f"missing {len(missing)} task×variant pairs: {sorted(missing)}")
    if errors or len(rows) != 15:
        raise ValueError("Reject invalid/incomplete model corpus: " + " | ".join(errors[:15]))
    return seen, sha(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inference_jsonl", type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args()
    seen, input_digest = validate(args.inference_jsonl)
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    output_file = report_dir / "kaggle_free_real5_cpu_scores.jsonl"
    if output_file.exists():
        raise FileExistsError("Refusing to overwrite prior scoring run: " + str(output_file))
    summary = {v: {"n": 0, "resolved": 0, "other_verdicts": {}, "token_total": 0} for v in VARIANTS}
    for index, (case, variant) in enumerate((c, v) for c in CASES for v in VARIANTS):
        row = seen[(case, variant)]
        started = time.monotonic()
        try:
            result = evaluate_patch_on_task(case, row["response_text"], run_id=f"kagglefree{index:02d}")
            verdict = result.get("verdict", "HARNESS_ERROR")
            error = None
        except Exception as exc:
            verdict, error = "HARNESS_ERROR", (type(exc).__name__ + ": " + str(exc))[:950]
            result = {"verdict": verdict}
        item = {
            "instance_id": case, "variant": variant, "verdict": verdict,
            "f2p_pass": result.get("f2p_pass"), "p2p_pass": result.get("p2p_pass"),
            "evaluation_time_sec": round(time.monotonic() - started, 3),
            "response_sha256": sha(row["response_text"].encode("utf-8")),
            "prompt_sha256": row["user_prompt_sha256"],
            "input_corpus_sha256": input_digest,
            "tokens": row["total_tokens"],
        }
        if error:
            item["harness_error"] = error
        with output_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        stats = summary[variant]
        stats["n"] += 1
        stats["resolved"] += int(verdict == "RESOLVED")
        stats["token_total"] += row["total_tokens"]
        stats["other_verdicts"][verdict] = stats["other_verdicts"].get(verdict, 0) + 1
        print(f"VERDICT {case} {variant} {verdict}", flush=True)
    final = {
        "source": "Kaggle_free_T4x2_Gemma4_real5",
        "collect_only_model_generation": True,
        "model": MODEL, "source_commit": COMMIT,
        "input_corpus_sha256": input_digest,
        "per_variant": summary,
        "task_count": len(CASES),
        "distinct_repos": 2,
        "honesty_note": "Five curated upstream tasks are too few to establish statistical noninferiority or broad generalization.",
    }
    (report_dir / "kaggle_free_real5_summary.json").write_text(
        json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(final, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
