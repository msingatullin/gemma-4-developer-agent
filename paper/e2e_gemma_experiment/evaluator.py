#!/usr/bin/env python3
"""
Evaluation engine for Gemma 4 E2E Experiments:
- Pre-flight syntax validation via compile()
- Root cause diagnosis extraction and semantic oracle check
- Test suite verification in isolated temporary workspace
"""
import re
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

TASKS_DIR = Path(__file__).parent / "tasks"

def extract_patch_code(response_text: str) -> str:
    """Extract python code block from model response."""
    # Look for ```python ... ```
    m = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
    if m2:
        return m2.group(1).strip()
    return response_text.strip()

def check_preflight_syntax(code: str) -> tuple[bool, str]:
    """Pre-flight compilation gate via compile()."""
    try:
        compile(code, "<candidate_patch>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} at line {e.lineno}"
    except Exception as e:
        return False, f"CompilationError: {e}"

def evaluate_root_cause(response_text: str, meta: dict) -> bool:
    """
    Check if the model identified the critical diagnostic root cause.
    Checks for presence of target symbol or key exception / root cause concepts.
    """
    resp_lower = response_text.lower()
    target_sym_parts = [p.lower() for p in meta["target_symbol"].split(".")]
    sym_matched = any(p in resp_lower for p in target_sym_parts)
    
    exp_exc = meta["expected_exception"].lower()
    exc_matched = exp_exc in resp_lower
    
    # Check key words from gold root cause
    gold_words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", meta["root_cause"])]
    matched_words = sum(1 for w in gold_words if w in resp_lower)
    concept_matched = (matched_words / max(len(gold_words), 1)) >= 0.3
    
    return (sym_matched and (exc_matched or concept_matched)) or (exc_matched and concept_matched)

def verify_patch_execution(task_id: str, candidate_code: str) -> tuple[bool, str]:
    """
    Test the candidate patch in an isolated temporary directory.
    Returns (passed, details).
    """
    tdir = TASKS_DIR / task_id
    if not tdir.exists():
        return False, f"Task directory {tdir} not found"
        
    with tempfile.TemporaryDirectory() as tmp_work:
        tmp_p = Path(tmp_work)
        # Copy test file
        shutil.copy2(tdir / "test_task.py", tmp_p / "test_task.py")
        
        # Write candidate code to source.py
        (tmp_p / "source.py").write_text(candidate_code, encoding="utf-8")
        
        # Run pytest
        cmd = [sys.executable, "-m", "pytest", "test_task.py", "-q"]
        res = subprocess.run(cmd, cwd=tmp_p, capture_output=True, text=True, timeout=30)
        
        if res.returncode == 0:
            return True, "All tests passed successfully."
        else:
            return False, f"Test failure (exit code {res.returncode}):\n{res.stdout}\n{res.stderr}"

def evaluate_response(task_id: str, response_text: str, meta: dict) -> dict:
    """Full end-to-end evaluation of a model response."""
    patch_code = extract_patch_code(response_text)
    
    # 1. Pre-flight check
    syntax_ok, syntax_err = check_preflight_syntax(patch_code)
    
    # 2. Root cause diagnosis
    diag_ok = evaluate_root_cause(response_text, meta)
    
    # 3. Test verification (only if syntax passed)
    if syntax_ok:
        test_ok, test_details = verify_patch_execution(task_id, patch_code)
    else:
        test_ok, test_details = False, f"Skipped test run due to syntax error: {syntax_err}"
        
    return {
        "task_id": task_id,
        "preflight_syntax_pass": syntax_ok,
        "syntax_error": syntax_err,
        "root_cause_accuracy": diag_ok,
        "test_suite_pass": test_ok,
        "test_details": test_details
    }

if __name__ == "__main__":
    print("Testing evaluator harness against task_01...")
    meta_p = TASKS_DIR / "task_01_flask_blueprint_dot" / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    
    # Test gold code (should pass)
    gold_code = (TASKS_DIR / "task_01_flask_blueprint_dot" / "gold_patch.diff").read_text(encoding="utf-8")
    # Let's read fixed code from build_tasks
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_tasks", str(Path(__file__).parent / "build_tasks.py"))
    bt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bt)
    gold_fixed = next(s["fixed_code"] for s in bt.TASK_SPECS if s["id"] == "task_01_flask_blueprint_dot")
    
    mock_resp_gold = f"ROOT_CAUSE: Blueprint name contains dot causing nested collision.\n```python\n{gold_fixed}\n```"
    res_gold = evaluate_response("task_01_flask_blueprint_dot", mock_resp_gold, meta)
    print("Gold result:", res_gold)
    assert res_gold["preflight_syntax_pass"] is True
    assert res_gold["root_cause_accuracy"] is True
    assert res_gold["test_suite_pass"] is True
    print("Evaluator self-test PASSED!")
