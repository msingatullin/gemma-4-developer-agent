#!/usr/bin/env python3
"""Rebuild EXACT best-E4B v15 into private minimally changed EXP-AGENT-002.

Only one line's shell '*.py' is quoted. No GPU/LLM calls or Kaggle submission.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SOURCE_SHA = "f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a"
FILES = {
    "agent.yaml",
    "configs/sampling.yaml",
    "eval_config.yaml",
    "prompts/system.md",
}
DIRECTORIES = {"configs/", "prompts/"}
BEFORE = b'git grep -n "SPECIFIC_TOKEN" -- *.py | head -20'
AFTER = b"""git grep -n "SPECIFIC_TOKEN" -- '*.py' | head -20"""


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build(input_zip: Path, output_folder: Path) -> dict:
    if not output_folder.is_dir():
        raise FileNotFoundError("Create a new private output dir explicitly")
    original = input_zip.read_bytes()
    if digest(original) != SOURCE_SHA:
        raise ValueError("Authenticated Kaggle v15 source ZIP SHA mismatch")
    with ZipFile(input_zip) as z:
        if z.testzip() is not None:
            raise ValueError("Corrupt archive")
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicated ZIP entries")
        files = {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}
        directories = {i.filename for i in z.infolist() if i.is_dir()}
        if set(files) != FILES or not directories.issubset(DIRECTORIES):
            raise ValueError(f"Unexpected ZIP layout: {list(files)}, dirs={directories}")
        if any(n.startswith("/") or ".." in Path(n).parts for n in names):
            raise ValueError("Unsafe ZIP member")

    prompt = files["prompts/system.md"]
    if prompt.count(BEFORE) != 1:
        raise ValueError(f"Unique source anchor expected once, got {prompt.count(BEFORE)}")
    replaced = prompt.replace(BEFORE, AFTER, 1)
    if replaced.replace(AFTER, BEFORE, 1) != prompt:
        raise ValueError("Prompt transformation not reversible")
    candidate = dict(files)
    candidate["prompts/system.md"] = replaced
    changes = [f for f in sorted(FILES) if candidate[f] != files[f]]
    assert changes == ["prompts/system.md"], changes

    zip_path = output_folder / "exp_agent002_quote_only.zip"
    manifest_path = output_folder / "exp_agent002_quote_only_manifest.json"
    if zip_path.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite previous built candidate")
    with zip_path.open("xb") as f:
        with ZipFile(f, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(FILES):
                entry = ZipInfo(name, date_time=(2026, 11, 12, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.external_attr = 0o600 << 16
                archive.writestr(entry, candidate[name], compress_type=ZIP_DEFLATED, compresslevel=9)
    with ZipFile(zip_path) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != FILES:
            raise ValueError("Candidate output ZIP verification failed")
        for name in FILES:
            if archive.read(name) != candidate[name]:
                raise ValueError(f"Output file SHA/bytes mismatch: {name}")

    diff = list(difflib.unified_diff(
        prompt.decode("utf-8").splitlines(),
        replaced.decode("utf-8").splitlines(),
        fromfile="v15/prompts/system.md",
        tofile="EXP-AGENT-002/prompts/system.md",
        lineterm="",
    ))
    # Only the context header + @@ + original/replacement one line should change.
    replaced_lines = [x for x in diff if x.startswith("-") and not x.startswith("---")]
    added_lines = [x for x in diff if x.startswith("+") and not x.startswith("+++")]
    if len(replaced_lines) != 1 or len(added_lines) != 1:
        raise ValueError(f"More than one prompt line changed: {len(replaced_lines)}-{len(added_lines)}")
    manifest = {
        "id": "EXP-AGENT-002",
        "source": "Exact authenticated Kaggle E4B v15 submission 58073369",
        "source_zip_sha256": SOURCE_SHA,
        "source_zip_bytes": len(original),
        "candidate_zip_filename": zip_path.name,
        "candidate_zip_sha256": digest(zip_path.read_bytes()),
        "candidate_zip_bytes": zip_path.stat().st_size,
        "file_names": sorted(FILES),
        "changed_member_files": changes,
        "baseline_members": {x:digest(files[x]) for x in sorted(FILES)},
        "candidate_members": {x:digest(candidate[x]) for x in sorted(FILES)},
        "prompt_line_minus_plus": {"removed":replaced_lines,"added":added_lines},
        "other_prompt_bytes_identical": True,
        "all_other_member_files_byte_identical": True,
        "static_validator": "NOT RUN",
        "organizer_adk_compiler": "NOT RUN",
        "model_inference": "NOT RUN",
        "kaggle_submission": "NOT SENT",
    }
    with manifest_path.open("x") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(build(a.baseline, a.output_dir), indent=2, ensure_ascii=False))
