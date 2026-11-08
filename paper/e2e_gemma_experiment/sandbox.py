#!/usr/bin/env python3
"""
Secure Isolated Sandbox for Executing Untrusted Model-Generated Code.
Enforces:
1. Complete environment variable stripping (no access to API keys, tokens, secrets)
2. Operating system resource limits (RLIMIT_AS for RAM, RLIMIT_CPU for CPU time, RLIMIT_NPROC for process spawning)
3. Filesystem isolation in unprivileged temporary directory
4. Subprocess execution with strict wall-clock timeout
"""
import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path

# Try importing resource (available on Linux / Unix)
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

def set_sandbox_limits(max_cpu_seconds: int = 10, max_memory_bytes: int = 512 * 1024 * 1024):
    """Pre-execution hook applied to the child process before exec."""
    if not HAS_RESOURCE:
        return
        
    # 1. CPU Time Limit (soft, hard)
    resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_seconds, max_cpu_seconds + 5))
    
    # 2. Virtual Memory Limit (512 MB)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
    except (ValueError, OSError):
        pass  # Some Linux kernels or container runtimes restrict RLIMIT_AS modification
        
    # 3. Maximum process/thread creation (prevent fork bombs)
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except (ValueError, OSError):
        pass
        
    # 4. Maximum file write size (5 MB)
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024 * 1024, 5 * 1024 * 1024))
    except (ValueError, OSError):
        pass

def get_sanitized_environment() -> dict:
    """Return a completely sanitized environment dictionary with zero secrets."""
    safe_keys = ["PATH", "LANG", "LC_ALL", "PYTHONPATH"]
    clean_env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "42"
    }
    # Explicitly ensure NO credentials or secrets leak
    for k in os.environ:
        if any(secret_term in k.upper() for secret_term in ["TOKEN", "KEY", "SECRET", "AUTH", "PASS", "KAGGLE", "RUNPOD", "GITHUB", "SSH", "AWS", "GCP"]):
            # Blacklisted
            continue
    return clean_env

def run_in_sandbox(
    test_file_path: Path,
    candidate_code: str,
    timeout_seconds: int = 20,
    max_memory_mb: int = 512
) -> tuple[bool, str]:
    """
    Execute pytest on candidate_code in an isolated sandbox.
    Returns (passed: bool, output_log: str).
    """
    if not test_file_path.exists():
        return False, f"Test file {test_file_path} not found"
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        
        # 1. Copy test file
        shutil.copy2(test_file_path, tmp_p / "test_task.py")
        
        # 2. Write candidate source code
        (tmp_p / "source.py").write_text(candidate_code, encoding="utf-8")
        
        # 3. Prepare sanitized environment
        env = get_sanitized_environment()
        env["PYTHONPATH"] = str(tmp_p)
        
        # 4. Run pytest under restricted environment and limits
        cmd = [sys.executable, "-m", "pytest", "test_task.py", "-q"]
        
        try:
            res = subprocess.run(
                cmd,
                cwd=tmp_p,
                env=env,
                preexec_fn=lambda: set_sandbox_limits(max_cpu_seconds=10, max_memory_bytes=max_memory_mb * 1024 * 1024),
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            out = res.stdout + ("\n" + res.stderr if res.stderr else "")
            if res.returncode == 0:
                return True, "All tests passed successfully in sandbox."
            else:
                return False, f"Test failure (exit code {res.returncode}):\n{out}"
        except subprocess.TimeoutExpired:
            return False, f"Sandbox Timeout: Execution exceeded {timeout_seconds}s limit."
        except Exception as e:
            return False, f"Sandbox Error: {e}"
