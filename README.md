# AST-Guided Verification Suite for Gemma 4

**Deterministic code navigation, pre-flight validation, and assertion-aware traceback compression for local software-engineering agents.**

[Kaggle Paper Track submission](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/ast-guided-deterministic-gemma4-agent) · [Executable Kaggle notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4) · [Research paper](paper/writeup.md) · [Русская версия](README.ru.md)

**Project:** Google Gemma 4 Developer Agent / Paper Track (2026)  
**Model used for the empirical study:** `google/gemma-4-31B-it-qat-w4a16-ct`  
**License:** [Apache 2.0](LICENSE)

## What this repository contributes

The AST-Guided Verification Suite is a reproducible research prototype combining:

1. **AST-guided symbol indexing and code slicing:** deterministic retrieval of relevant Python functions and classes without asking the language model to read entire source files.
2. **Pre-flight syntax validation:** a Python `compile(..., mode='exec')` gate that checks candidate code before test execution.
3. **Traceback compression with diagnostic safeguards:** filtering pytest banners and captured output while retaining failure anchors, exception evidence, and a conservative fallback.
4. **Assertion-aware traceback compression (B2):** preservation of test expectations, including `pytest.raises(..., match=...)`, adjacent assertions, and surrounding failure context.

The repo contains both a developer-agent submission workflow and a separate **Paper Track research study**. The findings below apply to the latter; they are **not** a claimed SWE-bench issue-resolution score.

## Real Gemma 4 inference and patch-execution results

We collected **150 live inference responses** from quantized Gemma 4 31B: an initial pre-registered 120-call comparison of four traceback treatments and an additional **30-call post-hoc exploratory** test of B2. Each treatment covers **15 self-contained synthetic bug reproductions** inspired by open-source Python bug patterns, evaluated with two seeds (`42`, `100`). Generated patches were subsequently evaluated with pytest in an unprivileged Docker environment configured without network access.

| Input variant | Model calls | Patches passing pytest | Mean total API tokens / call | Token reduction vs raw |
| --- | ---: | ---: | ---: | ---: |
| **A — full pytest output (`--tb=auto`)** | 30 | 30/30 (100.0%) | 1,158.3 | Baseline |
| **B — AST traceback compressor v1** | 30 | 25/30 (83.3%) | 792.8 | 31.5% |
| **B2 — assertion-aware compressor v2** | 30 | **29/30 (96.7%)** | **706.0** | **39.1%** |
| **C — last 35 traceback lines** | 30 | 30/30 (100.0%) | 1,000.7 | 13.6% |
| **D — no traceback** | 30 | 22/30 (73.3%) | 536.6 | 53.7% |

**Interpretation:** B2 recovered four net successful patches relative to B while using fewer total API tokens. It is an **exploratory post-hoc refinement**, designed after inspecting failures in B, so these numbers do **not** establish unbiased superiority, statistical equivalence, or non-inferiority to A or C. In this small synthetic dataset, A and C still achieved the highest observed patch pass rates. `Total API tokens` includes both input and output, **not just prompt tokens**.

**Why assertion context matters:** v1 sometimes removed `pytest.raises(..., match=...)` requirements or adjacent test assertions. This caused the model to fix the exception class but miss its required message, or handle only one side of a two-sided assertion. B2 retains those constraints. One B2 candidate still failed on a 303 redirect body-clearing test.

### Evidence and reproducibility

- [Paper Track writeup](paper/writeup.md) — methodology, benchmarks, uncertainty, limitations, and experimental comparisons.
- [AST traceback compressor implementations](paper/traceback_compressor.py) — baseline and assertion-aware `filter_pytest_log_v2`.
- [Synthetic task sources and tests](paper/e2e_gemma_experiment/tasks/) and [task manifest](paper/e2e_gemma_experiment/task_manifest.json).
- [Frozen inference inputs for all variants](paper/e2e_gemma_experiment/frozen_prompts/) — including **all 15 B2 task prompts**.
- [Initial 120 real model responses](paper/e2e_gemma_experiment/real_run_20261108/real_experiment_checkpoint.jsonl) and [original patch test results](paper/e2e_gemma_experiment/real_run_20261108/real_patch_execution_results.jsonl).
- [30 B2 model responses](paper/e2e_gemma_experiment/real_run_20261108/real_b2_experiment_checkpoint.jsonl), [B2 patch test results](paper/e2e_gemma_experiment/real_run_20261108/real_b2_patch_execution_results.jsonl), and [B2 analysis](paper/e2e_gemma_experiment/real_run_20261108/real_b2_patch_execution_analysis.json).
- [Full B2 experimental report](paper/e2e_gemma_experiment/real_run_20261108/REAL_B2_EXPLORATORY_REPORT.md) and [container-based evaluator](paper/e2e_gemma_experiment/run_container_execution_eval.py).
- [Deterministic benchmark and pytest evidence](paper/traceback_experiment/) and [public executable notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4).

**Reproduction outline:** inspect the task manifest and frozen prompts; run the deterministic tests locally; use the archived inference responses to reproduce the offline patch-test evaluations and task-clustered summaries. Regenerating model responses requires access to the same Gemma 4 checkpoint and a compatible inference runtime. Run model-produced patches only inside an appropriately isolated, unprivileged environment.

### Scope and limitations

- The 15 evaluated tasks are **synthetic, self-contained reproductions**; they are not genuine upstream repository checkouts or SWE-bench issue-resolution runs.
- A separate [five-case upstream archive](paper/e2e_gemma_experiment/real_repo_sample/) contains original issue and patch material for reference, but **was not executed in this model evaluation**.
- The B2 results are explicitly **post-hoc exploratory**. The paired sample is too small to demonstrate non-inferiority or generalization to unseen repositories.
- Some diagnostic rubric misses reflect keyword sensitivity; the supplementary error taxonomy is **rule-based post-hoc analysis**, not an independent blinded human study.
- Observed patch pass rates are limited to the included tests and do not establish production readiness.

## Repository map

| Directory | Purpose |
| --- | --- |
| [`paper/`](paper/) | Paper, deterministic component benchmarks, traceback compressor and research artifacts |
| [`paper/e2e_gemma_experiment/`](paper/e2e_gemma_experiment/) | Frozen prompts, tasks, 150-response empirical dataset, execution evaluation |
| [`submission/`](submission/) | Agent configuration and packaging assets for the separate Developer Agent track |
| [`tools/`](tools/) | Local validation and helper scripts |
| [`docs/`](docs/) | Project documentation |

## Competition and attribution

This repository supports the [Google Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent) and the separate [Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper). The Kaggle Paper Track entry is the canonical submitted research summary; repository artifacts provide reproducibility material. The Paper Track submission deadline is **November 12, 2026 (23:59 UTC)**.

**Author:** Mikhail Singatullin (`msingatullin`). Licensed under Apache 2.0.
