# Pre-Registered Evaluation Protocol: Authentic Upstream Repository Holdout (Phase 1/2)

**Document Status:** FROZEN & IMMUTABLE PRIOR TO INFERENCE  
**Repository:** https://github.com/msingatullin/gemma-4-developer-agent  
**Date:** 2026-11-08  
**Governing Issue:** msingatullin/gemma-4-developer-agent#6  
**Target Venue:** Kaggle - Google Gemma 4 Developer Agent Paper Track (Deadline: Nov 12, 2026 23:59 UTC)  

---

## 1. Scientific Objectives and Hypotheses

### 1.1. Core Hypothesis
AST-guided traceback compression (`B2_assertion_aware`) retains bug-fixing accuracy comparable to raw tracebacks (`A_raw`) and naive tail truncation (`C_tail35`) when evaluated on genuine, multi-file open-source repositories, while achieving substantial token savings (-45% to -75% on failure tracebacks) by eliminating redundant stack noise while strictly preserving failure assertions and context managers (`pytest.raises(..., match=...)`).

### 1.2. Methodological Discipline
- **Pre-Registration:** This protocol, task manifest, and prompt set are permanently frozen before any new model call.
- **Exploratory Labeling:** The 15-task synthetic experiment established B2 as post-hoc exploratory. This 5-task genuine upstream holdout serves as an out-of-distribution validation check.
- **Negative Result Policy:** If B2 underperforms C or A on this sample, this negative result will be reported transparently in the paper without iterative prompt tuning.

---

## 2. Pinned Task Selection & Eligibility

Five authentic defects from public open-source repositories (`pallets/flask` and `psf/requests`) were selected from the SWE-bench benchmark and independently verified through the CPU qualification gate.

| Instance ID | Upstream Repo | Base Commit | Py | Target Module | Fail-to-Pass (F2P) Target Test |
|---|---|---|---|---|---|
| pallets__flask-4045 | pallets/flask | d8c37f4372 | 3.10 | src/flask/blueprints.py | tests/test_blueprints.py::test_dotted_name_not_allowed |
| pallets__flask-4992 | pallets/flask | 4c288bc97e | 3.11 | src/flask/config.py | tests/test_config.py::test_config_from_file_toml |
| pallets__flask-5063 | pallets/flask | 182ce3dd15 | 3.11 | src/flask/cli.py | tests/test_cli.py::TestRoutes::test_subdomain |
| psf__requests-1963 | psf/requests | 110048f983 | 3.9 | requests/sessions.py | test_requests.py::TestRedirects::test_requests_are_updated_each_time |
| psf__requests-2148 | psf/requests | fe693c4922 | 3.9 | requests/models.py | test_requests.py::RequestsTestCase::test_iter_content_handles_socket_error |

### Selection Criteria:
1. Public open-source repository with permissive license (Flask: BSD-3-Clause, Requests: Apache-2.0).
2. Pinned git commit SHA for immutable checkout.
3. Clean, offline reproduction: test suite executes without external network access (mocked HTTP sessions).
4. Deterministic test behavior: verified RED at base commit, verified GREEN with reference patch, zero regressions on unaffected modules.

---

## 3. Matched Experimental Variants

Each task is evaluated across three strictly matched variants with identical problem statements, system prompts, and source code context:

1. **`A_raw` (Uncompressed Baseline):**
   Full verbatim pytest traceback output emitted by the failed test execution.
2. **`B2_assertion_aware` (Proposed Treatment):**
   AST-guided filtered traceback produced by `filter_pytest_log_v2`. Preserves `pytest.raises(..., match=...)`, `assert` statements, carets (`^^^^^`), and up to 3 lines of test context, while pruning verbose traceback frames and captured logging noise.
3. **`C_tail35` (Heuristic Compression Baseline):**
   Simple naive tail cap retaining the last 35 lines of pytest output.

---

## 4. Prompt Blinding & Zero-Leakage Guarantee

To prevent data contamination:
1. **Source Code Extraction:** All module code embedded in the prompts is extracted directly from the bare git repository at the exact `base_commit` (`git show {base_commit}:{target_file}`), guaranteeing zero patch content.
2. **Blinded Prompts:** Prompts contain only the upstream issue text, base source code, and test failure traceback. No target symbols, test expectations beyond emitted tracebacks, or reference code are provided.
3. **Automated Audit:** Pre-inference audit script (`check_gold_leakage.py`) certifies that 0 added lines from `gold_patch.diff` appear anywhere in the prompts.

---

## 5. Inference Specifications (Phase 2)

- **Model:** Gemma 4 31B (hosted on dedicated RunPod instance with vLLM / HuggingFace).
- **Decoding Parameters:**
  - Temperature: `0.0` (greedy deterministic decoding).
  - Top-P: `1.0`.
  - Max New Tokens: `2048`.
  - Repetition Penalty: `1.0`.
- **Sample Size:** 15 inference runs (5 tasks x 3 variants).
- **Budget Ceiling:** RunPod spend strictly capped within remaining authorized balance (<$20 total project cap; expected run cost ~$0.50-$1.00). Automatic teardown in `finally` block with active pod verification.

---

## 6. Execution Sandboxing & Patch Evaluation

Model-generated patches are evaluated in an isolated execution container:
- Sandboxing: `--network none --cap-drop ALL --pids-limit 64 --memory 512m` (or dedicated isolated subprocess environment).
- Execution timeout: 60 seconds per test run.
- Outcome Classification:
  - **RESOLVED (Pass):** All F2P target tests pass AND zero P2P regression tests fail.
  - **FAILED_F2P (Fail):** Target F2P tests continue to fail.
  - **SYNTAX_ERROR (Fail):** Generated patch does not apply cleanly or contains Python syntax errors.
  - **REGRESSION (Fail):** Target test passes but existing test suite breaks.

---

## 7. Statistical Analysis Methodology

- **Unit of Analysis:** Independent task (N=5).
- **Comparison:** Paired comparisons between variants (B2 vs A, B2 vs C).
- **Significance Testing:** Exact McNemar test for paired binary pass/fail outcomes.
- **Confidence Intervals:** 95% bootstrap confidence intervals (10,000 resamples) for token reduction percentages and character reduction deltas.
- **Sample Size Limitation Caveat:** With N=5, this holdout has statistical power to detect large effect sizes or catastrophic failures, but cannot establish fine-grained equivalence. It is explicitly reported as a focused out-of-distribution validation study.
