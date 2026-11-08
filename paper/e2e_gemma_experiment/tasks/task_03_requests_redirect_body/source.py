class Response:
    def __init__(self, status_code: int, location: str):
        self.status_code = status_code
        self.headers = {"location": location}

class Session:
    def resolve_redirects(self, resp: Response, req_method: str, req_body: bytes) -> dict:
        """Resolve redirect preserving body inappropriately."""
        if resp.status_code in (301, 302, 303, 307):
            return {
                "method": req_method,
                "body": req_body,
                "url": resp.headers.get("location")
            }
        return None
