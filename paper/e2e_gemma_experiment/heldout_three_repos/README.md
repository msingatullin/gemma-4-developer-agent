# Prospective three-repository diagnostic-compression audit — 2026-11-11

**Experiment:** PAPER-HELDOUT-THREE-REPOS-20261111-01; locally frozen [protocol](../real_repo_sample/HELDOUT_CPU_PROTOCOL_20261111.md) in GitHub commit `2a946218c18b3bada1568689896b4bfabed1e470` **before** any selected target test was executed. No tasks were substituted.

## External eligibility gate

Each of the three genuine SWE-bench Lite public test tasks was checked out at the public base commit, patched with its released test patch, and executed RED (exit 1, actual task assertion); after applying the public gold patch **solely to verify environment eligibility**, exactly the same test executed GREEN (exit 0). The algorithm does not read gold patches. All three were run with Python 3.9.25 / pytest 6.2.5 in a pinned isolated CPU Docker image (digest `sha256:80e945d7246b7d943fbbe20dbd5f3c010ed9e43c5ad85313164a2d84a1f0edb5`), network disabled during the scored test. Installed dependencies: pylint with astroid 2.9.3; xarray with NumPy 1.23.5 and pandas 1.5.3; legacy SymPy with mpmath 1.2.1.

| Task | Repo | RED | GREEN | B2 retained all *selected* markers | B2 log byte reduction |
|:--|:--|--:|--:|--:|--:|
| `pylint-dev__pylint-5859` | pylint | 1 | 0 | Yes | 61.92% |
| `pydata__xarray-4094` | xarray | 1 | 0 | Yes | **0.00% (safe raw fallback)** |
| `sympy__sympy-11897` | SymPy | 1 | 0 | Yes | 66.59% |

**Frozen headline:** B2 **3/3** selected diagnostic/header/summary marker retention, total **38.72%** corpus-byte reduction. On the same three RED logs, `head35` **0/3** (63.25% reduction), `tail35` **0/3** (64.75% reduction), `tail20` **0/3** (76.94%). B2 does **not** dominate truncation on bytes in this three-case split; it preserves markers whereas truncation loses them. For xarray, B2 deliberately falls back to unchanged raw log.

## Public replay

- [Authentic RED and GREEN test logs, per-log SHA256, task metadata](REAL_LOG_FIXTURES_HELDOUT_20261111.json)
- [Frozen-method comparison script](compare_baselines_heldout_20261111.py)
- [21 per-method results and aggregates](baseline_comparison_heldout_results_20261111.json)

The unchanged compressor source is [paper/traceback_compressor.py](../../traceback_compressor.py), SHA256 `a9e192fef9a0d53de60ea18c90e21167253f2e1445f6c17f70ad6354da1351d5`. Relative-path adaptation and metadata strings in the test harness do not alter any comparison algorithm. In a normal checkout of this repository run:

```bash
python3 paper/e2e_gemma_experiment/heldout_three_repos/compare_baselines_heldout_20261111.py
```

The benchmark uses Python standard library only; no model calls or original repository installation are needed to replay metrics from the shipped genuine logs. A fresh public-GitHub download into a clean VPS directory independently reproduced **all 21 per-case result rows and aggregates exactly**.

## Scientific scope

Exact-multiplicity verification covers selected pytest E-lines, failing-site markers, FAILED/ERROR summaries, exception diagnostic lines and underscored failure headers. It **does not** guarantee complete semantic equivalence, token-count reduction, improved Gemma patch solve rate or a superiority ranking against papers by Toeda, Jared Anderson, Maroof or others. Three new repositories are a useful prospective external sanity check, but still an extremely small, nonrandom sample of software failures.

**Decision:** Accept as supplementary heldout generalization evidence for the open source verification resource. Do not alter the submitted Kaggle paper or advertise a model performance gain without separate validation.

## Exploratory budget-matched stress test (not part of the frozen protocol)

In a separate post-hoc check we capped simple head/tail truncation at **each individual log's actual B2 output byte count**, testing prefix/suffix shares 0%, 25%, 50%, 75%, and 100%. We even allowed an optimistic *per-task oracle* to choose the best of these five variants after seeing the diagnostic evidence. That oracle preserved all selected markers on **3/11 logs** (1/8 development + 2/3 prospective), whereas B2 retained **11/11** by construction of the same selected-marker oracle. Whole lines are retained, so truncation may underutilize its allotted byte budget slightly. The prospective split includes xarray where B2 and a trivial full-log baseline both use the original length.

This is evidence against several *specified naive truncation strategies at approximately matched byte budgets*, not a theorem about all possible truncation methods, the general distribution of errors, end-to-end model quality, or statistical superiority over other research papers. The analysis family and oracle comparison were devised **after** observing the fixed split outcomes.

[Exploratory head/tail comparison code](byte_matched_truncation_exploratory.py) and [11 per-task results](byte_matched_truncation_exploratory_result.json). A clean public-source replay regenerated all 11 rows identically.
