# G1-007 / G1-008 — two more historical SWE oracles confirmed with real CPU pytest

Date: 2026-11-12. **Verdict: 2 additional DEV fixtures PASS**. Overall **8/50** pinned cases have a verified selected F2P RED→GREEN and selected P2P suite: 6 dev, 2 heldout across Flask, Requests and pytest. **These are offline reference-patch evaluator checks, NOT Gemma-generated solutions or private Kaggle score.**

## Executed actual tests

| Real SWE issue | Exact historical base commit | BASE F2P | GOLD F2P | BASE P2P | GOLD P2P |
|---|---|---|---|---|---|
| `pytest-dev__pytest-11148` | `2f7415cfbc4b6ca62f9013f1abd27136f46b9653` | **2 genuine assertion failures** | 2/2 PASS | 2/2 PASS | 2/2 PASS |
| `pytest-dev__pytest-5103` | `10ca84ffc56c2dd2d9dc4bd71b7b898e083500cd` | **1 genuine assertion failure** about missing `0 == 1` in pytest rewrite error | 1/1 PASS | 2/2 PASS | 2/2 PASS |

The exact historical Git trees were confirmed *before* any test/gold patches:
- pytest11148 Git tree SHA `267464d5003e787a35a2379726c9c5a54a43cf17`.
- pytest5103 Git tree SHA `b4f1860291efcf9923b7977bed74e34299ac4ebb`.

Testing: `gemma-paper-cpu:py311-20261110` and `gemma-paper-cpu:py39-20261110`; Docker `--network none --read-only --cpus 1 --memory 768m --pids-limit 64`, exact fixed test names, no GPU/API/model. BASE contains original code + official test patch, GOLD same plus **offline oracle gold source patch**, both source trees unchanged by test execution.

## Honest environment troubleshooting for old pytest5103

Initial runs did **not** reach test collection, all `ENV_BLOCKED`: missing `six`, then `atomicwrites`. Added identical pure-Python, read-only test-only dependencies in private `/g1deps` for BASE/GOLD (`six 1.17.0`, `atomicwrites 1.4.0`, `more-itertools 8.14.0`, `wcwidth 0.2.14`) with SHA hashes. An attempted nonexistent `atomicwrites==1.4.1` failed before install and was corrected in documented addendum to `1.4.0`.

Next both test processes were `ENV_BLOCKED` by `InvalidVersion: unknown`, because this historical pytest has `setuptools_scm write_to src/_pytest/_version.py` declared in its source `setup.py` but the generated file was absent. Added the same private build-generated version file to BASE and GOLD, SHA `fd1184104d722e6e4a1117f304bfabb4ed51a2596e3246d2439961ce050f1067`, without changing tracked original source.

Next the preinstalled setuptools `typeguard` pytest plugin was incompatible with old pytest’s allowed ini types. **Pre-registered** final environment change: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` set identically for BASE and GOLD. Only then were real tests collected and obtained the RED→GREEN and P2P outcomes above. No environment errors were ever counted as baseline RED, and earlier logs remain on private VPS.

**Evidence:** [preregistered protocol and all addenda](G1_007_008_PROTOCOL.md), [complete actual F2P/P2P stdout, exit codes, tracked Git tree and test/gold patch SHA](G1_007_008_VERIFIED_EVIDENCE.json), SHA256 `73b1f3814d0e73bd680d1ee3dde6bbe912d09a568ed518990586fd86077b2df4`. Prior env failures and final verified private source/logs are retained on existing VPS `nuremberf:/opt/kaggle/gemma-agent-g0-20261112-audit/g1_007_008_cpu_20261112`.

**Next:** use six verified DEV oracles for a pre-registered **three-arm authentic E4B** pilot, identical model and task budgets: original submitted v15, minimally quoted EXP-AGENT-002, full EXP-AGENT-001A. Score model-generated patches with independently verified F2P/P2P in the offline evaluator. No gold or test patch in agent input. Model runs need separate approval before spending even *free* Kaggle GPU quota. Keep frozen best Main v11/v14 0.17, E4B v15 0.06, no Kaggle send.
