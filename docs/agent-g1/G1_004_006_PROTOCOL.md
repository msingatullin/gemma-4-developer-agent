# G1-004–006 — preregistered heterogeneous RED/GREEN+P2P checks

**Date:** 2026-11-12. **Status:** FROZEN BEFORE EXECUTION.

Objective: improve verified CPU evaluator coverage beyond 3 dev issues, with **two distinct heldout cases** plus **one third-repository issue**. Tests and gold patches remain inaccessible to any model.

Frozen manifest: `paper/small_model_benchmark/manifest.json`, SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`.

| Stage | Instance | Split | Exact historical base | F2P | Two P2P selectors (if available) |
|---|---|---|---|---|---|
| G1-004 | `pallets__flask-5014` | heldout | `7ee9ceb71e868944a46e1ff00b506772a53a4f1d` | `tests/test_blueprints.py::test_empty_name_not_allowed` | `tests/test_blueprints.py::test_blueprint_specific_error_handling` and `tests/test_blueprints.py::test_blueprint_specific_user_error_handling` |
| G1-005 | `psf__requests-3362` | heldout | `36453b95b13079296776d11b09cab2567ea3e703` | `tests/test_requests.py::TestRequests::test_response_decode_unicode` | `tests/test_requests.py::TestRequests::test_entry_points` and `tests/test_requests.py::TestRequests::test_invalid_url[MissingSchema-hiwpefhipowhefopw]` |
| G1-006 | `pytest-dev__pytest-11143` | dev / third repository | read exact commit from same SHA-frozen manifest | `testing/test_pytester.py::TestPytester::test_*` selector **only if the manifest truly contains it**; otherwise use the manifest's first exact F2P selector without substitution | first two distinct manifest P2P selectors |

**IMPORTANT:** G1-006 test names must be read and reported from the frozen manifest before invocation; do not guess or transform selectors.

Setup conditions: never use a newer commit if historical commit not available. For shallow promisor cached repo, use `git archive <exact pin>`, force-add every tracked file, and verify full Git tree hash against historical `<pin>^{tree}` BEFORE patches; if source unavailable, may fetch exact public pinned commit into isolated audit directory without altering unrelated repos or services. Stop if any Git tree mismatch. Test patch applied to BASE/GOLD; gold source patch applied to GOLD only. Patch validation/identities recorded.

Runtime: existing CPU Docker Python 3.9, 3.10 or 3.11 image, no network during test, read-only source mount, <=1CPU and <=768MiB, <=55sec per test group; no new package installations on prod. An import/collection failure = `ENV_BLOCKED`, never counted as an F2P RED. For each task run BASE_F2P, GOLD_F2P, BASE_P2P, GOLD_P2P. PASS only if BASE F2P produces actual behavior failure and GOLD F2P passes AND the same P2P selectors pass both BASE and GOLD. Store exit codes, stdout, stderr, SHA, exact test IDs and source tree. No model calls or Kaggle submissions.

Measured oracle coverage denominator is **all 50 tasks** in frozen manifest. Passing selected cases is not proof of candidate uplift, nor a competition solve-rate metric. If a task cannot run without environment repair, report blocker and move to next selected task; do not count as success.

Resources: existing free CPU VPS, no GPU/RunPod/API; expected <=15 min overall CPU; $0 incremental external bill.

## G1-006 environment-repair addendum (recorded after first ENV_BLOCKED run, before retry)

The exact `pytest-dev__pytest-11143` upstream checkout imports `src/_pytest/_version.py` in `_pytest.assertion.rewrite`, but that path is a **build-generated** file declared by the checked-in `pyproject.toml` `[tool.setuptools_scm] write_to = "src/_pytest/_version.py"`. Neither BASE nor GOLD imported: `ModuleNotFoundError: No module named '_pytest._version'` (exit 1), so the first four executions are **ENV_BLOCKED**, not behavior failures.

A CPU-only retry MAY reproduce the build output `src/_pytest/_version.py` with an explicit frozen local version identifier in both BASE and GOLD **identically**, after first asserting the original tracked tree is exact and that neither copy already contains the file. Record generated text and SHA256. Treat that file as a build artifact (not a model patch), assert the rest of the tracked tree remains unchanged, and never include it in an agent submission or task patch. If additional missing package dependencies or incompatible runner are encountered, classify ENV_BLOCKED; no broad installations or unapproved resource use.
