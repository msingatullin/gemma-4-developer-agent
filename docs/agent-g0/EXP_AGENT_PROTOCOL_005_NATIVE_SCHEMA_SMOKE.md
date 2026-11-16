# EXP-AGENT-PROTOCOL-005 — 2026-11-16 CPU native tool schema smoke

**Hypothesis:** isolated protocol v3 can validate read-only shell actions while the real organizer swegemma 0.2.11 exposes only three native tools. **Expected uplift:** fewer malformed tool invocations in a future agent run; numeric solve-rate uplift unknown.

**Baseline:** F1 real E4B pilot on one DEV issue: 0/3 fixes; v15 Small 0.06 public, Main v11/v14 0.17 public (different tracks). F3 v3 safety 5/5 new and 8/8 legacy CPU tests.

**Method/resources:** Existing nuremberf CPU, no GPU, no model/API calls, no Kaggle submission. Imported actual installed swegemma.tools.execution from official organizer 0.2.11 isolated venv. Exercised native factories against fake sandbox context/docker; did not execute full real ADK agent or genuine Docker container. Used v3 adapter only for command allowlist checks.

**Actual:** 10/10 unittest PASS, 0.001s test suite, exit 0. Verified make_run_command(command), make_submit_patch(), make_get_status(); success/error/timeout response schema, budget count semantics, patch capture, and no native read_file/edit_file factories. Pipeline bypass remains rejected. No evidence of patch correctness or solve rate.

**SHA256:** test source `32e1b8d725d3d6348acbaeb0d9a16530220b8b22866eca98a62250bd9e0ff915`; test log `a1b9c5a50e39fcc80bddaa1268602b872146cbcaeccf77851cc6a9511720d6ba`; v3 candidate `12a3633e2f5a55d1ed25ff2181f81a01c1aaecbafa74fb5793951894a192e7cb`.

**VPS:** `/opt/kaggle/gemma-agent-g0-20261112-audit/gpu001_private_preflight/f4_native_tool_smoke_20261116/`.

**Verdict:** CPU schema PASS; end-to-end official ADK compatibility and E4B solve uplift HOLD. Next free stage: run genuine native ContainerManager+tool bridge against isolated pinned task source with no model and verify actual sandbox command and patch collection; no further GPU without explicit permission.
