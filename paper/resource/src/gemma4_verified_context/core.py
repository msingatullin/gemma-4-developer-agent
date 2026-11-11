"""Deterministic, standard-library-only safeguards for code-generation agents.

The compressor is the original frozen B2 algorithm, copied from the research
repository and additionally protected against diagnostic loss and expansion.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any
import re

from ._traceback_compressor import filter_pytest_log_v2


@dataclass(frozen=True)
class SliceResult:
    text: str
    symbol: str
    start_line: int
    end_line: int
    returned_full_source: bool
    fallback_reason: str | None = None

    def metadata(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k != "text"}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    error_type: str | None = None
    message: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class CompressionResult:
    text: str
    raw_bytes: int
    output_bytes: int
    byte_reduction_pct: float
    evidence_preserved: bool
    fail_open: bool
    evidence_lines: int

    def metadata(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k != "text"}


def _symbol_nodes(tree: ast.AST):
    def recurse(body, namespace):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = ".".join((*namespace, node.name))
                yield qname, node
                yield from recurse(getattr(node, "body", []), (*namespace, node.name))
    yield from recurse(getattr(tree, "body", []), ())


def slice_source(source: str, symbol: str, context_lines: int = 0) -> SliceResult:
    """Slice by *fully qualified* AST symbol; fail open on ambiguity or invalid text.

    All line numbers are 1-based and inclusive. Decorators are retained.
    Source is returned verbatim (including original indentation). The tool never
    silently returns a different class's similarly named method.
    """
    if not isinstance(source, str) or not isinstance(symbol, str):
        raise TypeError("source and symbol must both be str")
    if not isinstance(context_lines, int) or isinstance(context_lines, bool) or context_lines < 0:
        raise ValueError("context_lines must be a nonnegative integer")
    lines = source.splitlines(keepends=True)
    end = len(lines)
    def fallback(reason):
        return SliceResult(source, symbol, 1 if end else 0, end, True, reason)
    if not symbol.strip():
        return fallback("empty_symbol")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return fallback("invalid_python_source")
    matches = [node for name, node in _symbol_nodes(tree) if name == symbol]
    if len(matches) != 1:
        return fallback("symbol_not_found" if not matches else "ambiguous_symbol")
    node = matches[0]
    first = min([node.lineno, *(x.lineno for x in node.decorator_list)])
    last = node.end_lineno
    if last is None:
        return fallback("unknown_end_lineno")
    start = max(1, first - context_lines)
    stop = min(end, last + context_lines)
    value = "".join(lines[start - 1:stop])
    if not value:
        return fallback("empty_symbol_slice")
    return SliceResult(value, symbol, start, stop, False, None)


def check_syntax(source: str, filename: str = "<candidate>") -> GateResult:
    """CPU syntax gate; does not run imports or other candidate code."""
    if not isinstance(source, str):
        raise TypeError("source must be str")
    try:
        compile(source, filename, "exec")
    except (SyntaxError, ValueError, TypeError, OverflowError) as exc:
        return GateResult(False, type(exc).__name__, str(exc),
                          getattr(exc, "lineno", None), getattr(exc, "offset", None))
    return GateResult(True)


def diagnostic_lines(text: str) -> Counter[str]:
    """Frozen explicit evidence-marker definition from the log study."""
    failure_header = re.compile(r'^_{3,}\s*.*?\s*_{3,}$')
    return Counter(
        line.strip() for line in text.splitlines() if (
            line.lstrip().startswith(('E ', 'E\t', '> ', 'FAILED ', 'ERROR '))
            or line.strip() == 'E'
            or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):', line.strip())
            or failure_header.match(line.strip())
        )
    )


def compress_log(log: str) -> CompressionResult:
    """Run the original B2 compressor with a conservative integrity fail-open gate.

    Always count *UTF-8 bytes* rather than incorrectly labeling characters as
    model tokens. This does not guarantee total semantic equivalence; only the
    named diagnostic markers are checked for multiplicity and order.
    """
    if not isinstance(log, str):
        raise TypeError("log must be str")
    original = diagnostic_lines(log)
    proposed = filter_pytest_log_v2(log)
    changed = proposed != log
    parsed = diagnostic_lines(proposed)
    intact = not any(parsed[line] < count for line, count in original.items())
    # Do not expand or drop any selected marker. For recognized empty/nonpytest
    # input the underlying algorithm already returns unmodified text.
    if not intact or len(proposed.encode("utf-8")) >= len(log.encode("utf-8")):
        proposed = log
        intact = True
    raw_bytes = len(log.encode("utf-8"))
    out_bytes = len(proposed.encode("utf-8"))
    # 0.0 for an empty string, no division-by-zero.
    ratio = (100.0 * (raw_bytes - out_bytes) / raw_bytes) if raw_bytes else 0.0
    return CompressionResult(proposed, raw_bytes, out_bytes, round(ratio, 5),
                             intact, proposed == log, sum(original.values()))
