# EXP-AGENT-PROTOCOL-006 — real organizer Docker ContainerManager, pinned pytest11143 (2026-11-17)

**Hypothesis:** official swegemma 0.2.11 ContainerManager + native run_command work with the exact pinned pytest11143 historical source and leave it unmodified under a network-isolated CPU container.

**Expected uplift:** no solve-rate claim; elimination of a tool-environment integration blocker. Baseline PROTOCOL-005: 10/10 native wrapper tests using fake Docker, no real container. This test uses a **real Docker container**.

**Resource/cost:** existing nuremberf CPU VPS, one temporary container, image gemma-agent-g0-cpu-git:20261112, network=none, 1 CPU, 768 MiB, $0 incremental; zero model/GPU/API/Kaggle submissions.

**Implementation:** copied the previous official native bridge (no modifications to organizer wheel); changed historical source tree pin and 5 smoke assertions. Organizer wheel SHA256 9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3, swegemma 0.2.11. Historical pytest-dev__pytest-11143 tree 5e87fec76a0ead331441eaf05a1510c6c6efe6cf.

**Actual command execution:** Gateway nuremberf job `job_01M7KKYPNB00GGR91A00XFCGY7`, exit 0. Five actual native tool assertions **5/5 PASS**: working_directory, pytest_filename_locator, pytest_content_locator, git_tree_integrity, no_unintended_changes. Container created and removed successfully. All source read-only. No oracle/gold patches supplied to tool. CPU test script SHA256 `e59e3d7d251725fdd994347602103108b61bc3df9f555d9f43aa6f8cfe902a87`; result JSON SHA256 `4baddeb77d620d2c9952a9ee83ac20a169ce69f0a481524af11b8588ce9f14e3`; stdout log SHA256 `84f736bb61c9d4a09246c6b1afbe262777e9842f65a0198827bdc15c9faf0e86`.

**VPS artifacts:** `/opt/kaggle/gemma-agent-g0-20261112-audit/gpu001_private_preflight/f5_native_container_20261117/` (script, results.json, run.log).

**Verdict:** PASS_NATIVE_ORGANIZER_CONTAINER_PYTEST_5_CASES. This is *tool plumbing*, **not full ADK/model generation**, not F2P/P2P and **not an E4B solve-rate uplift**. Keep Main v11/v14=0.17 and Small E4B v15=0.06 frozen. F1 previously COMPLETE 0/3 model variants on one dev issue. No new GPU or submissions.

**Next:** CPU-only real native submit_patch/patch-capture/clean-worktree test in isolated historical source container; then model protocol readiness assessment. Do not spend GPU without separate authorization.
