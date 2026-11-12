# EXP-AGENT-001A — results: exact-v15 single-variable locator preflight

Date: 2026-11-12. Competition deadline: 2026-12-02 23:59 UTC.  
**Decision: ACCEPT CPU package/build gate; HOLD agent quality claims and all submissions.**

## Scope / hypothesis

Compare only a v15 prompt's first search instruction: the original unfiltered `git grep` versus a filename-aware source-first search excluding test, documentation and example matches by default. The hypothesis is that less irrelevant output helps a small E4B model identify relevant implementation files more reliably. **No E4B calls were performed. No F2P/P2P success claim.**

Important empirical correction: the previous assumption that `git grep ... -- *.py` only searches top-level files was **false**. Executing that exact command on real Flask source returned nested `src/flask/` files. The observed problem is that early output can include examples/tests, consuming limited result slots.

## Frozen baseline / candidate

| Object | Verified SHA256 |
|---|---|
| Actual Kaggle v15 owner submission, ID 58073369 | `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a` |
| Unsubmitted, private EXP-AGENT-001A ZIP | `5a93228a86397ae247e3b3395ae82cc31d4f724f23a083ca18a0926dfc79cde0` |

- Builder: [`scripts/agent_exp001a_build.py`](../../scripts/agent_exp001a_build.py); verifies original immutable Kaggle ZIP hash, four exact file contents and an exact unique prompt anchor.
- Baseline has 2 directory entries (`configs/`, `prompts/`) as well as four files. First strict build failed because it did not expect directories; parser fixed to permit ONLY those directory entries, without permitting extra files.
- Candidate replaces exactly **one bullet** of `prompts/system.md`. `agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml` remain **byte-identical** to the actual v15 submission.
- Validated extracted candidate with repository `tools/validate_submission.py`: **PASS**. Second private clean build gave the **identical ZIP and manifest SHA256**. Raw ZIPs stored privately on VPS `nuremberf:/opt/kaggle/gemma-agent-g0-20261112-audit/`; no Kaggle submission.
- [Exact member hashes and source manifest](exp_agent001a_package_manifest.json). ZIP is *not* committed publicly.

## Real CPU subprocess diagnostic (not SWE solve rate)

Source repository: public Flask **HEAD `49943b5a94413a530761350f04e896f76e8d620e`**, which is *not* the historical SWE task base commit. Two manually selected issue terms; oracle paths used **only offline for ranking**, not passed to model or shell. Same CPU VPS, same repository commit, source tree clean.

| Query | Offline relevant source file | Original v15 first-20 line rank | Filename-first first-10 rank |
|---|---|---:|---:|
| `Blueprint` | `src/flask/blueprints.py` | 10 | **1** |
| `Config` | `src/flask/config.py` | 2 | **1** |

Timings (seconds): Blueprint original 0.0063, candidate 0.0050; Config original 0.0057, candidate 0.0059. These are *not comparable to LLM wall time* and cannot establish a speedup. Repository `git status --porcelain` remained empty. [Raw per-case CPU record](exp001a_cpu_search_diagnostic.json).

**Limitations:** only two selected terms in one current repo, no independent heldout, baseline has code snippets whereas candidate first gets filenames (different output information), and no model trajectory. These diagnostic ranks **must not be reported as agent resolved tasks or Kaggle score uplift**.

## Gates and next action

- G0 original v15/v16 archive recovery: **PASS**.
- G0 isolated CPU package and fallback smoke: **PASS** for limited tested conditions.
- G0 native `swegemma`/ADK harness: **HOLD** — neither `swegemma` nor `adk_submission` nor `adk_eval_core` was installed in checked VPS Python environments. A local script/static validator does not reproduce the official contest executor.
- G1 true SWE RED→GREEN and F2P/P2P with frozen task revisions: **NOT RUN** in this phase.
- EXP-AGENT-001A genuine paired E4B inference: **NOT RUN** (requires explicit GPU budget approval).

Next priority: freeze a real-task oracle evaluator, verify RED on base, GREEN on gold patch and P2P regression handling **before** model outputs are visible. Then conduct real paired v15 E4B vs prompt-only candidate using the same model/settings/time budget; require independently scored patched-task outcomes on unseen issues before deciding on a paid GPU pilot or Kaggle submission.

Costs: **$0 new GPU/API/RunPod, 0 Kaggle submissions**. Existing CPU VPS used.
