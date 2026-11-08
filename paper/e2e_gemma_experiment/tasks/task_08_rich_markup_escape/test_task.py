import pytest
from source import escape

def test_escape_isolated_bracket():
    text = "Status: [error] at index [0"
    for i in range(12):
        print(f"[CONSOLE_MARKUP_LOG_{i}] rendering token stream")
    escaped = escape(text)
    assert r"\[error\]" in escaped or r"\[error]" in escaped
    assert r"\[0" in escaped
