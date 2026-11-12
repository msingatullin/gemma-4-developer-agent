# G1-002 / G1-003: real multi-repository RED→GREEN + P2P oracle proof

Date: 2026-11-12. **Result: 2/2 selected additional real tasks PASS as CPU evaluator fixtures.**

These are **genuine pinned repository tests** using historical code and the manifest's test/gold patches in an **offline oracle**. They are **not** Gemma-generated solutions, not official Kaggle evaluator results, and not independent model performance estimates.

## Reproduction contract

[Pre-registered protocol and storage-method addenda](G1_002_003_PROTOCOL.md) were saved before their corresponding runs. Frozen task manifest SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`; task IDs both belong to the development split, neither to heldout.

Both historical upstream bare repositories use shallow/promisor storage. Direct fetch of requested old commits returned missing-parent errors. The historical trees and their tracked blobs remained present. We therefore extracted **exact `git archive` snapshots** and checked full local Git tree SHA against the historical commit's tree before test/gold patching (not just a file-name list). Flask initially omitted two tracked dotenv files on `git add -A`; corrected using `git add --force --all`, with full tree-hash equality verified on both independent copies. No source reconstruction or replacement commit revision was silently accepted.

Isolated offline Docker: `--network none --read-only --cpus 1 --memory 768m --pids-limit 64`, source bind-mounted read-only, pytest cache disabled. No network installs, GPU, external model calls, or Kaggle submission.

## Actual pytest outcomes

| Task | Historical source commit | BASE F2P | GOLD F2P | BASE P2P | GOLD P2P |
|---|---|---|---|---|---|
| `pallets__flask-4992` | `4c288bc97ea371817199908d0d9b12de9dae327e` | **1 failed** (missing `text` argument) | **1 passed** | **2 passed** | **2 passed** |
| `psf__requests-2148` | `fe693c492242ae532211e0c173324f09ca8cf227` | **1 failed** (uncaught socket `OSError`) | **1 passed** | **2 passed** | **2 passed** |

Flask pinned tree `2ba551370f1a4204efbab1f82ba6cfd611634723`; Requests pinned tree `319437ae6f0d767c5885aff9d2c08cfe95e91e31`. Both exact source snapshots verified before applying offline patches.

### Environmental failure handled separately

The existing Python 3.10 container has Werkzeug 2.0.1 and cannot load this historical Flask (its `LocalProxy` lacks `unbound_message`); the resulting pytest exit 4 was correctly classified **ENV_BLOCKED**, not evidence of task failure. A **pre-existing** Python 3.11 Docker image with Werkzeug 2.3.8 imported Flask successfully, then gave genuine RED→GREEN and P2P results. Requests used pre-existing Python 3.9 and genuinely failed/then passed its socket-error test.

[Actual full logs, exit statuses, original pinned trees, selected F2P/P2P tests and patch hashes](G1_002_003_VERIFIED_EVIDENCE.json). Private evaluation snapshots remain on VPS. Evidence JSON file SHA256 `05e2457e9b5ab68dfdad5e3df364d5504856d258caab93263ba2716c9d4448cc`.

## Decision and next gate

The earlier Flask-4045 G1-001 fixture plus these two tasks establish **3 genuine oracle-verified development tasks from two upstream repositories out of the 50 frozen manifest cases**. This is infrastructure readiness only. It does not demonstrate any candidate Gemma E4B gain.

Continue with heterogeneous repository cases and heldout oracle validation. The official `swegemma` / `adk-submission` / `adk-eval-core` execution stack remains unverified in the CPU VPS Python environments, and real paired E4B inference has **not started**. Protect v11/v14 Main (Public 0.17) and v15 E4B Small (Public 0.06) until a controlled actual model test supports replacement.

**Cost:** no new paid computing. **Competition sends:** 0.
