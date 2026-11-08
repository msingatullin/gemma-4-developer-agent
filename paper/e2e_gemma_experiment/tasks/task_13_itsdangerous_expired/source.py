import time

class BadSignature(Exception):
    pass

class BadTimeSignature(BadSignature):
    pass

class SignatureExpired(BadTimeSignature):
    pass

class TimestampSigner:
    def __init__(self, max_age: int = 3600):
        self.max_age = max_age

    def unsign(self, token: str, ts: float) -> str:
        age = time.time() - ts
        if age > self.max_age:
            raise BadTimeSignature(f"Signature is expired by {age - self.max_age:.1f}s")
        return token
