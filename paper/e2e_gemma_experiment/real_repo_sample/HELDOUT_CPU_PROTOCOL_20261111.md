# Prospective held-out CPU protocol — November 11, 2026

**Experiment ID:** PAPER-HELDOUT-THREE-REPOS-20261111-01

**Decision frozen before target-test execution and before seeing outcomes on these issues.** This is a *local prospective protocol*, not externally timestamped independent preregistration.

## Hypothesis and claim boundary

The existing, completely frozen `paper/traceback_compressor.py` B2 compressor preserves the exact multiplicity of selected `E`, `> `, pytest `FAILED` / `ERROR`, exception-summary lines and pytest underscored failure-header lines while reducing the combined byte length of failing pytest logs relative to raw input on **new upstream repositories not used in the eight-issue development sample**.

Primary success requires 3/3 eligible authentic failing logs with 100% selected marker retention, and **positive** total byte savings. Secondary exploratory comparisons vs `head35`, `tail35`, `tail20`, naive marker-only, and B1. Report each case including failed/excluded cases. No inference or model solve-rate claim.

## Frozen task selection (SWE-bench Lite public test split)

Picked only using public metadata (repository, task ID, declared test name, test patch size), **not based on observed failing logs or compressor outcomes**:

1. `pylint-dev__pylint-5859`: source `pylint-dev/pylint`; declared F2P `tests/checkers/unittest_misc.py::TestFixme::test_non_alphanumeric_codetag`.
2. `pydata__xarray-4094`: source `pydata/xarray`; declared F2P `xarray/tests/test_dataset.py::TestDataset::test_to_stacked_array_to_unstacked_dataset`.
3. `sympy__sympy-11897`: source `sympy/sympy`; declared F2P `test_latex_Piecewise` (resolve only to one explicit test path from public test patch).

**Eligibility** per issue: at exact public `base_commit`, apply public `test_patch` and execute the declared test(s) in a local isolated environment (RED, test fails *for a task-related assertion/error* rather than import/collection/harness failure); then apply public `patch` (gold) for *validation only* and rerun the same exact test(s) (GREEN). Record exit codes, environment, Python and installed package versions, test paths. Gold code and expected outcomes MUST NOT be passed to the compressor and MUST NOT be used to choose a replacement case.

**No replacements** if an issue is ineligible, dependency setup fails, or a test does not produce RED/GREEN. Mark the case `EXCLUDED_ENV` or `EXCLUDED_INVALID_RED_GREEN`, keep it in the denominator for feasibility, and describe why. Do not silently omit an inconvenient case. Do not run a GPU model to synthesize errors.

## Frozen methods, metrics and acceptance

- Code: the exact already-published `paper/traceback_compressor.py` from repository `main` as fetched on Nov 11 before executing selected tests; pin its SHA256 in the report.
- Primary metric: selected diagnostic integrity, using the existing exact-multiplicity line-matching function from `compare_baselines_5repos_20261111.py`. This is weaker than full semantic preservation, and explicitly excludes other potentially useful context.
- Primary cost metric: UTF-8 *byte savings* on three RED logs; not model input tokens. Report full corpus sum and per-issue ratios, count of fallbacks.
- Baselines: raw, head 35, tail 35, tail 20, naive diagnostic-only, original v1, B2.
- **Accept:** all 3 tasks eligible and B2 holds selected integrity 3/3 with positive cumulative byte savings; this is added independent-repository evidence only. **Partial:** one or more excluded or B2 fails, report with limitations. **Reject model-gain claim** regardless of outcome since no Gemma inference is performed.
- Prevent partial result selection: report *all three named instances*, all six scored arm outputs and complete source log hashes, red/green statuses, repo commits and exclusion reasons.

## Limits and budget

CPU-only existing VPS, no paid resources, maximum 60 minutes aggregate worker walltime, cap installs to low-cost ordinary Python dependencies and no unrelated infrastructure changes; 1-2 concurrent tasks maximum, no competition submissions, no modification to live Kaggle writeup or model notebooks. Everything must be auditable via GitHub and logged in MMW. This is a scientific-support experiment, not a direct head-to-head with Taiko Toeda, Jared or Maroof, whose evaluation targets are different.
