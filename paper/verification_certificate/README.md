# Evidence-preserving pytest log compression: verifiable certificates

**Target:** Gemma 4 Developer Agent Paper Track, reusable `Best New Resource` artifact.

This module packages a **versioned, standard-library-only integrity certificate** for a compressed pytest failure log. A third party can recompute the exact selected diagnostic strings and SHA256 digests without trusting our compression function, a notebook's rendered screenshots or an LLM's explanation.

It is complementary to the existing [fail-open traceback compressor](../traceback_compressor.py) and [AST-guided resource](../../README.md); it **does not** change the original compressor's behavior or add model inference.

## How to reproduce with published materials

The [protocol](CERTIFICATE_TEST_PROTOCOL_20261111.md) was published before implementing this certificate. Download the five files via a regular GitHub clone:

```bash
git clone https://github.com/msingatullin/gemma-4-developer-agent.git
cd gemma-4-developer-agent
python3 paper/verification_certificate/run_certificate_adversarial.py \
  paper/traceback_compressor.py \
  paper/e2e_gemma_experiment/real_repo_sample/REAL_LOG_FIXTURES_5REPOS_20261111.json \
  paper/e2e_gemma_experiment/real_repo_sample/REAL_LOG_FIXTURES_HOLDOUT3_20261111.json
```

Expected output: `CERTIFICATION_PASS 11 of 11`, `CORRUPTION_REJECTION_PASS 165 of 165`, `BYTES_REDUCTION 72.01`. The script regenerates [row-level results](certificate_validation_report_20261111.json). This is a local CPU test; no Kaggle login, model weights, tokens, GPU or paid resources needed.

## Standalone API

```python
from paper.verification_certificate.diagnostic_certificate import produce, verify, canonical_json

raw = open("failing_pytest.log").read()
compressed = filter_pytest_log_v2(raw)
certificate = produce(raw, compressed)
assert verify(raw, compressed, canonical_json(certificate))
```

A certificate is a JSON object with version `pytest-diagnostic-integrity-v1`, input/output SHA256, byte counts, exact selected-marker counts, failure-header counts, failed-test-summary counts and an explicit verdict. A verifier recomputes **everything** from the supplied raw and compressed logs, rejects missing/duplicate JSON keys and checks the version. Delete, duplicate or alter a selected diagnostic string, or modify ordinary output bytes, and the original certificate no longer verifies.

## Evidence and trade-offs

The 11 authentic failing pytest logs span **8 upstream repositories**. Five were not used to develop the holdout experiment's new cases; specifically three **additional repositories** (Xarray, Pylint, SymPy) had their test IDs and acceptance criteria frozen in [a public protocol](../e2e_gemma_experiment/real_repo_sample/UNSEEN_3REPO_PRECOMMIT_20261111.md) before the new RED→GREEN tests.

On the 11-case *pooled secondary* analysis, the unchanged B2 compressor preserved all selected diagnostic/header/summary multiplicities in **11/11** logs, versus **2/11** for each `head35`/`tail35` truncation baseline. The pooled B2 reduction was **72.01% of raw UTF-8 log bytes**. For the three separately frozen newly-tested cases: B2 **3/3**, each line-truncation baseline **0/3**. These numbers measure **neither language-model tokens nor model issue solve rate**.

The certificate feature was developed after reviewing the publicly known cases. Its software tests **do not become independent held-out evidence** simply because the underlying traces include prospectively frozen cases. The 165 corruption controls are deterministic adversarial *unit tests*, not 165 different upstream failures, and are not a security penetration test.

## Security and scientific limits

- **Not semantic equivalence:** only specified diagnostic, fail site, failure-header and summary strings are protected; arbitrary omitted text could still affect a model.
- **Not authentication:** SHA256 detects changes relative to the supplied trusted certificate. It does not prove who created the certificate or prevent a malicious actor from changing both logs and the certificate.
- **Not a SWE solve-rate boost:** original five real Gemma 4 first-pass issue fixes were 1/5 for each prompting variant. Exploratory static patch repair and model feedback used the *same cases* and cannot be advertised as unbiased generalization.
- **Not evidence of beating any whole peer paper:** direct E4B transfer to Maroof's File@1 release gave 49/90 to 51/90, a nonsignificant difference (`p=0.6875`). The certificate has a different endpoint.
