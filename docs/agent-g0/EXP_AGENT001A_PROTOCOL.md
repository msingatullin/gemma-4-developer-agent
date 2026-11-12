# EXP-AGENT-001A — pre-registered one-variable candidate protocol

Date: 2026-11-12. Competition: Gemma 4 Developer Agent. Status: **CPU preflight only / no E4B inference authorized**.

## Hypothesis and expected improvement
The v15 issue locator uses `git grep ... -- *.py | head -20` without path exclusion. We **confirmed** Git's `*.py` pathspec can include nested `src/` files. The actual observed problem is that the first hits for generic issue tokens (e.g. `Blueprint` in public Flask HEAD) can be dominated by examples/tests before the actual implementation. A filename-first and source-only Git search may improve candidate-file prioritization at fixed call/time budget. This is a *hypothesis*, not measured SWE solve rate.

## Immutable baseline
Owner-authenticated Kaggle SDK downloaded **exact submitted v15 ZIP**, submission 58073369, SHA256 `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a`, 3321 bytes. Original raw archive is private at `/opt/kaggle/gemma-agent-g0-20261112-audit/submitted_archives/v15/58073369.raw` on VPS nuremberf. v15 Public Score 0.06 (E4B). Do not commit private submitted ZIP.

## Single change to test
Derive candidate by modifying **only one exact bullet inside `prompts/system.md`**: old unfiltered grep -> filename-aware, non-test/docs/examples implementation search using Git native pathspec. Keep `agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml`, and every other prompt byte identical. Do not introduce extra skills/tools/models, sampling settings or runtime budgets. Candidate must not rely on an unproven `/tmp/ast_locator.py` installation.

## Freeze / CPU validation
1. SHA256-check input ZIP before reading. Assert exactly four safe entries and a unique exact-match replacement anchor.
2. Build deterministic ZIP. Hash every member, compare baseline vs candidate and FAIL if any file besides `prompts/system.md` differs; check that other prompt lines remain untouched.
3. Run submission static validator against extracted candidate.
4. Run original-vs-filtered search on same pinned public repository HEAD with issue-derived tokens, record top hit file ordering, runtime and workspace cleanliness. **Do not use gold targets in agent inputs.** Model-free search diagnostics are not F2P/P2P.
5. Archive raw commands, environment, hashes, exit status, fixture limitations in a metadata report. No paid GPU or Kaggle submission.

## Criteria
- **CPU build gate PASS:** all exact-byte invariants + static validator pass; no source repo modifications; no oracle leak.
- **Search diagnostic PASS:** at least one genuine filtered search avoids example/test domination without hiding the relevant implementation and without excessive runtime (target <5 seconds on tested repository).
- **Actual candidate acceptance:** requires real Kaggle-equivalent harness proof plus paired E4B inference and independent F2P/P2P on frozen real issues, heldout replication, resource/budget review. Do NOT accept on CPU search results alone.
- If build gate fails or path-prioritization has no demonstrable signal, REJECT/REWORK 001A; retain v15 baseline.

Budget: free CPU on preexisting VPS, target <=20 min. GPU/RunPod/API: **not authorized**. Kaggle daily quota: **zero sends**. Issue: https://github.com/msingatullin/gemma-4-developer-agent/issues/7.
