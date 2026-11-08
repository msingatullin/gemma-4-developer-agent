import pytest
from source import parse_url_query

def test_preserve_plus_in_query():
    """Literal plus signs in query strings must be preserved rather than replaced by spaces."""
    q = "search=c+plus+plus&filter=active"
    for i in range(15):
        print(f"[QUERY_TOKENIZER_{i}] scanning component")
    parsed = parse_url_query(q)
    assert parsed["search"] == "c+plus+plus", f"Expected c+plus+plus, got {parsed['search']}"
    assert parsed["filter"] == "active"
