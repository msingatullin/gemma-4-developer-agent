# ANSI/CI diagnostic chaos challenge — independently reproducible safety upgrade

**Purpose:** Try to break our own Gemini/Gemma SWE pytest log compressor and its independent integrity certificate using common terminal/CI formatting shifts, before hidden judging.

**First, the negative result:** Under a frozen, pre-published [88-case protocol](PROTOCOL_20261111.md), original B2 + original v1 certificate made **10 false PASS decisions**. Specifically, when ANSI SGR coloring enclosed individual `E ...` and failing `> ...` lines, neither component recognized the escaped critical text. The B2 compressor silently dropped such evidence on ten of eleven source logs; the old certificate approved those outputs because its selected-marker extractor also missed the escaped input lines. **We do not conceal this failure.**

**Defensive repair:** The new optional [robust_evidence_guard.py](robust_evidence_guard.py) normalizes ANSI SGR, CRLF and a narrow `[worker-0]` CI prefix for checking **exact selected-marker multiplicities**, while passing the *original text unchanged* to the frozen B2 compressor. When evidence is lost or the format cannot be recognized, it fails open and returns the raw log without lossy compression. It separately exposes a versioned, SHA256-based certificate that independently recomputes the normalized selected evidence, hashes, byte lengths, and verdict.

| Test | Original B2 / v1 certificate | New optional guard / v2 certificate |
|---|---:|---:|
| Eight fixed format-perturbation families × eleven known upstream failure logs | 78/88 pass independent oracle | **88/88 pass** |
| **False positive** certificate approvals of incomplete diagnostics | **10** | **0** on this challenge |
| Rejected deliberate tampering checks | Not run in this challenge's legacy arm | **704/704** |
| Outputs on original eleven authentic upstream failure logs | Frozen control | **11/11 byte-for-byte unchanged** |
| Byte reduction on those original authentic logs | 72.01% | **72.01% unchanged** |

**Crucial limitation:** the 88 cases are **synthetic transformations of the same eleven previously known authentic logs**, not 88 independent real software bugs or Gemma-generated solutions. The certificate checks a bounded selection of pytest diagnostic/header/summary strings, not full semantic equivalence, cryptographic message authentication, or downstream model solve rate. The test was developed after the eleven source logs were known; this is an adversarial software test, not independent held-out scientific replication.

## Run from a fresh public checkout (no dependencies, no GPU, no Kaggle account)

```bash
git clone https://github.com/msingatullin/gemma-4-developer-agent.git
cd gemma-4-developer-agent
python3 paper/robustness_challenge/run_chaos_experiment.py
python3 paper/robustness_challenge/validate_robust_guard.py
```

The runner reads the two [existing public log-fixture archives](../e2e_gemma_experiment/real_repo_sample/), applies the eight deterministic format changes without model inference, measures the original B2 against its existing certificate and against a separate ANSI-normalizing marker oracle, then tests the new guard. It publishes row-level outputs locally under `paper/robustness_challenge/legacy_chaos_results_20261111.json` and `robust_guard_results_20261111.json`. The compact [published 88-row report](compact_88_case_report_20261111.json) provides per-case outcomes and exact predeclared method definitions.

Expected:
```text
TOTAL 88 ORACLE_PASS 78 FAIL 10 FALSE_CERT_ACCEPTS 10
OLD 78 /88 | NEW 88 /88
FALSE_LEGACY_CERT_PASSES 10
NEW_CERT_TAMPER_REJECTED 704 / 704
ORIGINAL_11_BYTE_IDENTICAL True SAVED 72.01 %
```

## Usage in an agent

```python
from paper.traceback_compressor import filter_pytest_log_v2
from paper.robustness_challenge.robust_evidence_guard import guard, produce_certificate, verify

source_log = open("pytest-red.log", encoding="utf-8").read()
safe_log, meta = guard(source_log, filter_pytest_log_v2)
certificate = produce_certificate(source_log, safe_log)
assert verify(source_log, safe_log, certificate)
```

The new wrapper deliberately **does not change** the baseline `filter_pytest_log_v2` or published five-case real-Gemma solve-rate data. It does **not** attempt to infer that colored output can be compressed safely: ambiguous cases are returned as raw log. New unexpected formats outside this test suite can still expose other weaknesses, and this module warrants further independent adversarial evaluation.

**Release decision:** ACCEPT the optional guard as a backward-compatible safety improvement on this fixed challenge. Preserve and disclose the previous ten failures and leave the earlier experimental baselines unchanged; do not infer global superiority over other papers from this limited format robustness test.
