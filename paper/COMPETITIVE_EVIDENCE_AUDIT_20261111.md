# Competitive evidence audit — Gemma 4 Paper Track (2026-11-11)

**Question:** Can the AST-Guided Verification Suite be shown to outperform the strongest competing Paper Track research? **Not yet overall.** The strongest released papers measure different targets. We can already show **a narrower, reproducible win** over direct diagnostic-compression baselines and a new but exploratory improvement in real patch resolution. Do not turn these into a global paper ranking.

## What was actually independently inspected

| Paper/resource | Published research target | Verified source/evidence | Directly comparable to our primary outcome? |
|---|---|---|---|
| Muhammad Maroof, [AST-Compressed Code Graphs](https://github.com/maroofiums/astgraph-gemma) | Gemma 4 **E4B** file/function localization on 150 SWE-bench Lite test tasks; reported repo-map signature **File@1 = 52.7%** vs own graph method 48.7%, plus ablation | Independently cloned public code at commit `b28c4b9790be7ae20ac584385a0cc122d4b5b58b`; benchmark protocol and complete `results/run_v3.jsonl` available. No inference was rerun in this audit. | **No** — file localization, not test-log evidence preservation or F2P/P2P issue resolution |
| Jared Anderson, [Name the Method at Its Code](https://www.kaggle.com/code/jaredga/name-the-method-at-its-code-code-and-data) | Gemma 4 **12B** code reading, 160 SWE-bench Lite tasks; strict Hit@3 39.4% to 47.5% with class-to-method block splitting, and 25 class-only cases 4% to 64% | Downloaded actual Kaggle notebook, unpacked archived 63-file release (XZ archive SHA256 `bf5bde32a5e40c07485c46093714b2fe888eaaebbb8489b22bb8392f92c59f8e`); all 62 files independently matched supplied SHA256 manifest. Archived numbers inspected, model not rerun. | **No** — code-reading Hit@3, not pytest diagnostics or final patch success |
| Boyang Wang, [Code-Graph Localization Reproducibility](https://www.kaggle.com/code/xxsyrbest/gemma-4-code-graph-localization-reproducibility) | Code-graph vs text/random retrieval under fixed budgets on fresh SWE tasks | Independently downloaded public Kaggle notebook and inspected published design/caveats; original authors report graph advantage failed to reproduce consistently. | **No** — retrieval-context ranking |
| Our [AST-Guided Verification Suite](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4) | Test-time deterministic diagnostic preservation, AST verification, patch application, and model-assisted upstream issue resolution | 31/31 public Kaggle CPU oracles in Notebook v20; eight external failing pytest logs across five repositories re-replayed; strict immutable Docker CPU patch checks | Comparable to **naive truncation/compression baselines**, not to the three different research endpoints above |

## Matched same-task comparison: test-log preservation

Frozen 8 genuine failing pytest logs from five upstream repositories (Flask ×3, Requests ×2, pytest, Sphinx, seaborn). Every arm receives the same byte-for-byte input. Outcome: **all selected E/failing-site/FAILED-ERROR/exception/failure-header/summary line multiplicities preserved**, and percent of corpus bytes removed. This is neither a complete semantic equivalence measure nor SWE solve rate.

| Method | Logs passing full selected diagnostic check | Corpus byte reduction |
|---|---:|---:|
| Raw log | 8/8 | 0.00% |
| Head 35 lines | 2/8 | 43.31% |
| Tail 35 lines | 2/8 | 40.12% |
| Tail 20 lines | 1/8 | 63.45% |
| Naive diagnostic lines only | 0/8 | 84.19% |
| **Our deterministic v1** | **8/8** | **50.86%** |
| **Our B2 assertion-aware** | **8/8** | **59.93%** |

**Scoped superiority:** B2 strictly Pareto-dominates both head35 and tail35 on *this dataset* (better retention **and** higher byte reduction). Against tail20, B2 preserves more diagnostic information but reduces slightly fewer bytes, so neither dominates in both metrics. Exact paired McNemar two-sided unadjusted p = 0.03125 for B2 vs head35 and tail35, p = 0.015625 vs tail20; comparisons are exploratory, n=8, repository-clustered, and there is no multiple-comparison-adjusted claim of general population-level superiority. No comparison here establishes that our research is overall stronger than Jared, Maroof or Wang.

**Reproduction:** [8-case source logs](e2e_gemma_experiment/real_repo_sample/REAL_LOG_FIXTURES_5REPOS_20261111.json), [standard-library comparison program](e2e_gemma_experiment/real_repo_sample/compare_baselines_5repos_20261111.py), [full per-case results](e2e_gemma_experiment/real_repo_sample/baseline_comparison_5repos_results_20261111.json). Fresh public-code replay produced identical aggregates.

## Matched same-task comparison: authentic Gemma issue resolution

Five original authentic upstream issues from Flask (3) and Requests (2), Gemma 4 31B QAT. **True first pass** from 15 frozen model responses: A_raw **1/5**, B2 **1/5**, C_tail35 **1/5**; all solve the same Requests1963 case. These results are in the published writeup.

Further **post-hoc** correction and feedback experiments on the **same five issues**, **not a held-out result**:

- A_raw + earlier class-aware and import/namespace repair: **3/5**.
- B2 + earlier static namespace recovery: **2/5**.
- B2 + a *new authentic second model inference* on three still-unsolved Flask cases, the same unique-hunk diff rebaser and strict F2P/P2P Docker: **one new success** (`pallets__flask-4992`), so *combined*, explicitly exploratory **3/5** across original five.
- C_tail35 + earlier static namespace recovery: **2/5**.

The new feedback generation came from a **private free Kaggle 2×T4 notebook** `msingatullin/gemma4-paper-b2-feedback-short-v2-free-t4`: exactly **three responses**, each `finish_reason=stop`, 5,903 combined API tokens; the original diffs each failed strict application (0/3). A new fail-closed source-anchored adapter was applied to immutable upstream source. After rebase, Flask4992 **RESOLVED (F2P + P2P PASS)**, Flask4045 and Flask5063 **FAILED_F2P**. Independent clean-directory fetch of the public rebase code, replay with private original outputs, and immutable Docker confirmed **1/3**.

**New reproducibility:** [parser with no gold input](e2e_gemma_experiment/recovery/strict_diff_rebase.py) and [sanitized row-level evidence](e2e_gemma_experiment/recovery/strict_rebase_sanitized_public.json). All three model outputs stay private. The parser may omit a cosmetic documentation-only hunk when it cannot be uniquely anchored, recorded explicitly; the successful Flask4992 semantic code changes were applied intact. The static adapter was tuned and tested on these same tasks. Do not claim these results demonstrate a quality lift *caused by B2 compression* versus A, or independent generalization.

## What must be done before claiming to beat a strong competing scientific paper

1. **Same prediction target.** For Maroof: file/function localization; for Jared: method Hit@3. Our current log-retention and F2P/P2P endpoints are **not exchangeable** with either.
2. **Same cases, frozen selection.** Reuse the competitor's public SWE-bench Lite task ids and frozen gold mapping on an untouched test partition. Any new retrieval layer built for comparison must be frozen before test data inspection.
3. **Same inference conditions.** Match the Gemma variant (E4B for Maroof, 12B for Jared), budget, decoding, quantization and judge; compare per-task paired outcomes. Report full reproduction scripts, exact model hashes and task split.
4. **Baseline and uncertainty.** Show at least one material improvement in a matched metric with paired confidence intervals/multiple-testing control; demonstrate no unacceptable regression in solve rate and resource cost.
5. **Only then use a stronger claim.** Overall judges consider five criteria and different scientific contributions. Even winning a matched metric does not mathematically establish ranking #1 among all articles.

**Decision on 2026-11-11:** ACCEPT scoped diagnostic compression superiority and the new verified Flask4992 feedback-repair finding. REJECT any present assertion that we outrank every strong competing study. This is the defensible evidence boundary for Best New Resource; no contest submission was changed.
