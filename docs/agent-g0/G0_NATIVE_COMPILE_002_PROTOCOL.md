# G0-NATIVE-COMPILE-002 — preregistered actual organizer ADK compile smoke

Date: 2026-11-12. This record is frozen **before** the compilation attempt.

## Goal and source provenance

Run the **unmodified real** `adk_submission.compile_submission()` from organizer-owned Kaggle wheelhouse dataset `metric/gemma-4-developer-agent-wheelhouse` version 31 (`adk-submission 0.2.13`), together with official `google-adk 1.36.1` imports, on four frozen E4B submission directories. This **does not** invoke Gemma, vLLM, Kaggle scoring, network model APIs or private scoring data.

Organizer wheels SHA256:
- `swegemma-0.2.11`: `9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3`
- `adk_submission-0.2.13`: `f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d`
- `google_adk-1.36.1`: `1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0`

Local isolated Python 3.12 `schema_venv` now has official Google ADK installed with its host dependencies. **Do not install vLLM/CUDA/torchvision or run any model.** The real `adk_submission` compiler can be invoked with an organizer-like but explicitly **synthetic test registry**.

## Four immutable inputs

1. Original Kaggle E4B v15 submission `58073369`, ZIP SHA256 `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a`.
2. Original Kaggle E4B v16 submission `58126337`, ZIP SHA256 `b6c470a38d4eb60a529b1f716e3d5a28b3f74b80f8197080549f1c3ee9c92a7c`.
3. Unsubmitted one-variable `EXP-AGENT-001A`, ZIP SHA256 `5a93228a86397ae247e3b3395ae82cc31d4f724f23a083ca18a0926dfc79cde0`.
4. Current isolated branch `agent/g0-portable-locator-20261112:v17_small_model_candidate`, exact Git commit recorded in output.

## Actual compilation contract

Construct `ModelRegistry` mapping the declared E4B alias to itself; use `ToolRegistry` with the six official tool names and **throwing no-op test functions that must never be called**. Use limits and generation ranges matching `swegemma.config.build_submission_limits`. Call the real `compile_submission` once per input. Assert returned ADK `BaseAgent`/class and root model alias, prompt contents, declared tools, and inspect skill registration. The test must perform no tool invocation, no network model calls, and no grading.

**PASS:** official compiler constructs a valid `BaseAgent` for the input with no errors. **FAIL:** compile exception, report exact error without guessing cause. **WARNING** if packaged `SKILL.md` is not listed in the agent config's `skills` field; such a file should not be assumed active. Import success or schema-only success is weaker than compile success.

**Strict limitations:** synthetic tool registry is not `SwegemmaContext`'s actual tool implementation; skill staging and `/tmp/ast_locator.py` availability in Container A remain unverified; no Gemma output, F2P, P2P, real Kaggle score. No submitted ZIPs or best baselines are changed. No GPU, paid API, RunPod, Kaggle sends or production changes.

Expected incremental spend: $0, existing VPS CPU and isolated venv.
