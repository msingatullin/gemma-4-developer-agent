# G1-001 — genuine SWE-bench oracle bring-up: Flask 4045

**Date:** 2026-11-12  
**Decision:** **PASS for the one-task CPU RED/GREEN/P2P oracle**; **NOT** an agent solve-rate result.

## Frozen inputs

- Real upstream task: `pallets__flask-4045` from SHA-frozen manifest `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`.
- Original repository checkout: `d8c37f43724cd9fb0870f77877b7c4c7e38a19e0` for BOTH independent copies.
- Task's official test patch SHA256 `def1da53a3857f67b571f108abde6fcdac61da5c7820c0749fa7c487fe87a62a`.
- Gold source patch SHA256 `6c4055e1cb35cf9c5d50bbba639af1787d6f5d5146f9539cedc364a43d01c687`.
- Protocol **committed before evaluation**: [G1_001_ORACLE_PROTOCOL.md](../agent-g0/G1_001_ORACLE_PROTOCOL.md).
- Pre-existing CPU image: `gemma-paper-cpu:py310-20261110` (Python 3.10.22, pytest 6.2.5), Docker `--network none --read-only --cpus 1 --memory 768m --pids-limit 64`, source mount read-only.

## Actual pytest results

| Checkout | Test group | pytest process | Evidence |
|---|---|---|---|
| Original BASE + official test patch | **F2P** (2 tests) | **2 failed, exit 1** | Missing expected `ValueError` and incompatible endpoint assertion |
| Gold source patch + same test patch | **F2P** (same 2) | **2 passed, exit 0** | Exact regression fix works |
| Gold source patch + same test patch | **P2P** (2 distinct tests) | **2 passed, exit 0** | Independent regression subset |
| Original BASE + official test patch | **P2P** (same 2) | **2 passed, exit 0** | Supplemental post-protocol control confirms both were already green |

The two BASE failures were **actual behavior assertions**, not import errors or missing test collection. Both checkouts have identical pinned HEAD; BASE contains only the applied test patch; GOLD additionally contains the isolated gold source patch.

[Raw Docker stdout/stderr, exit codes, pinned hashes and exact tests](G1_001_VERIFIED_EVIDENCE.json).

## Limitations and next step

This experiment validates **one historical task oracle**. It did NOT call Gemma E4B, run v15/v17, measure patch generation, establish any new Kaggle score, or prove full 50-task coverage. The gold patch and test patch are used **only inside the offline evaluator**, never supplied to an agent.

The previously planned native `swegemma`/ADK runner is still not installed in checked VPS Python environments; no actual Kaggle task sandbox session has been replayed. Move to a diverse 6–8-case genuine RED/GREEN/P2P fixture check, freeze held-out cases, then request approval for bounded paired E4B inference if compatibility gates pass. **Retain v15 E4B and v11/v14 Main as protected baselines.**

Cost: $0 new GPU/API/RunPod. Contest submissions: 0.
