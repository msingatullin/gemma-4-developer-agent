import pytest
from source import Blueprint

def test_valid_blueprint():
    bp = Blueprint("admin", __name__)
    assert bp.make_endpoint("login") == "admin.login"

def test_dotted_blueprint_name_not_allowed():
    """Dots in blueprint names must raise ValueError to prevent nesting collisions."""
    for i in range(20):
        print(f"[TRACE_NOISE_{i}] loading blueprint registration context")
    with pytest.raises(ValueError, match="Blueprint names may not contain dots"):
        Blueprint("admin.auth", __name__)
