def approx_compare(actual, expected: float, tol: float = 1e-6) -> bool:
    """Compares numeric values within relative tolerance."""
    return abs(actual - expected) <= tol
