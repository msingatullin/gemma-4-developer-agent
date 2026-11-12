# G1-007 / G1-008 — two additional pinned development SWE real oracle runs

**Date:** 2026-11-12. **Pre-registered before executing tests.** Scope: CPU-only historical source oracle RED/GREEN and P2P in existing Docker; NO Gemma inference, no GPU quota consumption, no Kaggle sends.

Target: expand previously verified six SWE issues (four dev, two heldout) to **six validated development issues** for a future bounded E4B model pilot. Both new tasks are from the immutable dev partition of 50-task manifest SHA256 `8270d1b7f7b4d29cd5ea1ac21fe1a981a36c7455b522db69b6b2133ce1f6dfcf`.

| Experiment | Real SWE task | Exact pinned commit | F2P | P2P selectors |
|---|---|---|---|---|
| G1-007 | `pytest-dev__pytest-11148` | `2f7415cfbc4b6ca62f9013f1abd27136f46b9653` | `testing/test_pathlib.py::TestImportPath::test_remembers_previous_imports`; `testing/acceptance_test.py::test_doctest_and_normal_imports_with_importlib` | `testing/acceptance_test.py::TestGeneralUsage::test_docstring_on_hookspec`; `testing/acceptance_test.py::TestInvocationVariants::test_invoke_with_invalid_type` |
| G1-008 | `pytest-dev__pytest-5103` | `10ca84ffc56c2dd2d9dc4bd71b7b898e083500cd` | `testing/test_assertrewrite.py::TestAssertionRewrite::test_unroll_expression` | `testing/test_assertrewrite.py::TestAssertionRewrite::test_place_initial_imports`; `testing/test_assertrewrite.py::TestAssertionRewrite::test_dont_rewrite` |

Pre-existing CPU Docker images only: `gemma-paper-cpu:py311-20261110` for pytest11148, `gemma-paper-cpu:py39-20261110` for pytest5103. `--network none --read-only --cpus 1 --memory 768m --pids-limit 64`, timeout <=75s/group. No pip install inside task container.

Exact original tracked Git snapshot already prepared under `g0_search_005_dev_source_retry1/<task>/source`. Check `HEAD^{tree}` against historical bare Git `<pin>^{tree}`, assert `git status --porcelain` empty, copy **source-only** to independent BASE/GOLD worktrees; no gold/test patch present beforehand. Read test/gold patches from same hash-verified frozen manifest ONLY in independent offline evaluator. Apply test patch to BOTH, gold source patch to GOLD ONLY. Record source tree SHA and patches' SHA before test.

Where historical pytest uses a build-generated `src/_pytest/_version.py` declared by checked-in `pyproject.toml` but absent from tracked source, create an identical minimal local build-version file in both BASE/GOLD. Record its sha and exclude it from model inputs. Any further dependency/environment failures are `ENV_BLOCKED`, never count as RED.

Run exact BASE_F2P, GOLD_F2P, BASE_P2P, GOLD_P2P. PASS only if BASE F2P test failures correspond to the target bug (no missing dependency/collection), GOLD F2P **all passed**, and 2 selected distinct P2P tests pass on BOTH BASE and GOLD. Record actual stdout/stderr, exit, duration, pinned tree sha, gold/test patch sha, Docker image; a failure is held as BLOCKED, not silently replaced. Tests must not modify tracked source; if they do, classify leakage/side effect and stop.

These are gold-patch evaluator bring-up tasks, NOT model-generated patches or independent Kaggle score. Never move baseline scores 0.17 Main and 0.06 E4B without actual official test. No paid GPU/RunPod/API or contest sends. Existing GPU quota read-only inspection does not authorize consuming it.
