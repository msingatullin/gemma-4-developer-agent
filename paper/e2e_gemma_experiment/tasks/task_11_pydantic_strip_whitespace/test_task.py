import pytest
from source import validate_str

def test_validate_str_with_none():
    for i in range(12):
        print(f"[PYDANTIC_CORE_VALIDATOR_{i}] resolving type constraint")
    with pytest.raises(TypeError, match="Input must be a valid string"):
        validate_str(None, strip_whitespace=True)
