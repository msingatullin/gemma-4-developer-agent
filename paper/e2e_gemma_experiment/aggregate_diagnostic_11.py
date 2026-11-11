#!/usr/bin/env python3
"""Descriptive pooled audit over 8 development + 3 prospective heldout logs.

This is NOT an 11-case preregistered hypothesis test. The two split reports
can each be replayed independently from authentic public fixture logs.
"""
from pathlib import Path
import json
import hashlib

ROOT = Path(__file__).resolve().parent
DEV = ROOT / "real_repo_sample/baseline_comparison_5repos_results_20261111.json"
HOLD = ROOT / "heldout_three_repos/baseline_comparison_heldout_results_20261111.json"

def read(path):
    return json.loads(path.read_text())

dev, hold = read(DEV), read(HOLD)
assert len(dev["rows"]) == 56 and len(hold["rows"]) == 21
assert len({r["instance_id"] for r in dev["rows"]}) == 8
assert len({r["instance_id"] for r in hold["rows"]}) == 3
assert not ({r["instance_id"] for r in dev["rows"]} & {r["instance_id"] for r in hold["rows"]})
assert set(dev["aggregate"]) == set(hold["aggregate"])

summary = {}
for method in sorted(dev["aggregate"]):
    d = [r for r in dev["rows"] if r["method"] == method]
    h = [r for r in hold["rows"] if r["method"] == method]
    assert len(d) == 8 and len(h) == 3
    merged = d + h
    original = sum(r["raw_bytes"] for r in merged)
    result = sum(r["out_bytes"] for r in merged)
    summary[method] = {
        "development_full_integrity": sum(r["all_integrity"] for r in d),
        "prospective_heldout_full_integrity": sum(r["all_integrity"] for r in h),
        "pooled_full_integrity": sum(r["all_integrity"] for r in merged),
        "pooled_n": len(merged),
        "pooled_raw_bytes": original,
        "pooled_output_bytes": result,
        "pooled_corpus_byte_reduction_pct": round(100 * (1 - result / original), 2),
        "heldout_corpus_byte_reduction_pct": hold["aggregate"][method]["corpus_saved_pct"],
    }
assert summary["ours_v2_B2"]["development_full_integrity"] == 8
assert summary["ours_v2_B2"]["prospective_heldout_full_integrity"] == 3
assert summary["head35"]["pooled_full_integrity"] == 2
assert summary["tail35"]["pooled_full_integrity"] == 2

output = {
    "experiment_id": "PAPER-11-CASE-COMBINED-DESCRIPTIVE-20261111",
    "scope": "Post-hoc descriptive pooling of an 8-case development benchmark and a separate 3-case locally prospective heldout audit; eight upstream repositories total. Never present pooled metrics as independent preregistered validation or model solve rate.",
    "development_cases": 8,
    "prospective_heldout_cases": 3,
    "unique_upstream_repositories": 8,
    "development_result_file_sha256": hashlib.sha256(DEV.read_bytes()).hexdigest(),
    "heldout_result_file_sha256": hashlib.sha256(HOLD.read_bytes()).hexdigest(),
    "methods": summary,
}
print(json.dumps(output, ensure_ascii=False, indent=2))
