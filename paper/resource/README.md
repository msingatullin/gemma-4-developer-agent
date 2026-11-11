# Gemma 4 Verified Context — reusable zero-inference SWE agent safeguards

CPU-only Python package implementing reusable components from the [Gemma 4 Developer Agent Paper Track research](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/ast-guided-deterministic-gemma4-agent), distributed under Apache-2.0. No GPU, model server, API key, hosted inference or runtime third-party dependencies required.

**Goals:** (1) select the exact Python class/method with AST and explicit line numbers, (2) check patch syntax without running arbitrary candidate code, and (3) compress pytest errors **fail-open** when explicit diagnostic evidence could be lost.

This is a deterministic **tool layer**, not an LLM patch-solving model or a claim of superior Kaggle leaderboard performance. On our 11 authentic red/green test logs from 8 repos, the original B2 compressor preserved all *selected* diagnostic markers in 11/11 with 72.01% aggregate byte reduction. Those markers are not a proof of complete semantic equivalence. See the parent repository for task selection and scripts.

## Install locally

```bash
python -m pip install --no-deps ./paper/resource
# Or use PYTHONPATH=paper/resource/src without installation.
gemma4-verified-context --help
```

No PyPI release is asserted; installation is directly from this source tree.

## Example API

```python
from gemma4_verified_context import slice_source, check_syntax, compress_log

module = open("repo/file.py").read()
loc = slice_source(module, "Blueprint.add_url_rule", context_lines=2)
# loc.text, loc.start_line, loc.end_line; unknown/ambiguous -> entire original source

candidate = "def change():\n    return True\n"
gate = check_syntax(candidate)
assert gate.passed  # parsing/compilation only; never executes source

log = open("failing_pytest.log").read()
out = compress_log(log)
# out.text, out.evidence_preserved, out.fail_open, out.byte_reduction_pct
# If evidence integrity is uncertain, out.text == log.
```

## Command-line integration

```bash
python -m gemma4_verified_context slice repo/file.py Blueprint.add_url_rule --metadata > sliced.py
python -m gemma4_verified_context check candidate.py   # JSON; exit 1 if invalid
python -m gemma4_verified_context compress failing.log --metadata > compact.log
```

The `slice` command emits source as-is and returns exit code **2** on fail-open fallback (symbol not found/ambiguous/invalid source) so agents can explicitly handle it.

## Tests and integrity

```bash
PYTHONPATH=paper/resource/src python -m unittest discover -s paper/resource/tests -v
```

Public red/green fixture sets of 11 genuine upstream issues are included in `tests/fixtures/`. The tests verify exact diagnostic marker multiplicity and no expansion, and basic AST/compilation fail-open behavior.

**Limits:** Old Python syntax and unsupported/unparseable input triggers a safe full-source fallback; AST extraction is lexical, not control-flow semantic analysis. The compiler gate does not run unit tests and cannot guarantee behavior. The compressor preserves the selected markers, but other information may be omitted; read the original traceback when needed. No new Gemma inference is performed by this package.
