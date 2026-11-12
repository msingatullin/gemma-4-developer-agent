# EXP-AGENT-GPU-001 — three-arm authentic E4B feasibility pilot (APPROVAL REQUIRED)

Date: 2026-11-12. **PRE-REGISTERED, NOT AUTHORIZED, NOT STARTED.** Objective is to determine whether the real Gemma E4B agent makes **valid patch-producing, independently F2P/P2P scored** progress when only a file-search instruction changes. A positive private test is not yet a Kaggle leaderboard gain.

## Sources and comparison arms (immutable)

1. **Baseline V15:** actual owner-submitted Kaggle E4B sub58073369, Public 0.06, ZIP SHA256 `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a`.
2. **EXP-AGENT-002 (quote-only):** exactly same four source files, two literal quote characters inserted around shell `*.py` in one system prompt line, candidate ZIP SHA `90601ff0fbcd805e6e4a72b9767a464c5b56c4657d09897a8770ee475777882f`; all other bytes from v15 identical. [Protocol](EXP_AGENT002_PROTOCOL.md).
3. **EXP-AGENT-001A:** actual v15 ZIP with exactly one full search-bullet rewrite, containing casefold/filename-first/filtering, candidate ZIP SHA `5a93228a86397ae247e3b3395ae82cc31d4f724f23a083ca18a0926dfc79cde0`.

All three CPU structural/static and organizer `adk_submission.compile_submission` checks already **PASS** on E4B model alias `gemma-4-e4b-it-qat-w4a16-ct`, six identical tool names, original frozen model sampling and eval config.

## Prerequisite permission / resource hard caps

Owner has **NOT** approved consumption of Kaggle GPU. Official Kaggle MCP `get_accelerator_quota` on 2026-11-12 reports allowed **108000 seconds** (30h), used **29642.473 seconds**, reserved 0, refresh **2026-11-14T00:00:00Z**, leaving **78357.527 seconds (~21h45m58s)**. This is available quota, **not** evidence the E4B QAT W4A16 runtime works on free T4/P100.

**Request:** separate explicit authorization for maximum **90 minutes (5400 s) of FREE Kaggle GPU quota**, cash cap **$0**, no RunPod, paid APIs or external cloud deployment, **NO Kaggle competition submission**, no public notebook or publication, no unrelated training. If user does not approve, stop before accelerator allocation and continue only read-only/CPU work. Never use GPU implicitly. Reserve no daily Kaggle competition submission quota without separate confirmation.

## Staged, budget-aware genuine model protocol (only after approval)

- Phase F0: read-only confirm available GPU type, E4B model weights and official `swegemma` server compatibility; confirm explicit 5400s cap and private output location. If accelerator/weights inaccessible, abort without attempting a different paid backend.
- Phase F1: **3-arm paired feasibility** on **one identical pre-registered dev issue**, `pytest-dev__pytest-11143` (pinned commit `6995257cf470d2143ad1683824962de4071c0eb7`, G1-006 verified oracle). Use same actual E4B weights/quantization, temperature/seeds if supported, time/calls/token budgets and issue prompt; **only prompt search instruction differs**. Model must operate on original source snapshot **without gold patch, test patch or oracle tests in its task container**. Expose gold/test patches only to a separate offline evaluator after model output is frozen.
- Phase F1 hard limits: **30 GPU minutes maximum including model loading** unless user explicitly authorizes more; if initialization stalls 15 minutes or model execution fails under GPU type, stop and record exact failure. Three-arm full comparison may be infeasible in 30 min; report whichever arms actually finished and do NOT call it a paired test unless all three completed under identical conditions. Keep remaining GPU cap for only evidence-driven continuation.
- Phase F2: only if all three arms generate valid model patch traces and remaining cap permits, test additional **5 verified DEV issues** with fixed order `pallets__flask-4045`, `pallets__flask-4992`, `psf__requests-2148`, `pytest-dev__pytest-11148`, `pytest-dev__pytest-5103`. `pytest5103` must use the documented identical offline test dependencies and disabled plugin autoload in BOTH baseline/gold evaluations; its environment repair files must not appear in model source. Do not spend beyond total 5400s GPU quota. Task batch cutoff and results must be reported as partial if full pairing cannot finish.
- **Output per arm/task:** experiment ID, exact ZIP SHA, model-id/precision, run seed, pinned git tree SHA, start/stop times and GPU seconds, issue input SHA (no gold), tool calls, token/latency budget, raw model-generated diff SHA and apply status, F2P RED/GREEN and P2P result on independent original source, exceptions and source pollution checks, links to private raw logs and run manifest. The process must never manufacture a patch from the gold reference.
- Outcome metric: only a **real model-generated patch** that applies cleanly and passes independent F2P and selected P2P counts as solved, alongside timeout/error and compute use. Avoid comparison of different incomplete tasks or temperatures. Never infer leaderboard Public Score gain from private development tasks.
- **Promotion gate:** one issue is only infrastructure feasibility. For selecting a new best E4B implementation, need a larger **paired** heldout study; original project criterion >=2 net solved on 25 dev and positive independent heldout remains unmet by this pilot. Do not replace the best submitted v15 or submit a candidate without another explicit approval.

