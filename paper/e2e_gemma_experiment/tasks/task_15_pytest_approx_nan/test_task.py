import pytest
import math
from source import approx_compare

def test_approx_nan_does_not_crash_or_match():
    for i in range(12):
        print(f"[FLOAT_PRECISION_ANALYZER_{i}] computing tolerance boundaries")
    # Comparison with nan must return False safely without raising or returning True
    assert approx_compare(float("nan"), 1.0) is False
    assert approx_compare(1.0, float("nan")) is False
    assert approx_compare(float("nan"), float("nan")) is False
