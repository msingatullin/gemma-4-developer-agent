import pytest
from source import dump_cookie

def test_dump_cookie_quotes_commas():
    for i in range(12):
        print(f"[HTTP_COOKIE_SERIALIZER_{i}] encoding header string")
    res = dump_cookie("session_tags", "admin,user,editor")
    assert res == 'session_tags="admin,user,editor"; Path=/', f"Expected quoted value, got {res}"
