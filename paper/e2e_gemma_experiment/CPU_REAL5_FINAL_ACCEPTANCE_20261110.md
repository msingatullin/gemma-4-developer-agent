# PAPER-CPU-REAL5-20261110 — Final CPU acceptance

**Status: ACCEPT CPU-only harness and reference controls; HOLD real-model performance claims.** Date 2026-11-10, owner authorization CPU-only, no GPU, no Kaggle submissions/edits, no incremental paid compute.

## Objective and hypothesis

Five authentic, pinned Flask/Requests bugfix tasks should reproduce the historical source failure (RED), pass after the gold patch (GREEN), and preserve their predefined offline passing-test subset (P2P). The real-repo evaluator must independently distinguish gold success, unfixed base, invalid syntax and a deliberately introduced regression. **This gate tests evaluator validity, not model efficacy.**

Immutable inputs: 5 authentic upstream commits, 10 test/gold patch SHA256 values, 15 frozen A/B2/C prompts; all previously audited and unchanged. Old benchmark of 150 real Gemma4 calls remains exclusively on 15 synthetic reproductions.

## Confirmed execution

| Checkpoint | Confirmed result | Evidence |
| --- | --- | --- |
| Existing code security/score unit tests | **39/39 PASS** on exact checkout `96e968959f4ae20c0c74f2dea10d120f81c0e3cf` (13 patch allowlist, 11 Docker command, 8 pytest scoring, 7 mocked cleanup) | Gateway job `job_01M72CZXR700MRCJ37VCYV9SVN` |
| Real five upstream bugs, original source + test patch | **5/5 RED**, 7 target F2P tests failed before gold patch | [CPU_UPSTREAM_RED_GREEN_20261110.json](CPU_UPSTREAM_RED_GREEN_20261110.json), Gateway job `job_01M72CK55Y00ZNT468T2G0BQA0` |
| Same five cases with gold patches | **5/5 GREEN**, 7/7 F2P tests passed | Same source |
| Offline P2P before and after gold patches | **155/155 P2P passed** in each matched red/green tree | Same source |
| Full actual evaluator positive gold controls | **5/5 RESOLVED** | [CPU_EVALUATOR_CONTROLS_20261110.json](CPU_EVALUATOR_CONTROLS_20261110.json) |
| Full actual evaluator negative unchanged-base controls | **5/5 FAILED_F2P** | Same source |
| Full actual evaluator malformed input control | **SYNTAX_ERROR** | Same source |
| Full actual evaluator deliberate regression control | **REGRESSION** | Same source |
| Total full post-refactor evaluator control cases | **12/12 PASS**, CLI exit 0, no temporary running containers | Gateway job `job_01M72CYBCV004XTTXPAKPSE2YP`, independent audit job `job_01M72CZXR700MRCJ37VCYV9SVN` |

Fresh control JSON SHA256: `f6c897a4d8e0b5ce8b5010547484a124d9fda20c60924865664bc2be934379e2`. Original reference control summary JSON SHA256: `67398529c32d8bc08c56eaeb2e5390d5510507f4f46f2541b6d62e4960ffb5eb` on server; original per-run pytest logs preserved under `/opt/kaggle/gemma-paper-cpu-runs/` and hashed individually in JSON.

## Reproducible environment and code

- Gateway SSH owned server: `nuremberf`; Ubuntu 24.04; ~6.0 GiB free after setup (96% root disk use). No production Docker services altered; `shadowtalk-postgres` remained running, no Kaggle test containers left running.
- Per-Python-version, **immutable local Docker image IDs**: 3.9 `sha256:80e945d7246b7d943fbbe20dbd5f3c010ed9e43c5ad85313164a2d84a1f0edb5`, 3.10 `sha256:8eb06d4197a52bc0a21cdbc733523a94fb6ebb1b7daad3854d985e77c5f5e47b`, 3.11 `sha256:ed700cf7dbc0604bed4374b3a027596162ac72b7ba6983d3c5b92988d527cc74`.
- CPU sandbox: no network, no privileges, read-only root/worktree, non-root UID 65534, disabled bytecode, bounded CPU/RAM/PIDs, tmpfs, exact ID-only image selection; named containers and fail-closed timeout cleanup.
- Executed evaluator source commit: `96e968959f4ae20c0c74f2dea10d120f81c0e3cf` (includes configurable isolated upstream/work/output folders, final-diff-newline preservation and stdout+stderr on patch error). No historical reports overwritten.
- Archive and test implementation: `real_repo_sample/manifest.json`, `evaluate_real_repo_patches.py`, `test_patch_path_guard.py`, `test_safe_sandbox_command.py`, `test_pytest_pass_contract.py`, `test_cpu_timeout_cleanup.py`.
- Tested with `PAPER_EVAL_UPSTREAM_CACHE=/opt/kaggle/gemma-paper-upstream`, `PAPER_EVAL_WORK_BASE=/opt/kaggle/gemma-paper-evaluator-work`, `PAPER_EVAL_REPORT_DIR=/opt/kaggle/gemma-paper-evaluator-reports-20261110`, and `PAPER_EVAL_IMAGE_PY3_{9,10,11}` set to respective image IDs.

## Audited failures and fixes (not hidden)

- Initial incomplete Requests-1963 checkout produced a Python import error; fixed by restoring pinned upstream source, then repeated and confirmed genuine 1 RED / 1 GREEN. Incomplete import error is **not** a benchmark failure.
- Missing old GitHub Buildx plugin required small offline image-ID-compatible bootstrap images, avoiding system package changes.
- The evaluator's first gold control failed with `PATCH_APPLY_ERROR` because fenced model diff extraction dropped the final newline. Proved with `patch --dry-run`; fixed in commit `bc22bcad1d66fa70c3d2da75285a69ab6647607b` and independently reran Flask4992 `RESOLVED` at Gateway job `job_01M72CWJJ900PBFTGE5KFCSF0M`.
- Fresh control results redirected outside archival manifest in commit `96e968959f4ae20c0c74f2dea10d120f81c0e3cf`.
- Unit suite 39/39 PASS and all 12 current evaluator controls PASS **after fixes**; earlier failures excluded from success claims.

## Interpretation and next gate

**Accept** that our evaluation harness can reproduce the authentic upstream RED→gold GREEN check and detect a deliberate regression, in offline CPU-only containers on all five instances. This establishes an independently re-executable **ground-truth quality gate**, which is stronger than metadata-only provenance.

**Not established:** Gemma performance on these real tasks; B2 quality advantage, generalization beyond five tasks/two repos, inferential noninferiority/equivalence, or prize-winning status. Gold patches are not model outputs.

The **next scientifically meaningful step** would be matched Gemma A/B2/C inference on the frozen five authentic issues and scoring those outputs through this now-validated harness. That requires **separate user approval for GPU and any expenditure**. Preserve published Paper Track Writeup ID `115692` and 150-response synthetic baseline. Paper Track deadline confirmed by official Kaggle MCP `2026-11-12T23:59:00Z`; user’s writeup still `PUBLISHED`. No changes to Kaggle submission during this task.

**Expense:** $0 new paid GPU/compute. Production stack untouched. User approval for any paid inference and Kaggle publication remains pending.
