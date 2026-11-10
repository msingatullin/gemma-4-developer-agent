# Gemma Paper — CPU execution audit (2026-11-10)

**Scope:** free, CPU-only verification. No GPU, paid resources, Kaggle writeup changes, model inference or generated patch execution.

## Execution environment

- Gateway SSH server: `nuremberf`, Ubuntu 24.04, Python 3.12.3 and Git 2.43.0.
- Separate sparse checkout: `/opt/kaggle/gemma-paper` (~6 MB), `main` SHA `d7288cd6bc4be01d441b9a8be9b1817a3f84632c`.
- Root filesystem around 95% used, 6.8 GiB free at audit. Existing production services untouched.

## Actual unit executions

Gateway job `job_01M729CMZC006PNXQ1SYXRFR1T`, prior SHA `157b5377`: **29/31**, two failed in pytest summary parsing. Actual failure: parser literal `\\s+passed\\b` failed to recognize `2 passed`, proving earlier reconstructed tests were insufficient. No false claim of initial success.

Fixed regexp via commit `d7288cd6bc4be01d441b9a8be9b1817a3f84632c`.

Gateway job `job_01M729DKTR00G3Z1DXN0PE8VEP`, exact GitHub checkout at corrected commit:
- `python3 -m unittest discover -s paper/e2e_gemma_experiment -p test_patch_path_guard.py -v`: **13/13 PASS**.
- `python3 -m unittest discover -s paper/e2e_gemma_experiment -p test_safe_sandbox_command.py -v`: **10/10 PASS**.
- `python3 -m unittest discover -s paper/e2e_gemma_experiment -p test_pytest_pass_contract.py -v`: **8/8 PASS**.
- Total **31/31 PASS** from real source, not a reconstructed mirror. No Python packages or Docker images downloaded.

## Frozen data integrity (read-only)

Gateway job `job_01M729FZVC00P9VG18WKY8EVEK`, exact checkout SHA `d7288cd6`:
- 5 distinct authentic upstream cases in `real_repo_sample/manifest.json`.
- 10/10 on-disk `gold_patch.diff` and `test_patch.diff` SHA256 hashes match the manifest.
- 15/15 frozen inputs (five cases × A_raw/B2_assertion_aware/C_tail35) found, all nonempty, metadata consistent, all `user_prompt_sha256` hashes match.
- Zero integrity errors. These are input/integrity assertions, **not model evaluation**.

## Open blockers

1. Upstream bare repositories `/home/mikhail/upstream_repos` and CPU virtualenv cache `/tmp/real_tasks_cpu_eval` absent on this VPS. Do not assume historical logs represent current rerun.
2. No dedicated digest-pinned per-Python-version runtime image yet; Docker inventory contains production images, which must remain untouched.
3. Disk 95% used (6.8 GiB available): do not install heavy dependency/image sets or remove other data without additional cost/resource assessment.
4. Real upstream 12 evaluator controls have **not** been freshly executed after sandbox rewrite; timeout/daemon teardown verification remains pending.
5. User authorization **CPU-only**, GPU and Kaggle publication modifications prohibited.

**Decision:** Phase 1 pure CPU unit and input integrity gates PASS; authentic upstream execution gate remains **HOLD**.
