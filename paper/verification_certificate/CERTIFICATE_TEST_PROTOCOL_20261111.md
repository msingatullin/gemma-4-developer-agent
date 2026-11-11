# PAPER-CERT-REAL11-20261111 — Software contract pretest

## Goal
Provide a stand-alone, stdlib-only independently verifiable **certificate of exact selected pytest diagnostic/header/summary multiplicity preservation**. This is a software verification contribution, NOT a new inference test, new held-out statistical study, or proof of universal semantic equivalence.

## Frozen input corpus and scope
Use the previously public `REAL_LOG_FIXTURES_5REPOS_20261111.json` (8 original logs, 5 repositories) and `REAL_LOG_FIXTURES_HOLDOUT3_20261111.json` (3 further logs, 3 new repositories) from the exact GitHub project. Both have existing public SHA256 per-log source digests and reproducible `filter_pytest_log_v2` from `paper/traceback_compressor.py`. Cases will be counted separately as 8 retrospective and 3 precommitted diagnostic heldouts; **do not represent this new certificate feature as tested on untouched data** because its design is based on public fixtures.

## Acceptance before implementation
1. Contract-certificate has **versioned JSON schema**, SHA256 of both complete input/output bytes, byte counts, exact multiplicity of critical strings and summary/failure headers, verdict `PASS` or `FAIL`. Verifier uses Python stdlib exclusively and independently recomputes from supplied input/output and JSON. It must never trust producer's PASS flag alone.
2. For all 11 authentic real pytest failing logs, certificate verifies output from the **unchanged** B2 compressor with identical unmodified output. Record raw fallback cases; do not quietly skip them. Retain source and output hashes and total corpus byte reduction.
3. Adversarial tests must reject **every deletion/duplication of any diagnostic or header/summary marker** and every output-body corruption detected by SHA256 mismatch. Include wrong input hash, forged certificate content, truncated JSON, duplicate diagnostic and wrong version controls. Also test non-evidence ordinary text modification: hash must detect it, but this is not an assertion of semantic preservation.
4. Report pass/fail across all controls and bugs, if any; no averaging away failures, no gamma claims.
5. If any failure, publish negative result and **REJECT** feature until repaired; changes to compressor forbidden in this experiment. **No paid resources, external model calls or competition submissions**.

## Known limitations
Certificate proves a specific syntactic contract based on a selected evidence-line extractor and an explicit digest, **not full stack-trace or traceback semantics**, not adversarial immunity of a future different extractor, and not integrity if both code and signed payload are controlled by an untrusted adversary. SHA256 ensures byte-level tamper detection against a trusted manifest, not authentication or signatures.

This protocol is frozen before creating the new certificate producer/verifier or adversarial test report; author knows the public 11-log fixtures. The current submitted Paper Track manuscript and Notebook must remain unchanged until separately verified and deliberately published.
