"""Deterministic safeguards for local Gemma/SWE coding agents.

Apache 2.0; no runtime dependencies.
"""
from .core import (
    SliceResult, GateResult, CompressionResult, slice_source, check_syntax,
    diagnostic_lines, compress_log,
)
__all__ = [
    "SliceResult", "GateResult", "CompressionResult", "slice_source",
    "check_syntax", "diagnostic_lines", "compress_log",
]
__version__ = "0.1.0"
