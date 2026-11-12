# EXP-AGENT-002 — built and organizer-compiled from authenticated E4B v15

**Date:** 2026-11-12. **Decision:** **ACCEPT CPU package and official compiler gates**; **HOLD any claim of model superiority or competition submission**.

## Frozen source and exactly one code change

- Source: Kaggle owner-submitted E4B v15, submission ID `58073369`, Public Score **0.06**, authenticated source ZIP SHA256 `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a`.
- New unsubmitted private candidate ZIP SHA256 `90601ff0fbcd805e6e4a72b9767a464c5b56c4657d09897a8770ee475777882f`, **2829 bytes**. The smaller ZIP file size than original is an archiver difference, not a deletion: all **four original source-file members** were read back and SHA-confirmed. Original extra directory entries are not needed for package semantics.
- Changed only one single-line substring in `prompts/system.md`:

```diff
- Search once with `git grep -n "SPECIFIC_TOKEN" -- *.py | head -20`. Use the most specific identifier or error string from the issue.
+ Search once with `git grep -n "SPECIFIC_TOKEN" -- '*.py' | head -20`. Use the most specific identifier or error string from the issue.
```

- `agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml` and **all other bytes of `prompts/system.md`** are byte-identical to actual v15; no sampling, token, tool, model or harness changes.
- [Pre-registered protocol](EXP_AGENT002_PROTOCOL.md); deterministic source-hash-gated [builder](../../scripts/agent_exp002_quote_only_build.py); [member-by-member SHA256 manifest](EXP_AGENT002_PACKAGE_MANIFEST.json). Raw original and candidate ZIPs stay privately on existing VPS `nuremberf:/opt/kaggle/gemma-agent-g0-20261112-audit/exp002_quote_only_private_build`; **not uploaded or submitted**.
- Built twice in independent private output folders, and **ZIP + manifest are exactly byte-identical** across repeats. Repository `tools/validate_submission.py`: PASS.

## Genuine organizer ADK compile proof

Used exact official `adk-submission 0.2.13`, `google-adk 1.36.1`, `swegemma 0.2.11` from Kaggle organizer wheelhouse v31 with six **nonexecuting test tool stubs** and identical E4B alias to compile three inputs independently:

| Version | Real ADK `compile_submission` | Agent tools | Prompt chars |
|---|---|---:|---:|
| Owner original v15 | PASS | 6 | 4253 |
| EXP-AGENT-002 (two added quote characters) | **PASS** | 6 | 4255 |
| EXP-AGENT-001A (full search rewrite) | PASS | 6 | 4978 |

[Unmodified organizer compiler actual output](G0_EXP002_OFFICIAL_ADK_COMPILE.json), SHA256 `e0390feff8ad7e3ee25b93e5e045116ed169a855020eeee492e403395f11c64c`. This is structural agent compilation, **not** an E4B model run.

## Why two candidates remain

The G0-SEARCH-006 dev-only CPU ablation on 9 fixed real issues gave:

| Search | Gold file in top 5 unique files | Gold file first |
|---|---:|---:|
| Unquoted original v15 | 1/9 | 1/9 |
| **EXP-AGENT-002 quote-only** | **4/9** | 2/9 |
| Full EXP-AGENT-001A rewrite | **4/9** | **4/9** |

In 8/9 repos the old Bash unquoted `*.py` expanded to Python files in root, preventing nested grep. Quote-only removes that risk with minimal language-model behavioral change. 001A prioritizes filenames more strongly and may reduce the number of agent reads. **We do not know whether 001A's extra prompt complexity improves or hurts E4B actual patches.** All queries were manually selected from the dev issue statements, and the same dev set was used for ablation. These retrieval results cannot prove Kaggle score uplift.

Source experiments: [pre-registered G0-SEARCH-006](G0_SEARCH_006_PROTOCOL.md), [raw 9-task commands](G0_SEARCH_006_RAW.json), [offline scoring JSON](G0_SEARCH_006_SCORED.json), [results](G0_SEARCH_006_RESULTS.md). There was **zero** E4B inference, zero user-submitted entry, zero paid GPU/API/RunPod consumption.

## Next gate / decision

Freeze same issue budget / model settings for **three-arm true E4B pilot**: unmodified v15 vs minimally quoted EXP-AGENT-002 vs full EXP-AGENT-001A. Score **model-generated** patches on 6–8 development issues with independently verified F2P/P2P, track per-case solved/net solved, patch validity, wall time and tool calls. Expand to heldout **only after** choosing an approach from development results; do not use the gold oracle patches as agent inputs. **Explicit owner approval required before consuming any GPU quota, third-party API, RunPod fees or Kaggle submission quota.**

Protect best 31B Main v11/v14 Public0.17 and best E4B v15 Public0.06. Proposed single pilot paid compute cap must be approved separately; no costs incurred here.
