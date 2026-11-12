# G0-SEARCH-005 — 9 pinned real DEV issue retrieval comparison

**This is file retrieval, not E4B inference, SWE solve rate, public score, or an approval to submit.**

The issue-only queries were committed before gold-path scoring. [Protocol](G0_SEARCH_005_PROTOCOL.md), [frozen queries](G0_SEARCH_005_FROZEN_QUERY_PLAN.json).

| Task | Gold source path(s), offline only | v15 top5 | 001A top5 | Delta |
|---|---|---|---|---|
| pallets__flask-4045 | src/flask/blueprints.py | MISS | MISS | tie |
| pallets__flask-4992 | src/flask/config.py | HIT | HIT | tie |
| psf__requests-1963 | requests/sessions.py | MISS | HIT | gain |
| psf__requests-2148 | requests/models.py | MISS | MISS | tie |
| psf__requests-2317 | requests/sessions.py | MISS | HIT | gain |
| pytest-dev__pytest-11143 | src/_pytest/assertion/rewrite.py | MISS | HIT | gain |
| pytest-dev__pytest-11148 | src/_pytest/pathlib.py | MISS | MISS | tie |
| pytest-dev__pytest-5103 | src/_pytest/assertion/rewrite.py | MISS | MISS | tie |
| pytest-dev__pytest-5221 | src/_pytest/python.py | MISS | MISS | tie |

## Frozen metric summary

- v15 hit@5: **1/9**; candidate hit@5: **4/9**.
- v15 hit@1: **1/9**; candidate hit@1: **4/9**.
- Wins/ties/losses at hit@5: **3/6/0**.
- Cases where shell unquoted \`*.py\` expanded to root filenames: **8/9**.
- Pre-registered pilot gate: **PROMISING_RETRIEVAL_ONLY**.

Gold path filenames are used solely in this OFFLINE scoring stage after CPU search outputs were saved; all nine cases are DEV. Tokens manually chosen from issue statements, not model-generated; these diagnostics cannot substitute for actual paired E4B patch solve validation. Raw stdout/runtime and Git tree checks: [G0_SEARCH_005_RAW.json](G0_SEARCH_005_RAW.json); gold-scored metadata: [G0_SEARCH_005_SCORED.json](G0_SEARCH_005_SCORED.json).

Original Kaggle E4B v15 score 0.06 preserved, candidate 001A not submitted. No GPU/API/spend/submission.
