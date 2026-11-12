# G0-NATIVE-TOOLS-003 — real swegemma CPU sandbox and run_command pre-registration

Date: 2026-11-12 20:30 MSK. This protocol is committed **before** any new sandbox test.

## Goal / boundary
Demonstrate authentic organizer `swegemma 0.2.11` `ContainerManager.start`, `copy_to`, `exec`, `stop` and the real `swegemma.tools.execution.run_command` tool executing *inside a clean air-gapped Docker workspace*, with **no model server, no model calls, no Kaggle competition sends and no oracle gold/test patch accessible in agent sandbox**.

Organizer wheelhouse source `metric/gemma-4-developer-agent-wheelhouse` version 31; official `swegemma-0.2.11-py3-none-any.whl` SHA256 `9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3`, `adk_eval_core-0.1.0` SHA256 `e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3`.

## Fixed input and execution conditions
- Use an immutable **historical source-only Git tree archive** of Flask-4992, original commit `4c288bc97ea371817199908d0d9b12de9dae327e`, Git tree SHA `2ba551370f1a4204efbab1f82ba6cfd611634723`, from existing local source cache `/opt/kaggle/gemma-agent-g0-20261112-audit/g1_multi_20261112_treesnap/G1-002/pinned_tree.tar`. Do NOT mount/test patch or gold patch directories.
- Use pre-existing Docker image `gemma-paper-cpu:py310-20261110`, network=none, CPU quota=1, memory=768m, container working dir `/workspace`. In clean container, copy the original source tar, extract it, initialize local Git (snapshot tree SHA must match above), and run limited read-only commands. Only Git setup modifies workspace, never source code.
- Import the **exact unmodified organizer wheel modules** `swegemma.sandbox.docker` and `swegemma.tools.execution`, using lightweight namespace packages to bypass package-wide `swegemma/__init__.py` eager model-serving imports. This does not replace or stub either tested module. `adk_eval_core.sandbox` is real. Python Docker SDK from isolated existing test venv.
- Invoke the **actual** `swegemma.tools.execution.run_command(ctx, cmd)` with test-only budget/context stubs (no calls blocked) so the genuine tool routes to genuine organizer `ContainerManager.exec`. Inputs:
  1. `pwd; git rev-parse --show-toplevel` must show `/workspace`.
  2. `git ls-files '*.py' | grep -i -F 'blueprint' ...` filename search must emit `src/flask/blueprints.py`.
  3. `git grep -n -i -F 'Blueprint' -- '*.py' ... | head -20` must report implementation source.
  4. `python3 /tmp/ast_locator.py --query Blueprint` must fail in clean sandbox (unprovided file), proving exact v17 hard-coded path not available under this setup.
  5. `git status --porcelain` must be empty (clean source tree).
- All Docker commands bounded <=20s, no shell network or package installs in container. Stop/remove **only the container created by this experiment** in `finally`, and record cleanup confirmation. Never touch other containers.

## Criterion, limitations and spend
- **PASS native tool bridge:** official ContainerManager create/copy/exec + official run_command valid JSON response for filename and implementation searches, detected absent `/tmp/ast_locator.py`, no source edits, cleanup. If directory/method API mismatch, classify blocker, not model failure.
- This is **not the full task harness evaluation** (no `swegemma.evaluate`, no LLM inference, no F2P/P2P). It is stronger than direct manual Docker subprocess because it tests the real organizer tool bridge. No score lift claim.
- No free Kaggle quota spent, no paid GPU/RunPod/API or production edits. Max existing CPU 1 core / 768MiB per container for under 2 minutes.
