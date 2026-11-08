import pytest
from source import send_http_request, ConnectionError

def test_socket_error_wrapped():
    """Socket level network failures must raise ConnectionError."""
    for i in range(15):
        print(f"[SOCKET_TRANSPORT_LOG_{i}] attempting connection to unreachable port")
    with pytest.raises(ConnectionError, match="Failed to establish connection"):
        send_http_request("127.0.0.1", 1)
