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


## 2026-11-11 verified evidence supersedes the earlier CPU-only/no-inference gate

**Do not reuse the historical proposed Section 5.6 verbatim.** The statements above that no real-upstream Gemma inference was performed, and that GPU permission is missing, describe the earlier 2026-11-10 state and are now superseded. The published Kaggle Writeup remains unchanged pending explicit owner approval.

- Private free Kaggle T4x2 notebook v10 completed, with 15/15 SHA-verified genuine Gemma4 31B model responses (five pinned upstream tasks × A_raw/B2_assertion_aware/C_tail35). Corpus SHA256: `7b9bddd1a410821db3bc4b509241fea8d18988340747d3a630706e19ef829ef2`. Raw responses stay private on VPS.
- Isolated offline CPU evaluation against pinned local Docker images and upstream repositories completed with 15/15 verdicts and **zero harness errors**. An initial path-misconfigured run produced 15 HARNESS_ERROR verdicts and was excluded, not treated as model failures. Verified final score JSONL SHA256: `0dd65aea3355aaae5d16c7eb821aeb5ac2bf2bcfa00df8f4f97f383fd487930a`; summary SHA256: `af32d8e330db0688067bf1e5fe0d10f0f6985494c424918397890882f39a9ab0`.
- Actual task resolution: **A_raw 1/5, B2_assertion_aware 1/5, C_tail35 1/5**; all three solved the same `psf__requests-1963` task, and the other four were unresolved. No observed resolution gain, no demonstrated noninferiority or generalizable performance improvement. Total prompt+completion tokens: A 41,013, B2 37,009, C 40,036; descriptive, not a proof of token savings at equal accuracy.
- Validated historical CPU controls remain 39/39 unit, 12/12 evaluator controls, 5/5 gold RED/GREEN, 155 selected P2P. Exact copied-gold literal scan of 15 prompts does not establish semantic non-leakage.
- **Proposed new manuscript wording, subject to live-text diff, word budget, and owner authorization:** “On five pinned authentic upstream issues (three Flask, two Requests), we additionally collected 15 genuine Gemma 4 31B responses under three frozen prompt variants using a private free Kaggle GPU notebook. An isolated, pinned CPU evaluator found one resolved task out of five for each variant, the same Requests issue in all three. This small exploratory sample does not show improved resolution or establish equivalence of compressed and raw prompts. All outputs were checked against frozen prompt hashes; the raw model responses are not publicly released.”
- Official Kaggle MCP `get_competition` checked 2026-11-11: ID 163111, deadline **2026-11-12 23:59 UTC**, 847 teams at check, user entered, USD 35,000 prize pool. Live Writeup 115692 could not be fetched by `get_hackathon_write_up` in this run (`Not found`); do not claim live-vs-draft equality or certified 3,000-word compliance.

**Release gate:** no published Kaggle Writeup edit or contest submission without explicit owner approval. Avoid publishing private model responses. The strongest final narrative is an honest negative/neutral real-upstream pilot plus reproducible deterministic infrastructure, not an unproven improvement claim.
