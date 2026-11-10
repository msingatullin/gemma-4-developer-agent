# Gemma 4 Paper Track — real upstream reference patch CPU validation

**Date:** 2026-11-10. **Experiment ID:** `PAPER-CPU-REAL5-20261110`. **Purpose:** establish an executable, zero-GPU gold-reference control for five authentic pinned upstream issues, not measure Gemma repair efficacy.

## Baseline and hypothesis

- Reference: five immutable upstream SWE defect cases (Flask ×3, Requests ×2) from `real_repo_sample/manifest.json`; 10 source/test patch SHA256s and 15 frozen A/B2/C prompt SHA256s separately verified.
- Hypothesis: each pinned base with frozen test patch produces a task-specific **RED**, then the historical upstream gold patch yields **GREEN** and preserves the explicitly selected offline P2P test subset.
- Budget: **$0 incremental paid compute; no GPU**; existing Gateway SSH host `nuremberf`, Ubuntu 24.04, CPU-only, isolated Docker images, without disrupting running production services.
- Experimental independence: gold patches are used **only** in offline reference qualification; **never** injected into prompts sent to Gemma. Model inference was **not** performed.
- Frozen generation inputs unchanged.

## Actual results (from SSH, not simulated)

| Upstream instance | Python | RED F2P | Gold GREEN F2P | P2P RED baseline | P2P GREEN gold |
|---|---|---|---|---|---|
| `pallets__flask-4045` | 3.10 | 2 failed | 2 passed | 47 passed | 47 passed |
| `pallets__flask-4992` | 3.11 | 1 failed | 1 passed | 18 passed | 18 passed |
| `pallets__flask-5063` | 3.11 | 2 failed | 2 passed | 4 passed | 4 passed |
| `psf__requests-1963` | 3.9 | 1 failed | 1 passed | 43 passed | 43 passed |
| `psf__requests-2148` | 3.9 | 1 failed | 1 passed | 43 passed | 43 passed |

**Final independent log audit:** 5/5 correct initial failing RED sets, 5/5 GREEN, 5/5 successful P2P before, 5/5 after, **155 green P2P tests**. Run `job_01M72CK55Y00ZNT468T2G0BQA0`, report SHA256 `67398529c32d8bc08c56eaeb2e5390d5510507f4f46f2541b6d62e4960ffb5eb`.

Full per-case exit codes, log SHA256 digests, exact image IDs and aggregate verification are published as [CPU_UPSTREAM_RED_GREEN_20261110.json](CPU_UPSTREAM_RED_GREEN_20261110.json), commit `85e342038b4115e49e1d2baad2400890023f096a`. Original raw pytest logs remain on the SSH server at `/opt/kaggle/gemma-paper-cpu-runs/{flask4045,flask4992,flask5063,requests1963,requests2148}` and are content-hashed in JSON; not all logs are uploaded to GitHub.

## Isolation and reproducibility

Each test run used the matching immutable **local Docker content ID**:

- Python 3.10: `sha256:8eb06d4197a52bc0a21cdbc733523a94fb6ebb1b7daad3854d985e77c5f5e47b`.
- Python 3.11: `sha256:ed700cf7dbc0604bed4374b3a027596162ac72b7ba6983d3c5b92988d527cc74`.
- Python 3.9: `sha256:80e945d7246b7d943fbbe20dbd5f3c010ed9e43c5ad85313164a2d84a1f0edb5`.

The images contain CPU-only pip dependencies installed into isolated bootstrap containers. Source cases use pinned real upstream commits; separate isolated `red` and `green` trees are copies with identical `test_patch.diff` (green additionally receives `gold_patch.diff`). Commands passed `--pull never --network none --cap-drop ALL --security-opt no-new-privileges --read-only --user 65534:65534 --pids-limit 64 --memory 1g --cpus 1 --tmpfs /tmp:rw,nosuid,nodev,size=128m,mode=1777`, Python bytecode disabled, `PYTHONPATH` restricted to checked-out source; worktree bound `readonly`, `-p no:cacheprovider`. Per-run explicit names and time bounds; no active `gemma-paper-cpu-` containers after completion, original `shadowtalk-postgres` untouched.

**Known execution adjustments (all disclosed):** first Requests-1963 attempt exited on missing `requests.utils` due incomplete lazy Git checkout; original upstream package completed before successful RED/GREEN rerun. The Requests reports use the **rerun** logs. Attempts on Flask-4045/4992 initially omitted some touched test files; corrected source-tree reconstruction handling extra `tests/test_basic.py` and newly created `tests/static/config.toml` before this final execution. None of these environment failures were counted as a genuine model outcome. Docker Buildx was absent, so small locally pinned images were provisioned without modifying system packages.

## Results and scientific interpretation

**ACCEPT reference-control feasibility** for these five curated authentic issues. Demonstrates original failure and historical gold fix under offline tests with no selected P2P regressions. **Does not establish** that Gemma 4 produced any of these patches, that assertion-aware B2 improves real-repository performance, broader cross-repo generality, or statistical noninferiority.

The published main experiment continues to be **150 Gemma4 responses from 15 synthetic local task reproductions**; B2 is **post-hoc exploratory**, A and C outperformed B2 on observed synthetic fix rate. Honest evaluation must preserve this distinction.

## Follow-up gates

1. Wire actual model-generated patch evaluator into these pinned images and fixed isolated tests (including complete fail-closed results, timeout cleanup and output-label integrity) before running any model code. Existing five gold controls do not replace the evaluator's 12 post-change controls.
2. Obtain genuinely evaluated non-gold model patches on these five real cases **only with separate authorization for GPU/inference resources**. No inference or Kaggle publication changes in this operation.
3. If results are obtained, log per-case A/B2/C quality and task-level uncertainty with small-N caveat. Do not claim win probability or generalization from five samples.
4. Verify final Kaggle Writeup text/word count, citations and submission status. Official read-only Kaggle MCP on 2026-11-10 still showed Writeup `115692` as `PUBLISHED`, deadline `2026-11-12 23:59 UTC`.

**Disk:** ~6.0 GiB available and root ~96% used after controlled Python container setup; no production data/images removed. New CPU resources only, no added paid charges, no GPU.
