# G1-002 / G1-003 — preregistered multi-repository CPU oracle audit

Date: 2026-11-12. **This document must be committed before running these tests.**

Purpose: independently test whether pinned SWE-bench RED/GREEN test oracles work across a second repository (Requests) and another Flask issue. **Not** Gemma inference, not v15/v17 head-to-head, not Kaggle score.

Frozen task manifest: `paper/small_model_benchmark/manifest.json`, SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`. Test/gold patches and complete case definitions are extracted by task ID from the frozen manifest on the private VPS, with SHA256 recorded before use. Gold and test patch are **offline evaluator only**; never pass to agent.

| ID | Git repository | Pinned base commit | F2P test | P2P tests |
|---|---|---|---|---|
| G1-002 | `pallets/flask` | `4c288bc97ea371817199908d0d9b12de9dae327e` | `tests/test_config.py::test_config_from_file_toml` | `tests/test_config.py::test_config_from_pyfile`; `tests/test_config.py::test_config_from_file_json` |
| G1-003 | `psf/requests` | `fe693c492242ae532211e0c173324f09ca8cf227` | `test_requests.py::RequestsTestCase::test_iter_content_handles_socket_error` | `test_requests.py::RequestsTestCase::test_basic_auth_str_is_always_native`; `test_requests.py::RequestsTestCase::test_cannot_send_unprepared_requests` |

**Protocol per task:**
1. Separate BASE and GOLD checkouts at the identical exact pinned commit, from pre-existing local cached upstream repository; if unavailable, log `MISSING_COMMIT` and do not silently use HEAD or a replacement. Extract and SHA-verify the exact manifest test patch and gold patch; apply test patch to both, gold source patch to GOLD only. Failure is `PATCH_BLOCKED`, not an inference result.
2. Execute BASE F2P, GOLD F2P, GOLD P2P, BASE P2P independently inside pre-existing Python3.9/3.10/3.11 CPU test images as compatible. No network, 1 CPU, <=768MiB, read-only bind mount and image, bounded commands, disable pytest cache. Do not install dependencies; report environment mismatch as `ENV_BLOCKED`.
3. **PASS** only if BASE F2P fails for actual task assertion (not import/collection/setup/absence), GOLD F2P passes, P2P on BASE and GOLD passes. Classify missing dependency or Python version incompatibility separately. Record actual stdout/stderr, exit status, code hashes, exact test selectors and execution duration.
4. Do not label 2/2 CPU test pass as model solve rate. Stop before expensive compute or Kaggle submissions. The private historical file snapshots stay on VPS; publication should contain hashes and bounded reproducible logs without secrets.

G1 task coverage denominator remains 50 frozen manifest tasks, not just successful selected cases. Aim for two additional valid tasks and heterogeneous repositories; otherwise explain blocker and update STATUS.md and MMW.
