# Kaggle discussion 754697 — corrective replacement, 2026-11-11

**Original topic:** https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion/754697

**Publication status:** DRAFT — **NOT POSTED** as of file creation. The existing topic remains unchanged until independently verified through Kaggle.

**Exact replacement title:**

[Correction / Verified Resource] AST-Guided Verification Suite for Gemma 4 SWE Agents — 11 Real Pytest Logs

**Exact replacement markdown body:**

---

**Correction — November 11, 2026**

This updates our November 1 research announcement. Its headline and table claimed a **+116% increase in issue-resolution rate (18.2% → 39.4%)**, **−66.5% context tokens**, and large reductions in syntax errors and regressions. Those claims were **not backed by a reproducible end-to-end comparison**. We withdraw all four claims and apologize for the confusion. They should not be cited as experimental findings.

### What we have actually verified

Our open-source **AST-Guided Verification Suite** provides deterministic code slicing, syntax checks, and pytest diagnostic-preserving compression. The public [Kaggle notebook](https://www.kaggle.com/code/msingatullin/ast-guided-loops-verification-for-gemma-4) passed **31/31 strict deterministic CPU checks**. These checks are **not** Gemma issue-resolution scores.

For the diagnostic compressor, we evaluated **11 genuine failing pytest logs from eight upstream repositories**. B2 retained *all selected* diagnostic, failing-site, failure-header, and summary line markers in **11/11** cases, compared with **2/11** for each fixed head-35 or tail-35-line baseline. B2 reduced **log bytes** by **72.01%** across this pooled corpus. This is **byte reduction, not a measured 72% reduction in model tokens**, and exact selected-marker preservation is not complete semantic equivalence.

Three of the 11 cases (Xarray, Pylint, SymPy) were **frozen in a public protocol before tests were run**. All three were verified against actual upstream RED → GREEN tests; on this separately reported holdout B2 retained selected markers in **3/3** logs, while head-35 and tail-35 retained them in **0/3**. The other eight cases were previously examined and are retrospective, not preregistered.

In a separate **real-Gemma-4 pilot on five authentic upstream issues**, three first-pass prompting variants each solved **1/5**, the **same issue**. We have **not demonstrated** a higher first-pass SWE solve rate caused by this resource. Exploratory same-task patch repairs and subsequent model feedback should **not** be treated as an unbiased held-out solve-rate gain.

### Reproduce and inspect

- [Final Paper Track writeup](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/ast-guided-deterministic-gemma4-agent)
- [Source code and tests](https://github.com/msingatullin/gemma-4-developer-agent)
- [Prospectively frozen three-repository protocol](https://github.com/msingatullin/gemma-4-developer-agent/blob/main/paper/e2e_gemma_experiment/real_repo_sample/UNSEEN_3REPO_PRECOMMIT_20261111.md)
- [Full public logs, comparison script, and results](https://github.com/msingatullin/gemma-4-developer-agent/tree/main/paper/e2e_gemma_experiment/real_repo_sample)

We welcome independent reproduction and corrections. This post is about a **reusable diagnostic-preservation resource**, not a claim of superior hidden-leaderboard performance.

---

**Original preserved:** VPS private backup `/opt/kaggle/gemma-paper-kaggle-cli/forum-754697-correction-20261111/original_kaggle_sdk_20261111.json`, SHA256 `17e591b1265847dffd85387a6fbd635ea74e06ad8daa7eea6f465fa1c4fe1caf`.

**Release gate:** Replace title and body in the same owned Kaggle discussion through the authorized site UI or a supported write-enabled tool, then use read-only official Kaggle MCP `get_forum_topic` to verify that the title no longer advertises `+116%` and the first message explicitly withdraws the old percentages. Merely changing the Paper Track writeup does not correct this forum post. No modification of competition submissions is authorized by this correction.
