# PAPER-HEAD2HEAD-MAROOF-20261111-001 — Frozen peer prediction replay protocol

**Study registered 2026-11-11 after prior public competitor report reviewed but BEFORE producing any per-task or aggregate outcomes for the reserved 90 cases.** This protocol is prospective for our derived file-selection reranker, but not an external hidden contest benchmark, and it uses released predictions from an existing competitor's public experiment. No new Gemma model calls.

## Question / shared model+metric

Can an inexpensive deterministic **post-inference verification/reranking** step select a more accurate source file from the **same Gemma 4 E4B (4-bit) output** as Muhammad Maroof's published `repomap_sig` baseline on held-out real SWE-bench Lite tasks?

Primary metric: **File@1 correct** when the first selected path belongs to the frozen SWE-bench Lite gold changed-files list. Source model/prompt model outputs must stay unchanged. **No additional model call** and **no extra Gemma input or output tokens** allowed in the primary condition. The postprocessor may reorder only `repomap_sig`'s existing `pred_files` list, never hallucinate or retrieve a new file; preserve that method's tokens and latency reporting separately (CPU postproc latency added). Claim only a direct improvement vs `repomap_sig` if measured. If a second-arm ensemble is investigated, preregister separately and account for 2× inference cost; do not mix with primary.

Source: cloned public peer GitHub `maroofiums/astgraph-gemma` commit `b28c4b9790be7ae20ac584385a0cc122d4b5b58b`; immutable archived file `results/run_v3.jsonl`, full SHA256 `d91325d689e3e492e5a3ba1e9689a4779ae92b6895fa765eed96a5e2f0c35ca2`. Secondary source is public SWE-bench Lite `test.parquet` SHA256 `7a21f37b8bc179c7db5beeb14e88ac538ba283455c776e6b2535bbfb6e3551b4`.

## Split (exact and mechanical)

1. All **150** issue IDs with a released `repomap_sig` row form the evaluation universe.
2. **60 DEVELOPMENT IDs** are exactly those also having a peer-published `ours_2stage` row (the competitor's extra ablation subset). Gold labels for these 60 can be inspected/tuned.
3. The remaining **90 HOLDOUT IDs** are the exact set difference. Code generating candidate features must **strip/never expose** `gold_files`, `file_acc1`, `file_acc3`, `file_acc5`, `gold_funcs` and other gold/score fields for all 90 to development/selection code, and must not open original heldout rows after generating features. Store hash of sorted issue IDs and all frozen inputs.
4. The 60 cases overlap the 150 already present in original article, so this split is an **additional analysis, not the independent fresh 150**. No cross-evaluation as 150 new heldout issues; only 90 genuinely reserved for this postprocessor development. The competitor's own methods may have been developed/evaluated on these rows; no stronger claim.
5. Do not tune or choose algorithms after peeking at the holdout 90 outcomes. Record each development candidate and cross-validation scores. Freeze one final algorithm and SHA256 source before exactly **one holdout outcome evaluation**.

## Proposed features and algorithm family

Deterministic issue-text/path aware reranking within original `repomap_sig`'s top-three predicted files, based on the issue statement from SWE-bench Lite (available to all agents) and candidate path/symbol name; avoid referencing gold patches or gold tests. Features may include basename/path/exact mention, lexical token overlap, method rank penalty, and predicted symbol. Choose a small fixed set of transparent non-LLM variants using only 60 development outcomes, ideally leave-one-repo-out CV. Final scorer must be executable on CPU with standard Python and no model weights. Sourced `repomap_sig` candidate predictions are not modified.

## Predeclared acceptance / reporting

- Primary gain metric: heldout `90` exact file@1 **positive increase** vs unmodified `repomap_sig`. A tie is scientifically null; a loss is REJECT. For a **strong** claim require at least **+5 absolute correct tasks**, zero additional model calls, and paired McNemar exact two-sided p <= 0.05; additionally disclose confidence intervals and all discordant cases.
- **Integrity gate:** candidate selected path must already occur in source candidate list; cannot use gold or issue/test patches; no additional model inference; number of tasks exactly 90. Negative results must be reported and retained.
- Statistical limitations: unregistered multiple dev variants, limited n=90, competition's public SWE-bench Lite source differs from hidden leaderboard; clustering by repository can invalidate task-level naive confidence assumptions. Treat significance exploratory unless stronger robust checks.
- Resource budget: CPU only, 0 paid, <=2 CPU hours, no Kaggle competition submission, no live Paper Track writeup edit without evidence review. Save code, manifest, results in GitHub and MMW; if heldout win credible, user must sync final writeup before deadline 2026-11-12 23:59 UTC.

**Acceptance: PENDING** (no holdout outcomes inspected at freeze).
