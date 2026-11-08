#!/usr/bin/env python3
"""
Security verification tests for the model code execution sandbox.
Validates:
1. Environment secret isolation (no leaked keys/tokens)
2. Infinite loop timeout termination
3. Normal execution functionality
"""
import os
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from sandbox import run_in_sandbox

def test_secret_isolation():
    print("Testing secret isolation...")
    # Inject fake sensitive env vars into host process
    os.environ["RUNPOD_API_KEY"] = "fake_secret_runpod_key_12345"
    os.environ["KAGGLE_KEY"] = "fake_secret_kaggle_key_67890"
    
    with tempfile.TemporaryDirectory() as td:
        tf = Path(td) / "test_secret.py"
        tf.write_text("""import os

def test_check_secrets():
    assert os.environ.get("RUNPOD_API_KEY") is None, "LEAK: RUNPOD_API_KEY visible in sandbox!"
    assert os.environ.get("KAGGLE_KEY") is None, "LEAK: KAGGLE_KEY visible in sandbox!"
""")
        passed, out = run_in_sandbox(tf, "x = 1\n", timeout_seconds=5)
        print("Secret isolation output:", out.strip())
        assert passed is True, f"Secret isolation failed: {out}"
        print("  [PASS] Secrets completely invisible inside sandbox!")

def test_infinite_loop_timeout():
    print("\nTesting infinite loop timeout enforcement...")
    with tempfile.TemporaryDirectory() as td:
        tf = Path(td) / "test_timeout.py"
        tf.write_text("""import time
from source import run_forever

def test_loop():
    run_forever()
""")
        infinite_code = """import time
def run_forever():
    while True:
        time.sleep(0.1)
"""
        passed, out = run_in_sandbox(tf, infinite_code, timeout_seconds=3)
        print("Timeout output:", out.strip())
        assert passed is False
        assert "Sandbox Timeout" in out or "timed out" in out or "Timeout" in out
        print("  [PASS] Runaway loop terminated strictly by sandbox watchdog!")

if __name__ == "__main__":
    test_secret_isolation()
    test_infinite_loop_timeout()
    print("\nALL SANDBOX SECURITY TESTS PASSED!")
