# Gemma 4 E4B head-to-head: zero-inference reranking of Maroof's released file candidates

**Experiment:** PAPER-HEAD2HEAD-MAROOF-20261111-001 (2026-11-11). [Protocol frozen before labels](PROTOCOL_MAROOF_20261111.md) at `ed66a5652e560440fa569088430ba1495909c290`. [Transparent reranker](reorder_gemma_candidates.py), [60-case dev grid and selection](select_dev_only.py), [frozen selected config](FROZEN_FINAL_MODEL.json), [input hashes/split](manifest.json), [one-shot scorer](score_holdout_once.py), [90 task outcomes](HOLDOUT90_RESULTS.json), [uncertainty](UNCERTAINTY_HOLDOUT90.json).

## Directly comparable question

The source study [Maroof, AST-Compressed Code Graphs](https://github.com/maroofiums/astgraph-gemma) provides **actual previously generated E4B model outputs**, including the method `repomap_sig`'s ordered top-three source files, for 150 SWE-bench Lite issues. We tested whether an extra **deterministic, zero-inference postprocessor** could select a better first file among the *same published candidate list*, given the public issue description. This **does not** require an additional Gemma call or additional Gemma input tokens. It is not a fresh Gemma inference experiment.

We partitioned the original 150 cases mechanically: 60 with a released `ours_2stage` ablation row formed development; the remaining **90** formed reserved evaluation. The 90 were not used for parameter selection. The source `results/run_v3.jsonl` hash was `d91325d689e3e492e5a3ba1e9689a4779ae92b6895fa765eed96a5e2f0c35ca2`. Fixed reranker source and config were published in GitHub *before* one-shot 90-case evaluation. In this experiment, split selection was mechanical, **not random**.

## Outcome

| Condition | Development (60) | Reserved test (90) |
|---|---:|---:|
| E4B `repomap_sig` File@1 | 30/60 (50.00%) | 49/90 (54.44%) |
| Same output + deterministic file reranker | 33/60 (55.00%) | **51/90 (56.67%)** |
| Absolute difference | +3 tasks (+5.00 pp) | **+2 tasks (+2.22 pp)** |

Heldout per-task discordance: **4 rescued, 2 regressed**, 11 first-file selections changed. **All four recovered cases were SymPy; regressions were one Astropy and one Django case.** The chosen algorithm was tuned on 60 development tasks across 256 transparent heuristic variants; this is a small and partially clustered development sample. 

Exact paired two-sided McNemar `p=0.6875`. Paired-task bootstrap 95% CI in percentage points **[−3.33, +7.78]**; repository-cluster bootstrap **[−6.25, +11.34]**. The preregistered **strong-win gate (≥5 additional correct files and p≤0.05) was NOT met**. This is a positive **numerical** result only; no statistically supported general superiority is established.

## Verification

A second, independent clean-directory replay re-fetched the **publicly committed reranker/config/results** and reconstructed the exact unlabeled reserved-90 issue inputs from the peer's original JSONL and frozen SWE-bench Lite dataset. SHA256 of unlabeled test input matched the preregistered manifest. It reran the original frozen code and reproduced **all 90 per-task verdicts byte-for-byte**, including 49→51, four rescues and two losses.

Reproduction requires the released competitor's repo `results/run_v3.jsonl` at commit `b28c4b9790be7ae20ac584385a0cc122d4b5b58b`, SWE-bench Lite `test.parquet`, Python with `pyarrow` to reconstruct issue descriptions, and the scripts in this folder. The original score script expects the local competitor checkout path from our VPS; point that path at your own checkout when replaying.

**Scientific boundaries:** Only file localization **File@1** is evaluated, not patch correctness, agent solve rate or Kaggle hidden leaderboard. We do not add new inference, but inherit possible selection/design bias from a publicly reported, potentially tuned competitor benchmark. The original 60 development cases overlap the source author's 150-test cases. Positive results are concentrated in one repository and not robustly significant. We make **no claim of overall superiority over Maroof's paper** or of Paper Track prize rank.
