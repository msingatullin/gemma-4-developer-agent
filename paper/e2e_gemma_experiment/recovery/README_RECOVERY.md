# Class-aware AST patch recovery — authentic Gemma4 real5 post-hoc investigation

Evaluation: the previously generated 15 first-pass Gemma 4 responses on five authentic Flask/Requests issues; NOT a new model call.
Original strict scorer: A_raw 1/5 RESOLVED, B2 1/5, C 1/5.
Recovered A_raw for pallets__flask-4045: model response included two method replacements, but the original evaluator matched a different class's __init__ and the candidate had malformed sibling indentation. The new adapter disambiguates Blueprint.__init__ and Blueprint.add_url_rule from model-declared symbol owner and constructs an allowlisted single-file diff. It does not read gold reference patches.
Frozen base commit and test patch, unchanged Docker scorer: pallets__flask-4045 => RESOLVED (F2P PASS, P2P PASS). The previous A_raw success psf__requests-1963 is retained, resulting in A_raw 2/5 from 1/5. B2 and C remain 1/5.
Scientific limitation: exploratory POST-HOC patch application repair on the SAME five tasks, NOT new independent evidence of generalization and NOT a base-model improvement.
Repro: class_aware_model_patch.py, flask4045_firstpass_A_response.txt, flask4045_recovered_A_candidate.txt, firstpass_recovery_report_20261111.json. Evaluator source: paper/e2e_gemma_experiment/evaluate_real_repo_patches.py.
Reproduction: run Python transform_output(model_output,base_source,target_relative_path) using base src/flask/blueprints.py at d8c37f43724cd9fb0870f77877b7c4c7e38a19e0, then unchanged strict Docker evaluate_patch_on_task. Immutable pinned CPU images and environment are required. Do not use a reference gold patch to construct the candidate.


## 2026-11-11 second-stage static binding recovery (exploratory)

Recovered one more authentic upstream case across **all three original frozen response variants**, `psf__requests-2148`, without new model calls or gold patch input. The original generated `iter_content` method referred to `socket.error` without `import socket` and raised the Python builtin `ConnectionError` rather than the Requests package's `ConnectionError`. A conservative static adapter identifies unbound standard-library attribute names and resolves a locally defined same-name exception from the frozen repository's sibling `exceptions.py`. It produces only the original model-supplied method body plus explicit import bindings, applied as a full allowlisted source module.

Public code: [namespace_binding_recovery.py](namespace_binding_recovery.py), [evaluate_namespace_recovery.py](evaluate_namespace_recovery.py), [15-row sanitized report](namespace_recovery_sanitized_report_20261111.json). Exact frozen original model response text, prompt hashes, pre-existing baseline scores, and immutable Docker image IDs are required to re-score. The script accepts those existing private inputs as CLI arguments; it does not embed private tokens or model responses. Authentic upstream tests were executed again in the original isolated Docker scorer with F2P and P2P controls.

| Variant | Original first pass | After post-hoc class/import recovery |
|---|---:|---:|
| A_raw | 1/5 | **3/5** |
| B2_assertion_aware | 1/5 | **2/5** |
| C_tail35 | 1/5 | **2/5** |

The A_raw second extra success is `pallets__flask-4045` (class-aware splice); all three variants additionally solve `psf__requests-2148` (binding recovery). The original `psf__requests-1963` remains solved in each variant. The three namespace-repaired candidates underwent **fresh independent strict Docker F2P/P2P checks**, both PASS. No gold patch was used to construct recovered candidates.

**Scientific caveat:** This is a *post-hoc, same-task* patch-application/repair experiment derived after inspecting first-run failures. It is **not** an unbiased held-out success-rate estimate, demonstration that compressed context beats raw context, or an independent improvement to Gemma model weights. Do not compare these replay numbers directly to another agent's first-pass SWE-bench score or present them as a new public leaderboard result.
