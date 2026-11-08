import pytest
from source import StrictUndefined, UndefinedError

def test_strict_undefined_slice():
    u = StrictUndefined("items")
    for i in range(18):
        print(f"[JINJA_AST_EVAL_{i}] evaluating AST subscript node")
    with pytest.raises(UndefinedError, match="'items' is undefined"):
        _ = u[:5]
