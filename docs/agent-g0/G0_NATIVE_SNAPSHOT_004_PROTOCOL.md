# G0-NATIVE-SNAPSHOT-004 — organizer snapshot setup and real tool bridge

Date 2026-11-12. Pre-registered before G0-004 execution.

Hypothesis: the **unaltered organizer `swegemma.harness.container_setup.extract_snapshot`** extracts a historical task source snapshot into the task container `/workspace`, does not implicitly stage `skills/repo_locator/ast_locator.py` from the submitted agent package to `/tmp/ast_locator.py`, and permits the authentic `swegemma.tools.execution.run_command` to read implementation files. This tests actual task-snapshot staging, not the entire E4B model loop.

Frozen source: historically pinned Flask4992 commit `4c288bc97ea371817199908d0d9b12de9dae327e`, tracked tree SHA `2ba551370f1a4204efbab1f82ba6cfd611634723`. Take **only original pre-test/pre-gold source** from private `g1_multi_20261112_treesnap/G1-002/pinned_tree.tar`; generate deterministic `.tar.gz` with gzip header mtime=0; record its SHA256 and verify extracted snapshot's tracked Git tree SHA before testing. No gold patch or test patch is mounted or provided.

Organizer code provenance: `swegemma 0.2.11` SHA256 `9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3`, `adk_eval_core 0.1.0` from organizer wheelhouse v31. Import **unmodified** `swegemma.harness.container_setup.extract_snapshot`, `swegemma.sandbox.docker.ContainerManager`, and `swegemma.tools.execution.run_command`, with namespace import bypass of only unrelated top-level GPU/model eager imports. The actual code under test is unchanged.

Execution: isolated test-only image `gemma-agent-g0-cpu-git:20261112` sha256 `dfc9164e95596719ef4b420ed713b3ce8b6616fa3ce5917dd6bcd45bfd99b6ee`, network=none, CPU1, memory768MiB, no Kaggle submission. Use organizer native `ContainerManager.start`, `extract_snapshot`, tool `run_command` to test `/workspace` and `git ls-files` filename lookup, check `/tmp/ast_locator.py` absence, `git status --porcelain` clean. Git init/commit inside scratch container only, never original tree or prod files. Do not pass oracle gold/test patches or model weights.

PASS requires: source archive exact tree SHA reconstructed, real official extraction returns without error, unchanged source tree, native `run_command` outputs expected Flask file, missing hardcoded temp locator confirmed, clean scratch tree and created container removed in `finally`. If native method errors, classify setup BLOCKED honestly; do not silently fall back to manual extraction. No LLM tasks or F2P scoring. New spend $0 and no GPU/API/RunPod; only already-running VPS test resources.
