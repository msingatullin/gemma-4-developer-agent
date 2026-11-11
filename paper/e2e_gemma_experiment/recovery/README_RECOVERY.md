# Class-aware AST patch recovery — authentic Gemma4 real5 post-hoc investigation

Evaluation: the previously generated 15 first-pass Gemma 4 responses on five authentic Flask/Requests issues; NOT a new model call.
Original strict scorer: A_raw 1/5 RESOLVED, B2 1/5, C 1/5.
Recovered A_raw for pallets__flask-4045: model response included two method replacements, but the original evaluator matched a different class's __init__ and the candidate had malformed sibling indentation. The new adapter disambiguates Blueprint.__init__ and Blueprint.add_url_rule from model-declared symbol owner and constructs an allowlisted single-file diff. It does not read gold reference patches.
Frozen base commit and test patch, unchanged Docker scorer: pallets__flask-4045 => RESOLVED (F2P PASS, P2P PASS). The previous A_raw success psf__requests-1963 is retained, resulting in A_raw 2/5 from 1/5. B2 and C remain 1/5.
Scientific limitation: exploratory POST-HOC patch application repair on the SAME five tasks, NOT new independent evidence of generalization and NOT a base-model improvement.
Repro: class_aware_model_patch.py, flask4045_firstpass_A_response.txt, flask4045_recovered_A_candidate.txt, firstpass_recovery_report_20261111.json. Evaluator source: paper/e2e_gemma_experiment/evaluate_real_repo_patches.py.
Reproduction: run Python transform_output(model_output,base_source,target_relative_path) using base src/flask/blueprints.py at d8c37f43724cd9fb0870f77877b7c4c7e38a19e0, then unchanged strict Docker evaluate_patch_on_task. Immutable pinned CPU images and environment are required. Do not use a reference gold patch to construct the candidate.
