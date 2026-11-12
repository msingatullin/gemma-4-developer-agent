#!/usr/bin/env python3
"""EXP-AGENT-001A: construct one-variable E4B candidate from actual Kaggle v15 ZIP.

CPU-only package build. Does NOT call an LLM, score SWE tasks, or submit to Kaggle.
Expected ZIP remains private on the operator's VPS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

BASELINE_SHA256 = "f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a"
EXPECTED = {
    "agent.yaml",
    "configs/sampling.yaml",
    "eval_config.yaml",
    "prompts/system.md",
}
TICK = chr(96)
OLD = (
    '- Search once with ' + TICK
    + 'git grep -n "SPECIFIC_TOKEN" -- *.py | head -20'
    + TICK
    + '. Use the most specific identifier or error string from the issue.'
)
NEW = (
    '- Prioritize implementation files over tests, docs and examples. Use a specific, '
    'issue-derived identifier, not a generic word. If the issue names a module/file, '
    'first run ' + TICK
    + "git ls-files '*.py' | grep -i -F \"MODULE_OR_FILE_TOKEN\" | grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10"
    + TICK + ' to find implementation files. Otherwise run '
    + TICK
    + "git grep -n -i -F \"SPECIFIC_TOKEN\" -- '*.py' ':!tests/**' ':!**/tests/**' ':!**/test_*.py' ':!docs/**' ':!**/docs/**' ':!examples/**' ':!**/examples/**' | head -20"
    + TICK
    + '. Replace command placeholders with exact text from the issue before running. '
    'Git pathspec *.py already searches nested files: the improvement targeted here is '
    'filtering irrelevant matches, not adding recursive search. '
    'If the issue specifically concerns executable documentation examples, deliberately '
    'include those implementation-example directories in your search.'
)

def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build(baseline: Path, output_dir: Path) -> dict:
    raw = baseline.read_bytes()
    if sha256(raw) != BASELINE_SHA256:
        raise ValueError("Baseline SHA256 mismatch: refusing to build candidate")
    with ZipFile(baseline, "r") as z:
        bad_file = z.testzip()
        if bad_file is not None:
            raise ValueError(f"Baseline corrupt ZIP: {bad_file}")
        members = z.namelist()
        if len(members) != len(set(members)) or set(members) != EXPECTED:
            raise ValueError(f"Unexpected ZIP members: {members}")
        original = {name: z.read(name) for name in members}
    prompt = original["prompts/system.md"].decode("utf-8")
    if prompt.count(OLD) != 1:
        raise ValueError(f"Expected exactly one canonical v15 locator bullet, got {prompt.count(OLD)}")
    result = dict(original)
    result["prompts/system.md"] = prompt.replace(OLD, NEW, 1).encode("utf-8")
    assert result["prompts/system.md"].decode("utf-8").replace(NEW, OLD, 1) == prompt
    changed = [key for key in sorted(EXPECTED) if result[key] != original[key]]
    if changed != ["prompts/system.md"]:
        raise ValueError(f"Not a one-variable edit: {changed}")

    if not output_dir.is_dir():
        raise FileNotFoundError("Output directory must already exist; no implicit deployment")
    candidate = output_dir / "exp_agent001a_v15_single_prompt_search.zip"
    report = output_dir / "exp_agent001a_package_manifest.json"
    if candidate.exists() or report.exists():
        raise FileExistsError("Candidate or manifest already exists; refusing overwrite")

    # The output ZIP contains the exact four baseline member names.
    with candidate.open("xb") as fp:
        with ZipFile(fp, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as z:
            for name in sorted(EXPECTED):
                info = ZipInfo(name, date_time=(2026, 11, 12, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                z.writestr(info, result[name], compress_type=ZIP_DEFLATED, compresslevel=9)

    with ZipFile(candidate, "r") as z:
        if z.testzip() is not None:
            raise ValueError("New candidate failed ZIP CRC")
        if set(z.namelist()) != EXPECTED:
            raise ValueError("Candidate ZIP has unexpected members")
        for name in sorted(EXPECTED):
            if z.read(name) != result[name]:
                raise ValueError(f"Candidate ZIP byte mismatch: {name}")

    payload = {
        "experiment_id": "EXP-AGENT-001A",
        "source_submission_ref": 58073369,
        "source_archive_sha256": BASELINE_SHA256,
        "source_archive_bytes": len(raw),
        "candidate_filename": candidate.name,
        "candidate_archive_sha256": sha256(candidate.read_bytes()),
        "candidate_archive_bytes": candidate.stat().st_size,
        "modified_files": changed,
        "baseline_members": {key: sha256(original[key]) for key in sorted(EXPECTED)},
        "candidate_members": {key: sha256(result[key]) for key in sorted(EXPECTED)},
        "exactly_one_bullet_changed": True,
        "all_nonprompt_bytes_identical": True,
        "static_validation": "NOT RUN",
        "e4b_model_inference": "NOT RUN",
        "kaggle_submission": "NOT SENT",
        "scope": "Private experimental archive, not an endorsed Kaggle entry",
    }
    with report.open("x", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.baseline, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
