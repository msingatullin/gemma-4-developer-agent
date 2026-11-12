# G1-004–006: three additional authentic SWE issue oracles on CPU

Date: 2026-11-12. **Result: 3/3 additional selected tasks pass the strict offline oracle conditions.** Combined with earlier G1-001–003: **6/50 tasks**, comprising **4 dev and 2 heldout**, across **three upstream repositories (Flask, Requests, pytest)**.

**This is evaluator validation. It is NOT proof Gemma E4B solved 6 tasks.** Neither E4B nor 31B was invoked, and there was no Kaggle submission.

## Pre-registration and pinned snapshots

[Protocol](G1_004_006_PROTOCOL.md) was frozen before running. The manifest is the 50-task frozen SWE issue dataset, SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`. Exact git tree SHA is checked before applying patches. Gold source patches and test patches stay exclusively in an offline test harness.

| ID | Frozen SWE-bench task | Split | BASE F2P | GOLD F2P | BASE P2P | GOLD P2P |
|---|---|---|---|---|---|---|
| G1-004 | `pallets__flask-5014` | Heldout | 1 behavior failure: missing `ValueError` | 1 PASS | 2 PASS | 2 PASS |
| G1-005 | `psf__requests-3362` | Heldout | 1 behavior failure: incorrect decoded content | 1 PASS | 2 PASS | 2 PASS |
| G1-006 | `pytest-dev__pytest-11143` | Dev | 1 behavior failure: inner assertion-rewriting TypeError causes outer test failure | 1 PASS | 2 PASS | 2 PASS |

Pinned source snapshots:
- Flask-5014 commit `7ee9ceb71e868944a46e1ff00b506772a53a4f1d`, Git tree SHA `c3d16a156c9206389b230b2884557c486e871589`.
- Requests-3362 commit `36453b95b13079296776d11b09cab2567ea3e703`, Git tree SHA `5602c48ac5ca0cabc7d13e5fddc339410dc7af18`.
- pytest-11143 commit `6995257cf470d2143ad1683824962de4071c0eb7`, Git tree SHA `5e87fec76a0ead331441eaf05a1510c6c6efe6cf` (retrieved exact pinned GitHub commit in isolated checkout).

All tests executed using existing CPU-only Docker images, `--network none`, `--read-only`, `--cpus 1`, `--memory 768m`, with independent BASE and GOLD checkouts and tested behavioral assertions.

**pytest environment repair:** the first four pytest runs could not import the exact historical source because `src/_pytest/_version.py` is created by the package's documented `setuptools_scm` build step. These runs were **ENV_BLOCKED**, not RED. After committing an environment-repair protocol addendum, generated the same minimal build-version file in both isolated BASE and GOLD checkouts, preserving every frozen tracked source file and original Git tree. A fresh retry then produced one actual failing outer regression test on BASE and 1 PASS after gold patch, with 2/2 P2P on both. The inner fixture originally failed because of the exact target source TypeError `argument of type 'int' is not iterable` during assertion rewriting; this is the behavior targeted by the SWE issue, not a missing dependency or external harness failure.

**Evidence:** [complete JSON, logs, exit statuses, Git tree and patch SHA](G1_004_006_VERIFIED_EVIDENCE.json), 25,913 bytes, SHA256 `e88625de19468a446621d585ee63beeb683776d0f2725e85d89f4d3c6bceae8f`. All source snapshots, gold and test patches remain private on `nuremberf:/opt/kaggle/gemma-agent-g0-20261112-audit/g1_004_006_cpu_20261112`.

## Explicit limitations / verdict

- PASS is an offline evaluator readiness indicator for selected F2P and P2P tests. Not full official hidden P2P suite.
- Two tasks are taken from the frozen heldout split but they were selected and their issue metadata inspected to construct the oracle. **This is not an untouched, blinded evaluation of an LLM**, and must not be counted as heldout agent solve rate.
- All six G1 fixtures were solved by oracle gold source patches, not by E4B; the official Kaggle `swegemma`/ADK agent runner remains unverified on VPS, and real EXP-AGENT-001A model A/B has **not** run.
- Original E4B v15 Public 0.06 and 31B v11/v14 Public 0.17 remain protected. No paid compute or Kaggle sends.
- Next stage: freeze a larger diverse task subset and validate native `swegemma`/ADK runner; measure actual model-generated patches, not gold oracle completions, using strict independent F2P/P2P. Paid GPU requires explicit separate owner approval.
