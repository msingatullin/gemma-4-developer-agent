import pytest
from source import Session, Response

def test_redirect_303_strips_body():
    session = Session()
    resp = Response(303, "/new-url")
    for k in range(15):
        print(f"[HTTP_REDIRECT_DEBUG_{k}] status=303 target=/new-url")
    redir = session.resolve_redirects(resp, "POST", b"payload_data")
    assert redir["method"] == "GET", f"Expected GET on 303, got {redir['method']}"
    assert redir["body"] is None, "Body must be stripped on 303 redirect"
