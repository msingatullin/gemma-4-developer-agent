# G1-001 — pre-registered real SWE task oracle smoke

Date: 2026-11-12. **CPU-only independent evaluator check; no agent/model inference**.

Purpose: establish that a real task-specific F2P test is **RED on pinned base** and **GREEN after a known-good gold patch**, with a separate P2P regression set passing on the same patched checkout. A test passing on base, an import error, or a missing test is NOT valid evidence of RED→GREEN.

## Frozen sources

- Real SWE-bench task `pallets__flask-4045` from repository manifest `paper/small_model_benchmark/manifest.json` SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf` (read-only offline evaluator; NEVER exposed to agent).
- Pinned upstream base commit `d8c37f43724cd9fb0870f77877b7c4c7e38a19e0`, from already available local upstream bare cache; no production repo writes.
- Official test patch SHA256 `def1da53a3857f67b571f108abde6fcdac61da5c7820c0749fa7c487fe87a62a`; gold patch SHA256 `6c4055e1cb35cf9c5d50bbba639af1787d6f5d5146f9539cedc364a43d01c687`. Used ONLY by offline oracle.
- Docker pre-existing `gemma-paper-cpu:py310-20261110` Python3.10.22, pytest6.2.5; `--network none`, `--cpus 1`, `--memory 768m`, `--pids-limit 64`. No install from internet, model, GPU or submission.

## Fixed tests

F2P:
1. `tests/test_blueprints.py::test_dotted_name_not_allowed`
2. `tests/test_blueprints.py::test_route_decorator_custom_endpoint_with_dots`

P2P:
1. `tests/test_blueprints.py::test_template_filter`
2. `tests/test_blueprints.py::test_add_template_filter`

## Strict protocol

1. Independently create **two isolated checkouts** at pinned base; apply identical test patch to both. `BASE` retains original implementation. Apply gold source patch only to `GOLD`.
2. Run the exact F2P tests in isolated Docker on BASE and GOLD with `PYTHONPATH=/workspace/src`, no network; store stdout/stderr, process exit, start/end timestamps and parsed pytest summary. Run P2P on GOLD with same conditions.
3. An **environment/import/collection error**, missing test, timeout or unrelated failure is `ENV_BLOCKED`, never count as F2P RED proof.
4. PASS requires both tests have clear assertion RED on BASE (not just nonzero), both GREEN on GOLD, and two distinct P2P GREEN on GOLD; exact checkout hashes and patch SHA verified.
5. No model inputs or hidden grader. This single task is evaluator bring-up, not an end-to-end E4B A/B sample or proof of competition improvement.

If environment missing a declared dependency, record the error and STOP (no broad installs or unapproved paid resources). Existing source/oracle files stay on VPS. Time target <=10 min CPU; spending $0; no Kaggle sends.
