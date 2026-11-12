# G0-SEARCH-005 — preregistered 9-dev-issue file search comparison

Date: 2026-11-12. **Experimental type:** model-free issue-localization diagnostic. No LLM/GPU/Kaggle submit.

**Goal:** compare the exact commands advised by frozen **original v15 prompt** versus the exact **one-bullet EXP-AGENT-001A** prompt under the **same manually frozen issue-derived tokens** for all 9 dev issues from Flask, Requests and pytest. This is not agent inference or patch solve rate.

Queries fixed in [G0_SEARCH_005_FROZEN_QUERY_PLAN.json](G0_SEARCH_005_FROZEN_QUERY_PLAN.json), committed **before** scoring or accessing gold target filenames. All tokens must occur in each task's `problem_statement`; any disallowed/invalid token fails closed. The source task manifest SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf` is fixed and **only dev split** entries will be used. Manual tokens were chosen from the issue text and may not match what Gemma E4B would choose. Do not promote these results to blinded heldout evaluation.

**Nine frozen cases:** Flask4045/4992, Requests1963/2148/2317, pytest11143/11148/5103/5221. Each historical Git commit tree must exist in pre-existing local bare cache or isolated previously fetched checkout. Use `git archive <exact pin>` and rebuild in its own scratch directory, verify `HEAD^{tree}` equals historical `<pin>^{tree}` before running commands, using `git add --force --all` to preserve tracked-but-ignored files. Never use current HEAD or a gold/test-patched source. Gold diff is used **only after** both command outputs are recorded.

**Baseline v15:** `git grep -n "SPECIFIC_TOKEN" -- *.py | head -20`, case-sensitive, as in exact Kaggle-submitted v15 prompt. Escape shell tokens and substitute the frozen issue token.

**Candidate EXP-AGENT-001A:**
- If plan defines a named class/module/file token: `git ls-files '*.py' | grep -i -F "MODULE_OR_FILE_TOKEN" | grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10`.
- Else: `git grep -n -i -F "SPECIFIC_TOKEN" -- '*.py' ':!tests/**' ':!**/tests/**' ':!**/test_*.py' ':!docs/**' ':!**/docs/**' ':!examples/**' ':!**/examples/**' | head -20`.
Candidate and baseline exact prompt texts must be SHA-recorded; the three other v15 submission files remain bitwise identical in 001A.

**Evaluator:** extract gold source patch `diff --git a/PATH b/PATH` target paths *after* searches, normalize `a/` or `b/` and use them **only offline**. Compare top-1/top-5 **unique displayed source file paths** from each command to at least one gold source file; report pairwise wins/ties/losses, total misses, response line counts, runtime and exact stdout. If the gold patch changes multiple files, report both any-source-hit and all-source-hit. Never feed gold paths into queries. No model or oracle tests.

**Pilot gate:** consider the search change promising only with **>=2 net cases improving hit@5** over v15 and <=1 regressing, across the nine dev issues. This threshold does **not** approve paid GPU or Kaggle sends; actual E4B solve-rate on paired tasks and independent heldout is still needed. If gate fails, keep the candidate HOLD/REWORK and protect E4B v15.

Resource cap: existing VPS CPU <=1 core per subprocess, <=10 seconds/query (typically <0.1), no paid services. No production service changes, no hidden-task leakage, no Kaggle quota.

## Recorded pre-retry correction — archive staged inside scratch Git tree

Initial Stage A was **ABORTED before issuing any search commands** because the experiment's source `historical_source.tar` was accidentally saved **inside the Git checkout** and `git add --force --all` included that artifact. Git tree SHA verification correctly rejected this: actual historical Flask4045 had 235 tracked files; scratch checkout had 236, the only extra file being `historical_source.tar`. No result was counted.

Correct the harness (not the query plan, tokens, commands, targets or score rule) by writing the archival input **outside** each working checkout, then reconstructing tracked source in sibling `source/` directory before `git init` and strict tree SHA. **Use a new output directory and raw report path; do not delete or overwrite aborted evidence.** Full initial mismatch remains logged on VPS. Do not run Stage B scoring until all nine source trees and actual Stage A searches complete.
