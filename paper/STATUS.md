# Paper Track — STATUS

Audit: 2026-11-10 UTC | ACTIVE / FINAL_REVIEW
Competition: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper
Deadline: 2026-11-12 23:59 UTC
Owner: msingatullin | Team ID: 16981959 | Writeup ID: 115692 | Hackathon WriteUp ID: 86845
Writeup: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/ast-guided-deterministic-gemma4-agent

## Official checkpoint
- Kaggle MCP get_competition: competition ID 163111, user_has_entered=true, 752 teams, $35,000 pool.
- Kaggle MCP list_hackathon_write_ups: team 16981959, writeup 115692, content_state=PUBLISHED, updated 2026-11-08 13:03 UTC. Separately tagged Submitted state not returned by this endpoint.
- Kaggle MCP get_notebook_info: msingatullin/ast-guided-loops-verification-for-gemma-4, current version 16, is_private=false. No new notebook execution in this audit.
- GitHub repository public, PR #3 merged. Root STATUS.md belongs to separate Agent/Main Track; this file covers Paper only.
- GitHub paper/writeup.md has approximately 2,885 whitespace-delimited words; this does not establish the live Kaggle Writeup word count. Rule max 3,000 words.

## Real-model evidence, frozen baseline
| Variant | Calls | Patch test pass | Mean total API tokens/call | Study |
| --- | ---: | ---: | ---: | --- |
| A_raw | 30 | 30/30 | 1,158.3 | Original |
| B_compressed | 30 | 25/30 | 792.8 | Original |
| C_tail35 | 30 | 30/30 | 1,000.7 | Original |
| D_no_trace | 30 | 22/30 | 536.6 | Original |
| B2_assertion_aware | 30 | 29/30 | 706.0 | POST-HOC exploratory |

Original study: 120 calls, 15 synthetic reproductions x 4 variants x 2 seeds. Additional B2: 30 calls after inspecting B failures; total 150 calls. No proven non-inferiority, no SWE-bench solve-rate claim. B2 task_03 remained 1/2. Five upstream issue samples archived but NOT executed.
Evidence: paper/e2e_gemma_experiment/real_run_20261108/REAL_B2_EXPLORATORY_REPORT.md ; paper/e2e_gemma_experiment/EXPERIMENTAL_PROTOCOL_AND_PROVENANCE.md ; paper/e2e_gemma_experiment/frozen_prompts/ ; paper/traceback_compressor.py

## Critical risks
- P0: Official published Kaggle Writeup describes 120-call original B study while GitHub README and report also describe exploratory B2 (150 calls). Reconcile narrative without rewriting primary measurements or misrepresenting B2 as confirmatory.
- P0: Confirm live word count <=3000, actual judging eligibility/Submitted, and Kaggle Project Links (published alone is not separately confirmed Submitted by inspected endpoint).
- P1: Link live submission to raw JSONL, frozen prompts, docker evaluator and B2 report. Clarify synthetic scope and total API token measurements vs len(text)//4 microbenchmark estimates vs analytical roofline modeling.
- P1: Describe novelty as evaluated deterministic combination, failure-safe diagnostic preservation and assertion-aware design; Python ast/compile and generic traceback filtering are prior techniques. Avoid universal claims.
- P1: Official criteria Novelty, Quality, Relevance, Verifiability, Clarity each 20%. Target Best New Resource ($10k), potentially Overall Best Paper ($15k).
- P1: Peer submissions not verifiably ranked; authenticated Kaggle listing returned only own entry and public web searches did not provide verifiable competitors.

## Final acceptance checklist
- [x] Participation, team-linked published writeup, public notebook v16, public GitHub and merged PR #3 checked.
- [x] Original plus B2 experimental outcome verified from GitHub report.
- [ ] Verify live rendered word count, Project Links, independent judging submission status.
- [ ] Reconcile exploratory B2 in live writeup, strictly owner-approved before changing Kaggle.
- [ ] CPU-only clean-room reproducibility smoke test and artifact integrity review.
- [ ] Recheck peers via trusted official source and freeze final publication before deadline.

Decision: GO for $0 evidence/clarity/documentation checks; NO-GO for speculative paid GPU runs, Kaggle publication edits or submissions without approval.
Next: draft concise, transparent B2 addendum, obtain approval, then verify live publishing status. No Kaggle changes made in this audit.
