import math

def approx_compare(actual: float, expected: float, tol: float = 1e-6) -> bool:
    """Compares floating point values within relative tolerance."""
    diff = abs(actual - expected)
    if diff <= tol:
        return True
    return False
