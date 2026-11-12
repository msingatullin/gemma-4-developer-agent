# G0-NATIVE-SCHEMA-001 — official wheel subset validation protocol

Date 2026-11-12. This protocol is frozen before running the official schema checks.

**Goal:** run the organizer-released `adk-submission` **directory, YAML include, and Pydantic schema** implementation on four actual agent directories, with exact source/provenance hashes. This is intentionally **not** full `swegemma` native evaluator, model inference, skill execution, or `compile_submission`.

## Official source provenance

Owner-authenticated Kaggle SDK downloaded four **individual** pure Python wheels (total about 3.2 MB) from dataset `metric/gemma-4-developer-agent-wheelhouse` version **31**, verified by official Kaggle MCP metadata. Exact SHA256:
- `swegemma-0.2.11-py3-none-any.whl`: `9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3`
- `adk_submission-0.2.13-py3-none-any.whl`: `f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d`
- `adk_eval_core-0.1.0-py3-none-any.whl`: `e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3`
- `google_adk-1.36.1-py3-none-any.whl`: `1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0`

A clean isolated Python 3.12 virtualenv installs exact `adk-submission==0.2.13`, `pydantic==2.13.4`, `PyYAML==6.0.3`. **Do not resolve and install `google-adk`'s >100 transitive cloud dependencies or `vllm`/CUDA packages for this CPU-only structural check.** Import the official package's `discovery`, `schema`, `yaml_loader` and `limits` submodules from the verified installed wheel without importing its ADK-dependent `compiler` (explicit lightweight namespace package shim). This still **executes the real official structural-schema source**, but is a subset of the native evaluator.

## Cases and expected checks

1. Exact downloaded, immutable Kaggle E4B v15 submission `58073369` (ZIP SHA256 `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a`).
2. Exact downloaded Kaggle E4B v16 submission `58126337` (ZIP SHA256 `b6c470a38d4eb60a529b1f716e3d5a28b3f74b80f8197080549f1c3ee9c92a7c`).
3. `EXP-AGENT-001A` from frozen exact v15 archive, one change in prompt only (ZIP SHA256 `5a93228a86397ae247e3b3395ae82cc31d4f724f23a083ca18a0926dfc79cde0`).
4. GitHub isolated branch `agent/g0-portable-locator-20261112:v17_small_model_candidate` at exact branch commit recorded at execution.

For each directory: run official `validate_directory` with limits matching the organizer's `swegemma.config.build_submission_limits`, official `load_yaml` to resolve `!include`, official `SandboxedAgentConfig.model_validate` and review declared `skills` (if absent, skill files may be unreferenced even if packaged). Assert permitted model alias and no traversal; record successes and full failure details. Fail closed on missing, mismatched, extra or invalid files.

**Verdict boundaries:** PASS means the organizer's *structural and root-config schema subset* accepts that directory. **It does NOT mean `compile_submission` passed, that the skill is registered, that `/tmp/ast_locator.py` exists in sandbox, or that Gemma can solve any task.** The full harness/paired E4B model A/B gates remain HOLD.

Budget: $0 external spend, CPU-only VPS; no Kaggle submissions, no changes to production services or the frozen baseline.
