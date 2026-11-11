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

## Independent competitor-result replays (additional verification, 2026-11-11)

1. **Maroof, real Gemma4 E4B SWE-bench Lite dataset.** Independently parsed all **1,860 released per-task prediction rows** from public source `results/run_v3.jsonl` (SHA256 `d91325d689e3e492e5a3ba1e9689a4779ae92b6895fa765eed96a5e2f0c35ca2`). On the exact same **150** task IDs per arm: `repomap_sig` File@1 **79/150 = 0.52667**, `ours` graph method **73/150 = 0.48667**, `snippet_rag` **57/150 = 0.38000**, `bm25_files` **40/150 = 0.26667**. Reported mean prompt tokens ~2595 for repo-map, ~2592 for graph method. This independently verifies the archived aggregate arithmetic, **not** new E4B inference or our superiority over it.
2. **Jared, reproducibility itself.** Extracted and SHA-verified the released 63-file companion; ran actual third-party `combined_table.py` in a **locked-down offline Docker container** (immutable local sha256 image; `--network none`, `--read-only`, `--cap-drop ALL`, unprivileged user, 1 GB RAM and one CPU). Output: **"checks against the saved run aggregates: 26 of 26 equal"** and **"table equals combined_table_FROZEN.md"**, exit 0. Thus Jared's published table is genuinely reproducible from released rows, rather than an unverified competitor claim. His reported strict class-only Hit@3 gain on 25 cases is much stronger within *his own code-reading endpoint* than our five-case patch-resolution pilot can establish.
   
**Conclusion of peer replay:** The strongest competitors have real evidence; it would be dishonest to label them weak or inferior on their own endpoints. Our existing matched advantage is specifically *diagnostic preserving log compaction* over the listed truncation baselines, not superiority over these peer papers.

## Taiko Toeda: Zenodo archive independently reproduced (2026-11-11)

