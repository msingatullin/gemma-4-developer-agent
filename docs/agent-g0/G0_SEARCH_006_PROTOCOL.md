# G0-SEARCH-006 — dev-only search behavior ablation

Date: 2026-11-12. **Preregistered before new subprocesses or offline scoring.** Exploratory ablation on **same 9 dev issues** already used in G0-SEARCH-005; not independent heldout, not E4B solve rate.

**Purpose:** isolate which components of the one-bullet EXP-AGENT-001A search rewrite drive the G0-005 1/9→4/9 hit@5 finding. The current v15 Bash command uses an **unquoted** `*.py` which expands to root Python filenames in 8 of 9 test trees. Avoid falsely crediting the filename-first feature alone for any gains.

Frozen inputs: 9 query tokens and filename tokens in [G0-SEARCH-005 query plan](G0_SEARCH_005_FROZEN_QUERY_PLAN.json), expected plan SHA256 `a0673b12d821907ba4391f7684a5eafd962c73ef5b4dc091eb443b78c4f06226`; immutable G0-005 stage-A raw SHA256 `58b050b73a64c18cdd741b8c947bc19ec20a48975588ad1a001572870b69d69a`. Pinned source-only local worktrees were Git-tree verified and contain no gold/test patch. Frozen 50-task manifest SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`. Do not touch heldout cases.

Run the following exact variations with **identical content tokens and per-task sources**:

- `v15_original`: `git grep -n "TOKEN" -- *.py | head -20` (unquoted shell expansion, case-sensitive).
- `quote_only`: `git grep -n "TOKEN" -- '*.py' | head -20` (one logical change, Bash expansion disabled).
- `quote_casefold`: `git grep -n -i -F "TOKEN" -- '*.py' | head -20` (add case-insensitive literal match).
- `quote_casefold_filtered`: same as above plus the precise `':!tests/**'`, `':!**/tests/**'`, `':!**/test_*.py'`, `':!docs/**'`, `':!**/docs/**'`, `':!examples/**'`, `':!**/examples/**'` exclusions.
- `exp001a_current`: the original EXP-AGENT-001A conditional filename-first when a filename token was frozen in G0-005, otherwise exactly `quote_casefold_filtered`.

Before scoring, verify the rerun `v15_original` and `exp001a_current` stdout exactly matches the prior Stage-A raw outputs, with identical per-case historical Git tree SHA and a clean worktree after all searches. Stage A must record all command lines, stdout, timings and unique returned paths *without reading gold patch paths*.

After raw evidence has been written and its SHA recorded, start a separate scorer process that reads gold source filenames from frozen dev manifest only for **top-1 and top-5 unique returned path hit rates**. Report per-stage totals, pairwise gains/losses relative to original v15, and whether `quote_only` captures most candidate improvements with less prompt complexity. No p-values or task-resolution claims from these nine selected issues. Do not use Stage B gold filenames to modify any queries or score thresholds in the same run.

Decision guideline: favor the simplest expression whose model-free `hit@5` is not materially worse than EXP-AGENT-001A (difference <=1/9), but do not auto-promote to competition entry. Further true model-generated patch comparisons must be independently approved. Resource cap: existing CPU VPS, 10 seconds/command, $0 paid GPU/API/RunPod/Kaggle sends.
