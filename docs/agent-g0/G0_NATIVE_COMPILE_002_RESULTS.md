# G0-NATIVE-COMPILE-002: organizer ADK compiled 4/4 with a nonexecuting tool registry

Date: 2026-11-12. **Decision: CPU compilation gate PASS for all four frozen directories; native task sandbox / Gemma inference gate remains HOLD.**

## Provenance

Actual organizer wheelhouse: Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse` **v31** (owner `metric`, authenticated Kaggle SDK). Selectively downloaded 4 small wheels, not the whole 880.8-MB wheelhouse:

| Distribution | Version | SHA256 |
|---|---|---|
| `swegemma` | 0.2.11 | `9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3` |
| `adk-submission` | 0.2.13 | `f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d` |
| `adk-eval-core` | 0.1.0 | `e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3` |
| `google-adk` | 1.36.1 | `1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0` |

An isolated Python 3.12 venv installed the real `google-adk` host-side dependencies (**without** GPU/vLLM/torchvision). `from google.adk.agents import Agent` returned **PASS**. No model server was contacted.

## Actual official tests

[Pre-registered CPU compile protocol](G0_NATIVE_COMPILE_002_PROTOCOL.md). The test invokes **real** `adk_submission.compile_submission` with limits and token generation constraints copied from the organizer `swegemma.config.build_submission_limits`. Models are mapped by their E4B aliases to test-only model names. All six tool names are registered to **throwing stubs**, so they cannot run shell commands or send network calls. This is not the real `SwegemmaContext.create_tools` registry.

| Version | Actual ADK compile result | Agent class | Declared tools | Skills enabled |
|---|---|---|---:|---|
| E4B v15 — Kaggle sub58073369 | PASS | `LlmAgent` | 6 | No |
| E4B v16 — Kaggle sub58126337 | PASS | `LlmAgent` | 6 | No |
| EXP-AGENT-001A — unsubmitted one-bullet v15 candidate | PASS | `LlmAgent` | 6 | No |
| Experimental v17 branch | PASS | `LlmAgent` | 6 | **No** (packaged unused skill) |

[Complete actual official compiler output](G0_NATIVE_COMPILE_RESULTS.json), SHA256 `00cc5f77836e2bc45cba56cb430e4a55eb9167e3100dfdaa05df31543da872c5`. [Deterministic test source](../../scripts/agent_g0_real_adk_compile.py).

Earlier organizer **structural schema subset** validation also passed 4/4: [raw official validation](G0_NATIVE_SCHEMA_RESULTS.json), SHA256 `1ae3c79f8c9b50449d56154548241a44dd1a2358b34ad449ea3b053e9f01b24b`. That is strictly weaker than the full compile shown above, and both are weaker than an end-to-end scored model run.

## Confirmed v17 skill integration blocker

In the submitted v17 candidate directory, `skills/repo_locator/SKILL.md` and `skills/repo_locator/ast_locator.py` are packaged, but **`agent.yaml` contains no `skills` declaration**. Official unmodified organizer `adk_submission/resolvers/tools.py:resolve_skills` returns `None` immediately when `config.skills` is empty (source lines ~150–151 in wheel v0.2.13). `adk_submission/builders/llm.py` only appends the `SkillToolset` when `resolve_skills` produced one. The actual compiled v17 therefore has only its six declared ordinary tools, **no SkillToolset**. This is a stronger finding than the previous directory-only audit.

Further, official `swegemma/harness/agent_runner.py` compiles the agent separately from its task snapshot; `swegemma/harness/container_setup.py:extract_snapshot` places the task repository under `/workspace`, while `run_command` executes inside that isolated container. None of the inspected default setup stages the packaged `ast_locator.py` at the exact `/tmp/ast_locator.py` path assumed by old v17 instructions. Absence of a special hidden runtime staging hook cannot be proved from source inspection alone; **there is no demonstrated delivery**. The portable guarded `git grep` fallback is the only verified way for current v17 to search implementation source in the clean CPU workspace.

**Decision:** v17 is **NOT ELIGIBLE FOR END-TO-END UPLIFT CLAIMS** and remains HOLD. For Small Model optimization, prioritize exactly one variable based on archived v15 (`EXP-AGENT-001A`), not the multi-change v17 package.

## Next blocker and honest boundary

Full `swegemma` task executor with official Container A/B behavior was **not run**: `swegemma` depends on additional runtime packages (including model-serving libraries); the host venv intentionally omits vLLM/CUDA/torchvision to avoid unapproved GPU and unnecessary downloads. The official ADK compiler success is *not* a model solve, a Kaggle public score, or evidence a skill script works in Container A.

G1 independent RED→GREEN/P2P offline oracles now pass **6 of the 50 frozen tasks**, including 4 dev and 2 heldout from three repositories, but these used gold patches in the offline evaluator, not Gemma-generated patches. Real paired E4B model inference is unexecuted. No paid resources, no Kaggle daily quota consumed. Protected baselines remain v15 E4B Public 0.06 and v11/v14 31B/Main Public 0.17.