- **Exact public version:** [Zenodo record 23834104](https://zenodo.org/records/23834104), published October 31, 2026, version 1.0.5. It's the **research data/code supplement** for the competing Paper Track manuscript *Scaffolding Helps the Smallest Gemma 4 Agent, Not the Larger Ones*, not a separate Kaggle competition, and not a peer-reviewed journal acceptance. [GitHub tagged code/data](https://github.com/mobius-style/gemma4-scaffold-capacity/tree/v1.0.5) points to the matching archived release.
- Independently cloned GitHub tag `v1.0.5` to VPS clean competitor-audit directory; checkout commit **`7356b06b0f5c8b5cc185a03b8ac2b4b68d210425`**. Archive holds `4,056` JSONL task-run outcomes (exact count independently enumerated), split **1,560 min + 1,560 max + 936 exploratory mid**; across 104 public competition tasks, 3 Gemma4 capacities E4B/12B/26B-A4B, 5 seeds per registered cell.
- Actually executed **`python3 scripts/reproduce.py`** on the tagged archive using only CPU/Python standard library: all frozen confirmatory outputs matched with **`MISMATCHES: none` and `REPRODUCE: PASS`**, exit 0. Recomputed archived task-run rates:
  - E4B simple `0.1000`, maximal scaffold `0.153846`; observed difference `+0.053846`, paired task bootstrap 95% CI `[+0.02308,+0.08846]`.
  - 12B simple `0.251923`, maximal `0.230769`; difference `-0.02115`.
  - 26B-A4B simple `0.276923`, maximal `0.267308`; difference `-0.00962`.
- **Scientific nuance:** their preregistered directional hypothesis predicted a positive scaffold effect for 12B/26B, not E4B. The frozen hypothesis test script prints `p_holm=1.0` for these preregistered directional tests. The positive E4B CI is a **real observed effect in a direction opposite the registered hypothesis** and cannot be advertised as confirmation of their originally registered hypothesis. Pre-registration timing is self-attested local git history, not independent external timestamp proof. CPU reproduction **verifies arithmetic and internally reported results from provided JSONL**, not the original live 4,056 GPU/agent actions, competition official grader implementation, or raw patch outputs (not published).
- **Competitive significance:** This is a substantively stronger *multi-model, multi-seed, authentic-task* empirical design for agent issue-resolution than our first-pass 5 authentic Flask/Requests issues. It is not on the same endpoints/model/tasks as our narrow eight-log diagnostic compression study, so scientific **global superiority has not been demonstrated either way**. Correct next head-to-head is a common frozen tasks, same Gemma capacity, same grader, shared budget study with a diagnostic-integrity intervention tested on the agent scaffolds, if allowed by remaining time and free compute.

## Prospective external-repository generalization — new check on November 11

**Protocol was frozen before outcomes** at [HELDOUT_CPU_PROTOCOL_20261111.md](e2e_gemma_experiment/real_repo_sample/HELDOUT_CPU_PROTOCOL_20261111.md), commit `2a946218c18b3bada1568689896b4bfabed1e470`. It names exactly three SWE-bench Lite cases from **three previously unseen upstream repositories** (pylint, xarray, SymPy). Each was independently validated RED on its public base commit + test patch (exit 1 due genuine assertion/error), then GREEN after its own gold patch (exit 0); scorer uses only the RED log, not gold code. Frozen compressor `paper/traceback_compressor.py` SHA256 `a9e192fef9a0d53de60ea18c90e21167253f2e1445f6c17f70ad6354da1351d5` was **not changed**. Python 3.9.25 and pytest 6.2.5 ran in a pinned offline immutable Docker image.

| *New prospectively fixed task* | B2 retains selected markers | B2 bytes saved | head35/tail35 retain all selected markers |
|---|---|---:|---|
| `pylint-dev__pylint-5859` | Yes | 61.92% | No / No |
| `pydata__xarray-4094` | Yes (raw safe fallback) | **0.00%** | No / No |
| `sympy__sympy-11897` | Yes | 66.59% | No / No |
| **Frozen split aggregate** | **3/3** | **38.72%** corpus bytes | **0/3 / 0/3** |

Artifacts: [unmodified local-study protocol](e2e_gemma_experiment/real_repo_sample/HELDOUT_CPU_PROTOCOL_20261111.md), [raw six red/green pytest logs and SHA256](e2e_gemma_experiment/heldout_three_repos/REAL_LOG_FIXTURES_HELDOUT_20261111.json) commit `64fedbb1dd9076b424b7454692cce41e334557e8`, [comparison program](e2e_gemma_experiment/heldout_three_repos/compare_baselines_heldout_20261111.py) commit `53ccea6a72466d975391f6bd6a120cc725c68646`, [full 21-row result](e2e_gemma_experiment/heldout_three_repos/baseline_comparison_heldout_results_20261111.json) commit `2537c3b4acc8f960591df7efde8b7439ca4ef8eb`. All 21 per-method per-task metrics reproduced exactly by a fresh checkout from **public GitHub** with only Python stdlib. The original eight development logs were not altered.

**Post-hoc descriptive pooling** of 8 development + 3 prospectively selected external logs (11 cases, 8 repositories): B2 **11/11 selected-marker retention with 51.37% bytes removed (18,215/37,459 bytes retained)**, head35 **2/11 with 51.35% bytes removed (18,222/37,459 retained)**, tail35 **2/11 and 50.05% bytes removed**. Thus at an *almost identical corpus-total output size* B2 preserves substantially more marked failures. This is not per-case budget matching and is not itself a prospective pooled confirmatory test. [Pure-stdlib calculator](e2e_gemma_experiment/aggregate_diagnostic_11.py) and [published JSON](e2e_gemma_experiment/diagnostic_11case_combined_descriptive_20261111.json), independently reproduced from public split reports.

**Separate exploratory per-log byte-budget stress:** five head/tail shares (0%, 25%, 50%, 75%, 100%) were given no more bytes *per input* than B2's output; an optimistic oracle picked the best of these five after knowing each task's markers. This oracle preserved selected markers **3/11** while B2 retained **11/11**. The family/oracle was devised after seeing split results; not pre-registered, no inference claims and no exhaustive claim against all compression algorithms. [Source and per-case output](e2e_gemma_experiment/heldout_three_repos/README.md).

**Competition assessment:** prospective external evidence makes the open-source deterministic diagnostic tool stronger and more generalizable. It does **not** establish superiority over Taiko Toeda's real issue-resolution study, Jared's model reading Hit@3, Maroof's E4B file localization, or a hidden SWE leaderboard. Do not convert the 3/3 marker result into a model solve-rate claim.
