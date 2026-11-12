# Gemma 4 Developer Agent — STATUS

Updated: 2026-11-10 UTC. Scope: Agent/Main Track and E4B Small Model Bonus only. Paper Track is managed separately.

## Official Kaggle baseline (read-only MCP verification, 2026-11-10)
Competition: https://www.kaggle.com/competitions/gemma-4-developer-agent
Deadline: 2026-12-02 23:59 UTC. Entry deadline: 2026-11-25 23:59 UTC. Max daily submissions: 1. Teams: 5225, current team rank: 2079 (at read time).

| Version | Submission | Model/track | Public score | Kaggle status |
| --- | ---: | --- | ---: | --- |
| v11 | 57911135 | 31B/main | **0.17** | COMPLETE |
| v14 | 58014403 | 31B/main | **0.17** | COMPLETE |
| v15 | 58073369 | E4B/small bonus | **0.06** | COMPLETE |
| v16 | 58126337 | E4B/small bonus | **0.05** | COMPLETE |

Sources: official Kaggle MCP get_competition, search_competition_submissions, and get_competition_submission for each ID. The 0.17 31B score is NOT a small-model-eligible score. Final prize outcomes depend on private evaluation, not public score.

## Regression diagnosis / evidence
- v14→v15 changed model to E4B; do not attribute the 0.17→0.06 drop to code quality alone. Need controlled comparison with identical model and baseline.
- v15→v16 changed more than one variable: temp .20→.15, thinking 4096→2048, max_output 8192→4096, calls 32→36, prompt/edit workflow revised. 0.06→0.05 observed; causal root cause **NOT ESTABLISHED**. Kaggle MCP list_submission_episodes for both returns empty objects, not task traces.
- Archived v15/v16 unpacked code is in forensics per Issue #7; exact submitted immutable ZIPs and matching hashes still need independent verification.
- Existing locator-only benchmark raw file: paper/small_model_benchmark/LOCATOR_BENCHMARK_RESULTS.json, N=42 of 50 manifest tasks across 6 of 9 repos; Recall@1 20/42 = 47.6%, @3 25/42 = 59.5%, @5 27/42 = 64.3%, MRR .5459, mean 11.587s. Eight tasks from sklearn/matplotlib/xarray not run. dev/heldout share repositories. These are localization metrics only: ZERO measured E4B F2P/P2P solve-rate improvement.
- v17_small_model_candidate prompt invokes tools/ast_bm25_locator.py; **integration unproven**: issue text/query not supplied and tool path may not exist in /workspace. No v17 Kaggle submission authorized. GitHub Issue #7 contains audit details and blockers: https://github.com/msingatullin/gemma-4-developer-agent/issues/7

## Work plan and acceptance gates
**G0 — CPU only, $0 cloud budget, target <= 2 hours operator time:** Freeze exact v11/v14 and v15/v16 submission artifacts with SHA256 and normalized diffs; capture model/tool configs. In a clean local equivalent of Kaggle harness, run 2-3 smoke issues, prove issue text flows to locator, script is reachable from sandbox, no gold labels enter agent, only permitted files change, and package passes static validation. Archive commands/stdout/stderr/hashes. PASS only if complete, deterministic and reproducible; otherwise STOP v17.

**G1 — CPU only, $0 cloud budget, target <= 4 hours:** Freeze 50 allowed real SWE issues with repo base commits, dev 25/heldout 25, fixtures and separate F2P/P2P. Correct the 42/50 coverage issue or explicitly report missing 8. Validate evaluator RED on base, GREEN on known-good patch, P2P regression detection, nonempty diff, syntax and safe patch application. Gold is permitted only for offline oracle, not prompt. PASS if all eligible fixtures have valid test oracles, coverage/exclusions documented; otherwise fix dataset.

**EXP-AGENT-001 — isolated E4B locator-only test, not authorized to run paid GPU:** Freeze exact v15 E4B, sampling and prompt; only change deterministic locator integration. Start with paired 6-8 dev issues, then 25 dev and 25 untouched heldout issues, same per-task time/tool budgets and seeds. Collect per-task raw model trajectories, applied patch, F2P/P2P, solved, time, tokens, tool errors and category. Preserve v15 and rollback. Only count paired solved outcomes, not locator Recall alone. Acceptance: smoke compatibility; zero invalid/unsafe patches; on 25 dev >=2 additional net resolved cases and no material timeout regression; on heldout net-positive solved cases with zero new severe failures; provide uncertainty / paired win-loss and repetition where feasible. Thresholds are **decision gates**, not statistical proof or guaranteed Kaggle uplift.

**EXP-AGENT-002 (conditional):** If 001 passes, test simplified prompt/tools as a separate single-variable A/B. Do not combine changes or submit by default.

**Budget and authorizations:** CPU local/VPS only until owner approves; proposed initial paid E4B GPU pilot hard spending cap **$2 total**, subject to explicit owner approval, verified billing/watchdog/termination and resource availability. No pod launch, no Kaggle submission, no final selection change from this status update. Reassess spend only after G0/G1.

