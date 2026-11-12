# EXP-AGENT-002 — exact frozen v15 minimal shell-quote correction

**Date:** 2026-11-12. **Status:** PRE-REGISTERED before build. **No model inference, no Kaggle send.**

**Hypothesis:** the existing best E4B v15 agent's first search instruction contains `git grep -n "SPECIFIC_TOKEN" -- *.py | head -20`. Bash expands the **unquoted** `*.py` when root `setup.py` or `test_requests.py` exists (8/9 pinned DEV source trees in G0-SEARCH-005), blocking nested Python source matches. A minimal **two-single-quote edit** around the shell wildcard (`-- '*.py'`) avoids this failure, reducing search omissions without adding instructions or model complexity.

**Immutable baseline:** authenticated original owner Kaggle Small/E4B v15 submission `58073369`, Public Score `0.06`, actual ZIP SHA256 `f812377537d941a9d7308a0d0e153a7e1362ba5b8832e66520a3b8916e9ca63a` (3321 bytes), stored privately at `/opt/kaggle/gemma-agent-g0-20261112-audit/submitted_archives/v15/58073369.raw`.

**Exact code delta:**
- Only replace one unique literal prompt line occurrence:
  - BEFORE: `git grep -n "SPECIFIC_TOKEN" -- *.py | head -20`
  - AFTER: `git grep -n "SPECIFIC_TOKEN" -- '*.py' | head -20`
- **Everything else unchanged byte-for-byte:** the other lines of `prompts/system.md`, `agent.yaml`, `configs/sampling.yaml` and `eval_config.yaml`. No package skill scripts, no added tools, no model aliases, no token-budget changes. This is a genuinely isolated single-feature edit unlike multi-behavior 001A.

**Already observed *retrieval-only*, not a model measurement:** In preregistered G0-SEARCH-006 9 DEV issue search diagnostic with issue-only manually selected queries and gold paths used only after search, exact original v15 HIT@5 **1/9**, quote-only HIT@5 **4/9**, full EXP-AGENT-001A HIT@5 **4/9**; quote-only HIT@1 **2/9**, full 001A **4/9**. These are not SWE solve results and not independent heldout evidence. [Data](G0_SEARCH_006_RESULTS.md).

**Build and gate:** Verify source ZIP SHA256 and exact allowable four file names / harmless `configs/`, `prompts/` directory entries; enforce exactly one anchor; write a deterministic ZIP and manifest only into a new **private** VPS directory, never overwrite; verify every member SHA after build and exact text back-replacement; run repository static validator; build an independent second ZIP to confirm byte identical; then call genuine organizer `adk_submission.compile_submission()` in isolated CPU venv with nonexecuting tool registry, correct E4B model and 6 tools. No Kaggle submission, GPU, RunPod, external LLM API or paid CPU upgrade. Target <=5 min on existing VPS.

**Decision:** If build+static+official ADK compile PASS, accept only as **ready for a future controlled paired model A/B**, not as superior contest entry. No actual model solve rate may be claimed. Comparative pilot shall test frozen v15 vs EXP-AGENT-002 and EXP-AGENT-001A under identical E4B model/issue budget and independent F2P/P2P, only after explicit user approval for any GPU/API costs or Kaggle quota.

Experiment ID: `EXP-AGENT-002`. Expected search retrieval uplift 3/9 on observed dev queries, actual E4B solve uplift **unknown**. Costs $0 expected. No baseline replacement.