**Non-goals:** Kaggle Paper Track, Main31B optimization, rankings based solely on file retrieval, spending external money, releasing model output or public notebook.

## Preserved prerequisites

- G0 real organizer `adk_submission.compile_submission` all 3 arms PASS, real `swegemma` Docker tool and `extract_snapshot` CPU smoke PASS.
- G1 8/50 historical true offline RED→GREEN fixtures PASS (6 dev, 2 heldout, 3 repos), all gold patch used only in oracle, not agent solve.
- Dev-only model-free search ablation (same manually selected 9 issue tokens, no independent heldout): hit@5 baseline1/9, quote-only4/9, full001A4/9; hit@1 quote-only2/9, full001A4/9. Not model solve rate.

**Status:** **HOLD until owner consent for GPU**. Next owner action is explicit approval or rejection of the 90-minute free-GPU/$0/no-submission limit.

## 2026-11-12 owner authorization and cost-preserving accelerator selection (before allocating GPU)

In direct response to the question "Разрешаешь запустить приватный эксперимент ... максимум 90 минут бесплатного GPU Kaggle, $0, без отправок?" the owner replied **"продолжай"**. Treat that affirmative continuation as authorization for this **specific** experiment within the stated hard limits, not blanket approval for additional Kaggle sends, publishing or paid usage. Official Kaggle MCP reread: `get_accelerator_quota` used **29642.473/108000s**, reserved0, reset **2026-11-14T00:00Z**; latest competition rank 2203/5521, best E4B v15 Public0.06 and Main v11/v14 0.17 unchanged.

**Optimization of quota consumption:** Published competition rules say its special L4×4 notebooks spend 2× quota. Free T4×2 (as used previously in owner's private Kaggle notebook `gemma4-paper-b2-feedback-short-v2-free-t4`) consumes normal quota and provides two 16GB GPUs. For small E4B W4A16, **first attempt NvidiaTeslaT4 (x2), not L4×4**, because E4B is much smaller than 31B and user prioritizes minimizing spend. This is an unverified compatibility hypothesis; stop and report if incompatible, do not silently switch to L4×4. Attach only official model `google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2`, verified through owner's Kaggle API `model_instance_versions_list` (version ID897264) and use a **private** competition-attached Kaggle script; no public notebook or Kaggle competition submission. Cash spend hard cap $0, total Kaggle GPU charged time <=5400 seconds across all stages.

**Stage F0 hard gate (before actual F1 three-arm):** create a new private Kaggle script `msingatullin/gemma-agent-e4b-private-gpu001-f0`, Kaggle `is_private=true`, `enable_gpu=true`, accelerator `NvidiaTeslaT4`, attached official E4B model, no competition submission; script must enforce elapsed **<=900 seconds** GPU T4 using process `signal.alarm` and API `kernels_push(...timeout='900', acc='NvidiaTeslaT4')` bound (check actual API). Read/record GPU hardware, exact attached weight directory/config/hash of `config.json` and installed vLLM version, load E4B QAT in vLLM (prefer already installed matching version, only pip install package if needed within bound), produce **one authentic local short completion** from model; no task patch claims. The first model/token output is pure feasibility; if no GPU, weights or compatible vLLM, classify BLOCKED and do not spend further quota. Any runtime cap applies to ALL program steps including installs. After completion, audit used quota via official Kaggle MCP and ensure consumption remains within total5400s. Stage F1 three-arm paired patch work can start only if F0 succeeds and remaining charged quota permits.

This amendment clarifies the prior "APPROVAL REQUIRED" heading: **owner approved specific capped pilot on 2026-11-12**; F0/F1 actual execution remains subject to compatibility and hard ceilings.
