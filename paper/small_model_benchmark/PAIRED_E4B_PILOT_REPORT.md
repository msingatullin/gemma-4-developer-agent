# EXP-AGENT-001 — forensic correction: scripted CPU simulation, NOT Gemma E4B evaluation

**Status:** INVALID AS SOLVE-RATE EVIDENCE / G0 HOLD  
**Corrected:** 2026-11-12  
**Original experiment:** 2026-11-09  
**Competition:** https://www.kaggle.com/competitions/gemma-4-developer-agent  
**Source:** `paper/small_model_benchmark/run_paired_e4b_eval.py`  
**Unmodified historical data:** `paper/small_model_benchmark/PAIRED_E4B_PILOT_RESULTS.json`

## Executive correction

The old report labeled a scripted six-case simulation as an empirical Gemma E4B A/B test. **Neither actual v15 nor v17 Gemma E4B inference ran in this script.** Therefore the original reported 1/6 vs 4/6, 15 vs 5 calls, +50 percentage points and purported task wins are **not actual agent solve-rate, model tool-call usage, or Kaggle projections**. The old conclusion additionally claimed 4/6 -> 6/6 without supporting data; this claim is withdrawn. Preserve the old raw JSON for provenance, but do not put these values on any model-performance dashboard.

Source inspection shows:
1. `simulate_v15_agent` and `simulate_v17_agent` are Python routines modeling imagined agent steps, not invoking Gemma inference.
2. `apply_model_edit(workdir, instance_id, target_file)` contains task-specific prewritten edits for six known issue IDs.
3. `target_file` is sourced from task ground truth and passed to the editor in the v17 path even when predicted location is wrong. This is oracle leakage, invalidating an end-to-end localization claim.
4. The verifier initializes `p2p_pass = True`, without actually running an independent P2P regression suite. Several task checks are simple source-string assertions rather than genuine task-level tests.
5. Call counts are program counters, not model-observed tool calls. Temporary placement of a locator script in a simulated test does not prove Kaggle harness provisioning.

## What remains supported

A distinct raw 42-case deterministic locator-only benchmark (`LOCATOR_BENCHMARK_RESULTS.json`) reports file-level Recall@1 = 20/42 (47.6%), Recall@3 = 25/42 (59.5%), Recall@5 = 27/42 (64.3%) across six repositories. That is a file-search diagnostic, **not resolved SWE-bench tasks**. Eight of the manifest's 50 issues were not evaluated. `v17_small_model_candidate/prompts/system.md` calls `/tmp/ast_locator.py`; real Kaggle sandbox delivery and full issue-text transfer remain unverified.

Official Kaggle MCP baseline: 31B/Main v11 submission 57911135 and v14 58014403 each Public 0.17; E4B/small v15 submission 58073369 Public 0.06; E4B/small v16 58126337 Public 0.05. The 31B scores are not E4B prize baselines.

## Mandatory repair gates — in order

**G0 (free CPU):** Recover the exact submitted v15/v16 ZIPs and SHA256 hashes; inspect normalised code/config diffs. In a clean, isolated sandbox run the actual v17 package, verify the allowed harness stages `/tmp/ast_locator.py` and passes a real issue-derived `--query`. Validate exits, stdout, file-scope changes, no gold/target_file in model inputs. Preserve commands and raw logs. **Fail closed** if file/query cannot be supplied.

**G1 (free CPU):** Pin 25 development + 25 separate heldout real issues, valid repository revisions, environment, issue text, test patch and independent F2P/P2P oracles. Freeze scoring first. Verify RED on base, GREEN with known-good oracle outside agent reach, and regression detection. Exclude or disclose unsupported cases.

**EXP-AGENT-001 (requires separate paid-GPU approval):** Perform genuine E4B inference twice on matched issues using exactly the archived v15 configuration and a single-variable locator-only candidate. Record actual model requests, responses, tool invocations, timestamps, generated patches, F2P and independent P2P results per issue, failures and uncertainty. Keep ground-truth targets and gold patches out of all agent-visible inputs. Start with 6–8 development issues, then widen to heldout if warranted. Do not infer improved solve rate from a synthetic script. Do not submit candidate to Kaggle until explicitly approved.

**Acceptance:** Reproducible actual inference, no target leakage, safe patch application, meaningful per-task RED/F2P/P2P, measured paired net resolved improvement (not just locator recall), acceptable runtime/budget, preserved best baseline, and full artifacts.

**Decision:** Reject original simulation as evidence; retain it for audit only. G0 HOLD, v17 NOT APPROVED for Kaggle submission or paid pilot.
