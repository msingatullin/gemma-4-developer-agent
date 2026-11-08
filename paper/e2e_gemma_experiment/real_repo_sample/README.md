# Authentic Public Repository Defects Archive

This directory contains a curated reference sample of 5 genuine defects from public open-source repositories (`pallets/flask` and `psf/requests`).

## Provenance and Execution Status: ARCHIVED / NOT EXECUTED

- **Execution Status:** These tasks have **NOT** been evaluated by the Gemma 4 inference runner (`run_e2e_inference.py`).
- **Purpose:** They serve as an immutable, pinned benchmark resource and reference dataset for future full-repo end-to-end evaluations.
- **Experimental Separation:** All inference benchmarks and statistical comparisons in the current experiment are evaluated exclusively on the separate 15-task synthetic reproduction suite (`tasks/`). No claim of model performance on these 5 upstream tasks is made.

## Archive Contents per Instance

Each subdirectory contains:
- `meta.json`: Pinned git commit SHA, repository URL, date, fail-to-pass test list, SHA256 hashes.
- `problem_statement.txt`: Original issue description verbatim from the upstream project tracker.
- `gold_patch.diff`: Official upstream pull request patch that resolved the defect.
- `test_patch.diff`: Official regression test patch added upstream to verify the fix.
