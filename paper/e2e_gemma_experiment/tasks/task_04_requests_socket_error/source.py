import socket

class RequestException(Exception):
    pass

class ConnectionError(RequestException):
    pass

def send_http_request(host: str, port: int):
    """Dispatches raw socket connection without wrapping socket.error."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.001)
    s.connect((host, port))
    return b"HTTP/1.1 200 OK"
