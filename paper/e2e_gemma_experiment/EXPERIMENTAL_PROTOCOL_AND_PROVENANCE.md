# Gemma 4 E2E Benchmark Protocol and Provenance Specification

This document formally specifies the experimental conditions, evaluation criteria, dataset provenance, and statistical framework for the Gemma 4 E2E diagnostic study.

## 1. Dataset Provenance and Structural Separation

### A. Evaluated Suite: 15 Synthetic Reproductions
- **Directory:** `paper/e2e_gemma_experiment/tasks/` (15 tasks)
- **Provenance Statement:** 15 self-contained synthetic reproduction modules inspired by recurring open-source bug patterns from popular libraries (Flask, Requests, Click, Jinja2, Urllib3, Rich, Pluggy, Marshmallow, Pydantic, Attrs, ItsDangerous, Werkzeug, Pytest).
- **Scope & Boundaries:** These are designed as isolated unit-level regression reproductions for controlled ablation of test-failure diagnosis. They are **NOT** full-repository SWE-bench issue checkouts.
- **Experimental Status:** Evaluated across 4 variants and 2 random seeds (120 calls) by `run_e2e_inference.py`.

### B. Unexecuted Upstream Archive: 5 Authentic Repository Defects
- **Directory:** `paper/e2e_gemma_experiment/real_repo_sample/` (5 instances)
- **Provenance Statement:** Curated sample of 5 authentic upstream issues from public repositories (`pallets/flask` and `psf/requests`), with pinned git commit SHAs, genuine upstream problem statements, gold PR patches, and test patches.
- **Experimental Status:** **ARCHIVED / NOT EXECUTED BY RUNNER**. They serve as an open-source reference benchmark resource for future full-repo studies and have not been scored by the Gemma 4 runner.

## 2. Experimental Conditions (Four Variants)

For each of the 15 tasks, four controlled prompt variants are generated:

1. **Variant A (`A_raw`):** Full, uncompressed raw pytest failure traceback.
2. **Variant B (`B_compressed`):** AST-guided deterministic compressor output (retaining failing test boundaries, call sites, and exception summaries; safely falling back to 0% truncation when no separable test boundary exists).
3. **Variant C (`C_tail35`):** Naive tail truncation heuristic (last 35 lines of log).
4. **Variant D (`D_no_trace`):** Black-box control baseline containing issue statement and source code, with zero traceback log.

### Presentation Order:
A balanced Latin-Square rotation ($A \to B \to C \to D$, with 1-position shift per task) is applied to cancel sequence and fatigue bias.

## 3. Two-Tier Diagnostic Evaluation Rubric

### Tier 1 (Primary): Objective Pre-Registered Rubric
- **Objective Localization (`objective_localization_pass`):**
  Requires the model's explicit `DEFECT_LOCATION:` string to match the pre-registered canonical target symbol for the task (e.g., `Blueprint.__init__`, `Config.from_file`, `Session.resolve_redirects`).
- **Objective Root Cause (`objective_root_cause_pass`):**
  Requires the model's `ROOT_CAUSE:` text to satisfy all pre-registered required concept sets (e.g., must mention both "dot/period" and "endpoint collision") AND contain zero forbidden hallucinated misdiagnoses (e.g., blaming unrelated syntax or circular imports).
- **Combined Diagnostic Pass (`objective_diagnostic_pass`):**
  `objective_localization_pass AND objective_root_cause_pass`.

### Tier 2 (Auxiliary / Proxy): Lexical Heuristic
- **Lexical Localization (`heuristic_lexical_localization_pass`):**
  Checks whether any 3+ character component of the target symbol appears as a substring in the localized text.
- **Lexical Root Cause (`heuristic_lexical_root_cause_pass`):**
  Checks whether the expected exception is mentioned OR at least 25% of words from the reference root cause string match.
- **Role:** Explicitly labeled as an auxiliary proxy metric to detect lexical gaming.

## 4. Execution Mode: `collect_only` (Safe Default)

- During GPU execution, `collect_only = True` is strictly enforced by default.
- The runner collects model text, token counts, latency, finish reasons, and evaluates Tier 1 and Tier 2 text diagnostics.
- Model-generated candidate code is **NOT** executed on the host or GPU instance.
- Pre-flight syntax validation uses Python's built-in `compile()` function, which statically verifies syntax without executing candidate code.

## 5. Statistical Framework and Completeness Integrity

- **Sample Size:** Exactly 15 tasks x 4 variants x 2 seeds = 120 unique observations.
- **Integrity Validation:**
  The statistical module verifies that all 120 cells exist with zero duplicates and zero missing cells.
  If any cell is missing or duplicated, analysis aborts with an explicit error. **Silent substitution of zeros for missing variants is prohibited.**
- **Clustered Paired Bootstrap:**
  - Resampling unit: Task ID (seeds are averaged within each task).
  - Iterations: 10,000 bootstrap resamples.
  - Metrics computed: $\Delta(B - A)$, $\Delta(B - C)$, $\Delta(B - D)$ with 95% percentile bootstrap confidence intervals.
  - Permutation test: Two-tailed paired sign-flipping test (10,000 permutations) for exact p-values under $H_0: \Delta = 0$.
- **Truncation Tracking:**
  Responses with `finish_reason == "length"` are explicitly logged and flagged.
