# Gemma Paper — P0 final editorial corrections (2026-11-10)

**Scope:** evidence QA and proposed edits only. Published Kaggle Writeup ID 115692 remains untouched. Deadline 2026-11-12 23:59 UTC.

## Confirmed inputs

- `paper/writeup.md` in GitHub: **2,959 whitespace-separated words** (not an authoritative Kaggle Markdown/rendered/figure-caption word count).
- Official Kaggle MCP `get_hackathon_write_up` returned truncated response (49,429 original characters), **so current full live Writeup cannot be compared or word-count-certified** from this response.
- The five genuine pinned issues in `real_repo_sample/manifest.json` are **Flask (3) and Requests (2) only**. They have actual CPU-only RED/GREEN controls, 155 P2P tests, and 12/12 evaluator controls; they do **not** include fresh Gemma model inference.
- The 120 original Gemma4 inferences and 30 B2 exploratory inferences are **on 15 synthetic reproduction tasks**, not authentic upstream issues.
- `A_raw` and `C_tail35` achieved 30/30 synthetic patch tests each; post-hoc `B2_assertion_aware` 29/30; initial `B_compressed` 25/30. B2 reduced **total API tokens**, not exclusively prompt tokens, 39.05% vs A. No proven noninferiority.
- All five real-task A/B2/C frozen prompts passed a zero exact copied-gold-code check; **not a semantic leakage certificate**.

## Highest-priority proposed replacement (replace the current inaccurate subsection 5.6, do not append without trimming)

**Suggested replacement:**

> **5.6 External-Task Feasibility (CPU-only, no model inference).** Five archived authentic upstream issues—three Flask, two Requests—were independently checked at pinned commits. Their frozen test patches reproduced the original failures (5/5 RED); corresponding historical gold fixes resolved them (5/5 GREEN), with 155 selected offline regression tests passing before and after. An isolated deterministic patch evaluator passed 12/12 gold/base/syntax/regression controls; 39/39 security/scoring CPU tests passed. This verifies benchmark feasibility and execution integrity, **not Gemma's fix rate on these upstream issues**. [CPU evidence](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/CPU_REAL5_FINAL_ACCEPTANCE_20261110.md).

This replacement is ~95 words; adjust final Kaggle 3,000-word count against the actual published text *before* publication.

## Second correction: exploratory B2 claim

Replace `proving that assertion-aware compression preserves test signals without forfeiting token efficiency` with:

> `suggesting a promising task-specific trade-off in this post-hoc synthetic evaluation, without establishing noninferiority to raw tracebacks or generalization to authentic SWE issues`.

## Third correction: make all claims proportionate

- In the abstract/summary, distinguish **original 120 pre-specified calls** from **30 additional post-hoc B2 calls** and note synthetic-case scope.
- Do not describe B2 as equal to A; its synthetic patch test rate was lower, 29/30 versus 30/30 (underpowered comparison).
- Do not phrase 31.5% reduction in measured total API tokens as purely a deterministic character compressor improvement; actual output length and decoding vary.
- Don't claim five real upstream tasks as a new independent blind Gemma validation.
- `paper/writeup.md` links point to top-level repo and Kaggle Notebook, while reproducibility artifacts are listed as relative code paths. Consider a **direct link** to CPU acceptance, original JSONL and B2 JSONL. Ensure visible hyperlinks on Kaggle; markdown links in GitHub are not proof of Kaggle accessibility.

## Remaining separate acceptance gates before updating Kaggle

1. Get full current live Writeup body and verify the **actual judged word count** (3,000 including captions/tables under contest rules).
2. Ensure science/novelty/related work differentiates AST+compile primitives (not novel) from assertion-aware preservation + execution integrity gate (integration contribution).
3. Verify direct resource links work publicly and an independent user can run CPU unit controls without credentials.
4. Get owner's explicit go-ahead **before any Kaggle Writeup edit, submission or unsubmission**. Do not rewrite Kaggle on mere technical recommendation.
5. Without GPU approval, no A/B2/C Gemma inference on five authentic issues.

**Recommended action:** prepare an exact minimal diff against the *live* Kaggle Writeup, not just the GitHub surrogate, and obtain owner approval. The competition deadline is less than three days away as of this audit.
