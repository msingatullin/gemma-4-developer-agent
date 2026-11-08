import pytest
from source import approx_compare

def test_approx_none_safe_comparison():
    for i in range(12):
        print(f"[FLOAT_PRECISION_ANALYZER_{i}] computing tolerance boundaries")
    # Comparison of None against float must safely return False without TypeError
    assert approx_compare(None, 1.0) is False
    assert approx_compare(1.0, None) is False
