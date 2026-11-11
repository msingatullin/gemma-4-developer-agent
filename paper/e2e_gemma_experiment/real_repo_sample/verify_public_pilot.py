#!/usr/bin/env python3
"""Recompute public, non-replayable five-upstream-issue result aggregates.

This independently checks consistency of the released task-level verdicts.
It does NOT execute hidden model responses or validate patch correctness.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import json

data = json.loads(Path(__file__).with_name("PUBLIC_PILOT_RESULTS_20261111.json").read_text())
rows = data["tasks"]
assert len(rows) == 15
variants = ("A_raw", "B2_assertion_aware", "C_tail35")
expected_tasks = {
    "pallets__flask-4045", "pallets__flask-4992", "pallets__flask-5063",
    "psf__requests-1963", "psf__requests-2148",
}
seen = {(r["instance_id"], r["variant"]) for r in rows}
assert len(seen) == 15
assert seen == {(t, v) for t in expected_tasks for v in variants}
assert all(len(r["prompt_sha256"]) == 64 and len(r["response_sha256"]) == 64 for r in rows)
assert all(r["verdict"] in {"RESOLVED", "SYNTAX_ERROR", "FAILED_F2P"} for r in rows)
assert all(isinstance(r["tokens"], int) and r["tokens"] > 0 for r in rows)
agg = {}
for v in variants:
    subset = [r for r in rows if r["variant"] == v]
    agg[v] = {
        "n": len(subset),
        "resolved": sum(r["verdict"] == "RESOLVED" for r in subset),
        "tokens": sum(r["tokens"] for r in subset),
    }
    assert agg[v] == data["summary"][v], v
    print(f"{v}: {agg[v]['resolved']}/{agg[v]['n']} resolved; "
          f"{agg[v]['tokens']} total API tokens")
solved = [{r["instance_id"] for r in rows
           if r["variant"] == v and r["verdict"] == "RESOLVED"}
          for v in variants]
assert solved[0] == solved[1] == solved[2] == {"psf__requests-1963"}
reduction = (1 - agg["B2_assertion_aware"]["tokens"] / agg["A_raw"]["tokens"]) * 100
assert abs(reduction - 9.7623) < 0.02
print(f"B2 total-token reduction vs A: {reduction:.2f}%")
print("PASS: 15/15 public verdict manifest entries and recomputed aggregates")
print("LIMITATION: raw private responses not included; this checks arithmetic, NOT replay.")
