# UNSEEN-3REPO-20261111 — pre-analysis frozen CPU log experiment

Freeze time: 2026-11-11 (before inspecting the test-patch content, running tests, or seeing outcome logs). Scope: an **additional diagnostic-preservation holdout** not a model solve-rate test or competitor head-to-head.

## Immutable task selection

Public SWE-bench Lite test parquet exact SHA256 `7a21f37b8bc179c7db5beeb14e88ac538ba283455c776e6b2535bbfb6e3551b4`. Exactly these three task rows, selected by fixed IDs from **three repositories not previously used** in our 8-case experiment:

| Instance ID | Upstream repository | Frozen base SHA | Official F2P selector |
|---|---|---|---|
| `pydata__xarray-4248` | pydata/xarray | `98dc1f4ea18738492e074e9e51ddfed5cd30ab94` | `xarray/tests/test_formatting.py::test_inline_variable_array_repr_custom_repr` |
| `pylint-dev__pylint-5859` | pylint-dev/pylint | `182cc539b8154c0710fcea7e522267e42eba8899` | `tests/checkers/unittest_misc.py::TestFixme::test_non_alphanumeric_codetag` |
| `sympy__sympy-11897` | sympy/sympy | `e2918c1205c47345eb73c9be68b14c0f15fdeb17` | `test_latex_Piecewise` (pytest-specific mapping to be documented before run) |

## Protocol and declared conditions

1. Clone each upstream at its exact base commit and apply **only the task's official public test patch** from frozen SWE-bench Lite row. Before applying gold patch, run the exact indicated test. Fail closed on setup failures, collection errors, import issues, crash, timeout, or no test collected; do not relabel them as actual task failure. Record command, runtime and both exit status and a log digest.
2. If and only if the original test fails with an **actual assertion/test failure**, preserve the full red pytest log, then apply the official gold patch and verify **same test turns green**. This is a **log-format study**, so gold patch may be used **only to establish red/green validity**, never included in model prompts or proposed patch generation.
3. Compare the **unchanged previously frozen** algorithms `filter_pytest_log`, `filter_pytest_log_v2` from public `paper/traceback_compressor.py` against identical `head35`, `tail35`, `tail20` and `naive_diag`. Exact diagnostic/header/summary line multiplicity retention and **raw byte reduction** are primary outcomes; no LLM calls, no updated thresholds, no new optimizer modifications. Show all rows incl. failures; missing env counts **not evaluable**, never as method win.
4. Holdout **acceptance criterion** precommitted: at least two of these three genuinely passing red→green checks and 100% selected diagnostic/header/summary retention in those, with positive byte reduction under B2. Else REJECT claim of broader external robustness. Under no circumstance claim statistical significance with n=3 or independence from repositories where the source compressor was already manually debugged.
5. Baseline is current `8` original issues/5 repos (Flask3 Requests2 pytest1 Sphinx1 seaborn1). These 3 are **untouched heldout source repositories** for diagnostic compressor, but task selection was not random and related research existed. No claim of agent solve rate or superiority to Jared/Maroof/Toeda, who study different endpoints.
6. Resource budget: free CPU VPS only, up to 3 source clones and three dependency environments, <= 25 minutes planned working budget, no paid calls/GPU, no Kaggle submission or live writeup edit. Do not damage unrelated VPS processes or disk. Save verified code/log manifests, ideally no secrets.

Decision rule: ACCEPT/REJECT based on actual test harness observations, publish results even if negative. Frozen before test output inspection.
