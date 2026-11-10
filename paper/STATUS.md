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

## Competitor intelligence — 2026-11-10 (read-only update)

Scope: public Kaggle notebooks and public sources, not a full verified ranking of submitted Paper Track Writeups. Kaggle competition notebook search returns public notebooks but cannot certify each notebook has an eligible final Writeup. Team count 752 as of previous official read; not number of valid prize candidates.

| Rival | Public evidence | Relative threat / remaining uncertainty |
| --- | --- | --- |
| Taiko Toeda, Scaffolding Helps the Smallest Gemma 4 Agent | Zenodo https://zenodo.org/records/23834104: 3 model capacities x 2 scaffolds x 5 seeds x 104 public tasks, published preregistration; E4B claimed 10.0% to 15.4% resolved | Very high for Best Paper, not independently rerun |
| xxsyrbest (Boyang Wang), Code Graph Localization | https://www.kaggle.com/code/xxsyrbest/gemma-4-code-graph-localization-reproducibility ; extensive prior verified artifacts and large reported runs | Very high novelty/verifiability risk, model inference not independently re-executed |
| maroofiums (Muhammad Maroof), AST-Compressed Code Graphs | https://www.kaggle.com/code/maroofiums/ast-compressed-code-graphs-for-gemma-4-agents ; reported 150 SWE-bench Lite test, 60 dev, statistical analysis | Very high; direct overlap on AST/code graph, inference not independently rerun |
| jaredga (Jared Anderson), Name the Method at Its Code | https://www.kaggle.com/code/jaredga/name-the-method-at-its-code-code-and-data ; 63 embedded files and recomputation | High threat to Best New Resource |
| fabrianivan, Three Paradoxes & CA HGR | https://www.kaggle.com/code/fabrianivan/gemma-4-swe-agents-three-paradoxes-ca-hgr ; reports 1627 trajectories/294 tasks | High conditional, full underlying runs unverified |
| pablodiegoo, L4 Decode Law & 12-Call Cliff | https://www.kaggle.com/code/pablodiegoo/gemma-4-paper-l4-decode-law-12-call-cliff ; reported 692 paired trajectories | High potential Quality threat; fresh inference not independently replayed |
| Kevon Gaines, PhaseGuard-AST / Nullspace LoRA Surgeon | https://www.kaggle.com/code/kevongaines/phaseguard-ast-and-nullspace-lora-surgeon-repro ; currently public Kaggle notebook verified | Emerging, full outcomes still need independent review |
| mobassir, Why Your Leaderboard Can't See a 3-Point Gain | https://www.kaggle.com/code/mobassir/why-your-leaderboard-can-t-see-a-3-point-gain ; current public notebook v8, discusses heldout and winner's curse | Emerging; methodological competition, not established Paper judging entry |
| Mattbusel, SWE-Graph Lite | https://github.com/Mattbusel/swegraph-lite ; claims 300 SWE-bench Lite tasks released as code graphs | Potential strong Best New Resource rival; Kaggle submission unverified |

Additional known contenders include Mark Whiteley (192 recorded episodes claimed), Akash Nair (16 constructed diagnostic cases), Pablo's competing hardware analysis, Roland Poulin E4B paper and recent GemmaGraph-Agent. These are monitored, not independently judged.

**Competitive gap:** our 150 calls cover only 15 synthetic tasks and B2 is post-hoc. A_raw and C_tail35 had 30/30 patch tests while B2 had 29/30; cannot claim proven raw-equivalent quality. Our strongest defensible advantage is a small, readily auditable assertion-aware diagnostic preservation tool with raw data, fixed prompts and sandbox evaluation. Immediate best zero-cost improvement: concise manuscript coherence and evidence links; CPU-only heldout validation if safely runnable. DO NOT claim rivals are eligible submissions or compute a fake winning probability.

**Next checkpoint:** verify direct Writeup links for top contenders if Kaggle exposes them; prioritize Toeda, xxsyrbest, maroofiums and Jared; monitor new notebooks such as Kevon and Mobassir. No spending or Kaggle submission changes authorized.

## CPU-only harness hardening checkpoint — 2026-11-10

Authorization: owner approved free harness development and audit; **NO GPU**, no paid compute and no Kaggle submission/publication changes.

### Implemented and verified by GitHub read-back
- Commit 4efbde57b2ab3cac0e6203c5f42219fd8dab2505 modified `paper/e2e_gemma_experiment/evaluate_real_repo_patches.py`: added `validate_candidate_diff_paths()` requiring a single allowlisted target source file for unified diffs, rejecting traversal, absolute paths, changed test targets, deletion/rename/copy/binary patches and missing hunks; `patch` now runs noninteractively with `--fuzz=0`; evaluator run_id restricted to safe ASCII path component.
- Commit ac746aded5429e5d43a5321a4952ed8ed95d5108 created `paper/e2e_gemma_experiment/test_patch_path_guard.py` with 10 CPU-only unit tests; extracts the guard via AST without importing Docker/dependencies.
- GitHub fetch_file read-back confirmed both exact source files, diff guard and 10 tests are present. **Tests were NOT run against a checked-out repository in this environment**; do not record PASS from source inspection.

### Outstanding blockers / next execution
1. Run `python -m unittest discover -s paper/e2e_gemma_experiment -p 'test_patch_path_guard.py' -v` from a clean clone and log 10/10 actual results. Stop if any fail.
2. Audit `run_in_docker`: current volume mounts include host `/home/mikhail/.local` (read-only), and copied virtualenv; isolation and compatibility must be confirmed before executing ANY model-generated code. Better use purpose-built, pinned, credential-free sandbox and read-only input mounts.
3. Run evaluator gold/base/malformed/regression controls in appropriate isolated CPU-only environment, for all five real upstream tasks, and independently verify F2P vs P2P disjointness and actual test counts.
4. No Gemma inference, GPU, Kaggle writeup modification or prize claim until all gates pass and relevant operations separately authorized.

Current decision: **HOLD on real model patch execution**, CPU static path-hardening changes only. Previous successful historical CPU RED/GREEN artifacts are not a fresh rerun.
