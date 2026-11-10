# Gemma 4 Paper Track — CPU-only Gateway SSH phase 2 audit

Date: 2026-11-10. All activities are read-only or limited to isolated `/opt/kaggle/gemma-paper*` workspaces. No GPU, paid compute, Kaggle edits, Docker image pulls or service modifications.

## Control points

- **Confirmed scientific baseline remains unchanged:** 150 real Gemma4 calls over 15 synthetic cases; this report makes **no new model-performance claim**.
- Gateway SSH server `nuremberf`, Ubuntu 24.04, 3.8 GiB RAM (~2.8 GiB available in initial audit), root filesystem 95% full (~6.8 GiB available). Production container `shadowtalk-postgres` was left running.
- Storage audit: `/root` 81G, `/opt` 11G, `/var` 12G, Docker images ~5.316GB, ~1.315GB marked reclaimable; **none deleted**. In particular `/opt/mmw-staging` and other production projects are untouched. Separate Kaggle sparse checkout ~6.1MB. No broad directory cleanup is authorized.

## Source and test fixtures

1. Using GitHub over SSH, fetched the exact five pinned historical Flask (3) and Requests (2) commits into `/opt/kaggle/gemma-paper-upstream` (bare Git repositories). Download size approximately 7–9MB. Some full old tree checkouts were slow; a bounded full-tree qualification attempt timed out at job `job_01M72A39T900AWB8AP2NBW3WHG`. No arbitrary code was executed.
2. Recovered necessary exact source and test files only; compared the Git blob SHA-1 of each of the ten source/test files to its commit's blob ID. **10/10 match** at job `job_01M72AMQH000AEHPA4VZ7NBPA2`.
3. Archive integrity remained **10/10 gold/test patch SHA256** and **15/15 frozen prompt SHA256** PASS (previous verified Gateway job `job_01M729FZVC00P9VG18WKY8EVEK`).
4. `patch --dry-run --fuzz=0` applied to the exact archived source files: **5/5 test patches** and **5/5 gold patches** verified as applicable, job `job_01M72AE92R005P0ZTYD3PCKYGQ`.
5. Built **disposable source-only** patch qualification trees at `/opt/kaggle/gemma-paper-combined-v3`. Files touched by the patch headers (including new `tests/static/config.toml` for Flask-4992) were restored from the original pinned commits, followed by actual application of test patch, then gold patch with `patch --batch --forward --fuzz=0`. **5/5 task combinations applied cleanly; 5/5 modified Python file sets passed `ast.parse`**. Gateway job `job_01M72ARZRZ00H7G17EFMZC1658`. Some 2014 Requests docstrings emit Python 3.12 SyntaxWarning, not a SyntaxError.
6. Important transparent failure history: initial minimal-file combination check 4/5 because Flask-4045 test patch also touches `tests/test_basic.py`; follow-up attempt failed to recognize the *new file* `tests/static/config.toml` in Flask-4992; the corrected path-complete new-file-aware v3 qualification passed 5/5. None of those failures involved model inference, and they must not be represented as model failures.

## Actual CPU unit tests from exact GitHub checkout

- Fixed `run_in_docker` Python version acceptance (literal regex escaping) and added a randomized, unique `gemma-paper-cpu-<uuid4>` container name; Docker CLI timeouts now issue an explicit `docker rm -f` against exactly that name and **raise** if cleanup fails. Code commit `3a53050f3e43dff0387bbf60a9264c0e0cc0e99c`.
- Added mocked CPU-only tests of teardown, success and Python 3.9/3.10/3.11, commit `5fcc5dc40e5bcb672441db19f5f283de9c0f4956`. First run exposed missing `Path` in test AST namespace, corrected in `48155d56a0d73bb01afeb8aabb38b53953aa1a7e`.
- Gateway job `job_01M72AKS4Z0080AVYEH6C6NN1X`, exact checkout `48155d56a0d73bb01afeb8aabb38b53953aa1a7e`: **38/38 PASS** (13 guarded patch path + 10 immutable Docker-command builder + 8 pytest pass-count + 7 Docker timeout/Python-profile mock tests). These are true source tests, **not** only reconstructed versions.
- The 7 timeout tests use mocked `subprocess.run`: they do **not** establish successful cleanup of a real Docker daemon under abnormal termination. A real isolated container test is a future gate.

## Experiment gate / decision

**ACCEPTED — CPU-only static provenance and parser gates.**
**HOLD — actual upstream pytest RED/GREEN, container controls and model-generated patch execution.**

The target host lacks prepared offline, digest-pinned Python 3.9 / 3.10 / 3.11 test images with pinned Flask/Requests dependencies. No new image pulled owing to 95%-used disk, no direct model calls. Archived prior RED/GREEN logs are historical and not a fresh post-change test run. The five authentic upstream tasks provide only source/test eligibility evidence, **not** new Gemma generalization or leaderboard results.

Next action: decide whether a strictly budgeted, CPU-only sandbox image build can fit available disk and verify dependencies. Require explicit image digest and container teardown checks; then rerun five gold/base/malformed/regression controls. Never overwrite submitted Kaggle Writeup 115692 without user approval.
