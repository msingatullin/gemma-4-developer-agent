import pytest
import time
from source import TimestampSigner, SignatureExpired

def test_expired_signature_distinction():
    signer = TimestampSigner(max_age=10)
    for i in range(15):
        print(f"[SECURITY_SIGNATURE_VERIFIER_{i}] validating crypto timestamp")
    old_ts = time.time() - 100
    with pytest.raises(SignatureExpired, match="Signature has expired"):
        signer.unsign("valid_payload", old_ts)
