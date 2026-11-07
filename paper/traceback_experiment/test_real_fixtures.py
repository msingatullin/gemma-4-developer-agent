# Real test suite designed to evaluate traceback compressor retention
import pytest

def test_single_verbose_stdout():
    """Single test failure buried under verbose stdout spam."""
    for i in range(120):
        print(f"[STDOUT_BUFFER_LOG_NOISE_{i}] processing batch item {i} with metadata payload")
    assert 42 == 99, "EXACT_DIAGNOSTIC_ROOT_CAUSE: single_failure_target_marker"

def test_multiline_assertion_diff():
    """Multiline assertion failure with 30+ structured diagnostic detail lines."""
    diagnostics = ["MULTILINE_HEADER_MARKER"]
    for i in range(32):
        diagnostics.append(f"diagnostic_frame_detail_{i:02d}: payload_state_verification_active")
    diagnostics.append("MULTILINE_FOOTER_MARKER")
    assert False, "\n".join(diagnostics)

@pytest.mark.parametrize("scenario,expected,audit_marker", [
    ("alpha_case", 100, "ALPHA_PARAMETRIZED_CAUSE_KEY"),
    ("beta_case", 200, "BETA_PARAMETRIZED_PASS"),
    ("gamma_case", 300, "GAMMA_PARAMETRIZED_CAUSE_KEY"),
])
def test_parametrized_cases(scenario, expected, audit_marker):
    """Parametrized test suite where distinct fixtures fail with unique causes."""
    for j in range(15):
        print(f"[PARAM_BUFFER_{scenario}_{j}] debug message")
    if scenario == "alpha_case":
        assert False, f"FAILED_CASE: {audit_marker}"
    elif scenario == "beta_case":
        assert expected == 200
    elif scenario == "gamma_case":
        raise ValueError(f"CRITICAL_EXCEPTION: {audit_marker}")

def test_independent_cause_one():
    """Independent failure 1: standard AssertionError."""
    for i in range(25):
        print(f"[LOG_CAUSE_1_{i}] initializing subsystem")
    assert False, "INDEPENDENT_CAUSE_ONE_ASSERTION_MARKER"

def test_independent_cause_two():
    """Independent failure 2: ValueError with non-assertion trace."""
    for i in range(25):
        print(f"[LOG_CAUSE_2_{i}] validating schema")
    raise ValueError("INDEPENDENT_CAUSE_TWO_VALUE_ERROR_MARKER")

def test_independent_cause_three():
    """Independent failure 3: KeyError with dictionary contract breach."""
    d = {"status": "active"}
    print("[LOG_CAUSE_3] accessing missing key")
    val = d["missing_route_target_INDEPENDENT_CAUSE_THREE_MARKER"]
