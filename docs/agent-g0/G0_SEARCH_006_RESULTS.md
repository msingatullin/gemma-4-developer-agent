# G0-SEARCH-006 — nine DEV issue search instruction ablations

**Important:** same previously used dev tasks and manually selected issue tokens; exploratory retrieval only, not independent heldout or model solve rate.

| Variant | Gold source hit@1 | Gold source hit@5 | Gains vs v15 | Losses vs v15 |
|---|---:|---:|---:|---:|
| v15_original | 1/9 | 1/9 | 0 | 0 |
| quote_only | 2/9 | 4/9 | 3 | 0 |
| quote_casefold | 2/9 | 4/9 | 3 | 0 |
| quote_casefold_filtered | 2/9 | 4/9 | 3 | 0 |
| exp001a_current | 4/9 | 4/9 | 3 | 0 |

Exploratory simplest retrieval expression within the pre-registered <=1/9 slack from full 001A: **quote_only**.

## Per-task gold-source hit@5

| Task | V15 | quote only | quote+case | quote+case+filters | 001A |
|---|---|---|---|---|---|
| pallets__flask-4045 | — | — | — | — | — |
| pallets__flask-4992 | ✓ | ✓ | ✓ | ✓ | ✓ |
| psf__requests-1963 | — | ✓ | ✓ | ✓ | ✓ |
| psf__requests-2148 | — | — | — | — | — |
| psf__requests-2317 | — | ✓ | ✓ | ✓ | ✓ |
| pytest-dev__pytest-11143 | — | ✓ | ✓ | ✓ | ✓ |
| pytest-dev__pytest-11148 | — | — | — | — | — |
| pytest-dev__pytest-5103 | — | — | — | — | — |
| pytest-dev__pytest-5221 | — | — | — | — | — |

All original and 001A command stdout reproduced **exactly** from the frozen G0-005 raw record. CPU subprocesses operated on original immutable Git trees without gold/test patches. Gold filenames were accessed only in the separate offline Stage B process.

Query plan [G0-SEARCH-005](G0_SEARCH_005_FROZEN_QUERY_PLAN.json); this stage's [preregistered protocol](G0_SEARCH_006_PROTOCOL.md), [search raw output](G0_SEARCH_006_RAW.json), [offline score metadata](G0_SEARCH_006_SCORED.json).

Never infer E4B solve-rate or Kaggle score gains from these retrieval metrics. No Kaggle send, paid GPU/API, or original submission changes.