## Next decision
Recover exact v15/v16 submitted ZIP SHA and verify v17 clean-harness invocation. Then request approval for the bounded paired E4B GPU pilot *only if* CPU gates pass. Freeze v11/v14 (main) and v15 (E4B) as non-overwritable baselines. Continue Paper Track separately.

## Autonomous operations (2026-11-10)
- Scheduled daily agent cycle in Asia/Singapore, 10:00, for read-only Kaggle verification, next free evidence-gated work, MMW/GitHub status upkeep, meaningful-change alerts and Monday summary. Paper Track keeps its separate hourly sprint; do not duplicate it.
- G0 read-only fresh check: live v17 prompt currently calls `python3 /tmp/ast_locator.py --query "SPECIFIC_IDENTIFIERS_FROM_ISSUE"` (not the older tools/ast_bm25_locator.py invocation documented above). Therefore implementation **changed since last audit**: must trace provenance/installation of /tmp/ast_locator.py and ensure the correct issue-derived query is actually passed before any claim of working integration. This was static source inspection only, not a sandbox smoke test. No paid compute or Kaggle submission.

## 2026-11-11 G0 evidence audit — HOLD (EXP-AGENT-001)
- Kaggle MCP rechecked: no new submissions since v16 (2026-11-08), best main v11/v14 0.17, E4B v15 0.06; current rank 2127/5340, deadline unchanged. No submission performed.
- Critical: `paper/small_model_benchmark/PAIRED_E4B_PILOT_RESULTS.json` reports simulated 6-task 1/6→4/6 and 15→5 tool calls, but `run_paired_e4b_eval.py` explicitly uses `simulate_v15_agent`/`simulate_v17_agent`, scripted `apply_model_edit` branches on `instance_id`, and `target_file` ground truth to choose candidate edit even if locator ranking fails. This is **not real E4B inference**, not an unbiased end-to-end paired comparison, and cannot justify paid pilot or Kaggle score uplift. Results must be labelled **synthetic scripted simulation** everywhere they are cited; do not promote 4/6 as agent solved rate.
- `verify_in_sandbox_locator.py` copies locator into a separately created local temporary directory before running. It verifies a simulated environment only; actual Kaggle executor provisioning of `/tmp/ast_locator.py` remains unverified. In current v17 prompt, locator path is `/tmp/ast_locator.py`; the script must be staged by a real harness before invocation. The candidate prompt's issue-derived query is a template instruction, not proven actual model behavior.
- Decision: **G0 HOLD / EXP-AGENT-001 NOT STARTED**. Next: inspect actual Kaggle harness artifact for pre-session locator provisioning, then perform a clean isolated CPU smoke and preserve raw logs; recover exact submitted ZIPs. No GPU, API spend, or Kaggle submit.

## 2026-11-12 G0 read-only server artifact discovery — HOLD
- Official Kaggle MCP checked 2026-11-12: still no submissions after v16 2026-11-08; v11/v14=0.17 (31B), v15 E4B=0.06, v16 E4B=0.05. Rank 2177 / 5461 teams, one submission/day, deadline unchanged. These ranks change with entrant count and are not solve-rate improvements.
- Gateway SSH read-only command executed successfully on registered CPU VPS `nuremberf` (job `job_01M76QXGWM00RQZ48Z97B9JPKJ`, exit 0). Historical local path `/home/mikhail/gemma-4-developer-agent/submission_v16_staged.zip` is **absent on this server**; `/tmp/ast_locator.py` is also absent **on this server at audit time**. `/opt/kaggle` exists but bounded name search maxdepth 3 found no Gemma Agent artifacts. This does NOT establish Kaggle executor absence; do not conflate VPS and Kaggle runtime.
- G0 blocker: exact submitted ZIP bytes and SHA remain unrecovered, and Kaggle harness provisioning of locator remains unverified. Next: locate submitted ZIP via authorized Kaggle download endpoint or actual staging host, compare SHA to reported staged artifact, then isolated clean CPU smoke. No modifications to VPS, GPU use or Kaggle submission.

## 2026-11-12 critical report correction — EXP-AGENT-001 remains NOT STARTED
- Independently re-read `paper/small_model_benchmark/run_paired_e4b_eval.py`: `simulate_v15_agent`/`simulate_v17_agent` never call E4B inference; `apply_model_edit` hardcodes per-instance patches and receives gold `target_file`; `verify_patch_in_clean_container` sets `p2p_pass=True` without P2P tests. Thus claimed 1/6 vs 4/6, tool calls 15 vs 5 are synthetic counters, not measured agent outcomes. Original report additionally claims 6/6 contrary to its own table.
- Corrected/replaced `paper/small_model_benchmark/PAIRED_E4B_PILOT_REPORT.md` with explicit retraction, unchanged historic JSON as audit trail, three gated repair stages G0/G1/real E4B paired A/B. GitHub commit `c8c15dfe031e2fd0beee6d341245f049b2108d10`.
- No actual v17 solve-rate uplift proven; no Kaggle submission or spend. Next: recover ZIP bytes and verify real Kaggle locator provisioning. Do not accept new results unless raw model trajectories and independent F2P/P2P logs exist.
