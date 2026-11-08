#!/usr/bin/env python3
"""
Blinded and Sandboxed Evaluation Engine for Gemma 4:
- Pre-flight compilation check via compile()
- Blinded defect localization evaluation from DEFECT_LOCATION field
- Independent semantic root cause explanation check
- Sandboxed test suite execution via sandbox.py (zero leaked secrets, CPU/RAM/process limits)
"""
import re
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TASKS_DIR = BASE_DIR / "tasks"

sys.path.insert(0, str(BASE_DIR))
from sandbox import run_in_sandbox

def parse_structured_response(response_text: str) -> dict:
    """Extract DEFECT_LOCATION, ROOT_CAUSE, and PROPOSED_CODE from model output."""
    loc_match = re.search(r"DEFECT_LOCATION:\s*([^\n]+)", response_text, re.IGNORECASE)
    location = loc_match.group(1).strip() if loc_match else ""
    
    cause_match = re.search(r"ROOT_CAUSE:\s*(.*?)(?=PROPOSED_CODE|```|$)", response_text, re.IGNORECASE | re.DOTALL)
    root_cause = cause_match.group(1).strip() if cause_match else ""
    
    # Extract code
    code_match = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
    if not code_match:
        code_match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
    code = code_match.group(1).strip() if code_match else ""
    
    return {
        "location": location,
        "root_cause": root_cause,
        "code": code
    }

def check_preflight_syntax(code: str) -> tuple[bool, str]:
    """Pre-flight compilation gate via compile()."""
    if not code:
        return False, "Empty code patch"
    try:
        compile(code, "<candidate_patch>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} at line {e.lineno}"
    except Exception as e:
        return False, f"CompilationError: {e}"

def evaluate_blinded_localization(model_location: str, target_symbol: str) -> bool:
    """
    Check if the model correctly identified the target symbol without prior knowledge.
    Requires model_location to contain the target function or class name.
    """
    if not model_location:
        return False
        
    m_clean = model_location.lower().replace("`", "").strip()
    target_parts = [p.lower() for p in target_symbol.split(".")]
    
    # Target function or class name must be in the localized string
    return any(p in m_clean for p in target_parts if len(p) >= 3)

def evaluate_blinded_root_cause(model_cause: str, meta: dict) -> bool:
    """
    Evaluate the explanatory quality of ROOT_CAUSE against ground truth concepts.
    Operates strictly on the ROOT_CAUSE text block (not on the code).
    """
    if not model_cause:
        return False
        
    cause_clean = model_cause.lower()
    
    # Check expected exception name
    exp_exc = meta["expected_exception"].lower()
    exc_found = exp_exc in cause_clean
    
    # Key concept tokens from gold explanation
    gold_words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", meta["root_cause"])]
    matches = sum(1 for w in gold_words if w in cause_clean)
    concept_ratio = matches / max(len(gold_words), 1)
    
    return exc_found or (concept_ratio >= 0.25)

def evaluate_response(task_id: str, response_text: str, meta: dict) -> dict:
    """
    Perform full blinded, sandboxed evaluation.
    """
    parsed = parse_structured_response(response_text)
    
    # 1. Blinded Localization
    target_sym = meta.get("target_symbol", "")
    loc_pass = evaluate_blinded_localization(parsed["location"], target_sym)
    
    # 2. Root Cause Explanation Quality
    cause_pass = evaluate_blinded_root_cause(parsed["root_cause"], meta)
    
    # 3. Pre-flight Syntax Compilation
    syntax_pass, syntax_err = check_preflight_syntax(parsed["code"])
    
    # 4. Sandboxed Test Execution (only if syntax passed)
    if syntax_pass:
        tdir = TASKS_DIR / task_id
        test_file = tdir / "test_task.py"
        test_pass, test_log = run_in_sandbox(test_file, parsed["code"], timeout_seconds=15)
    else:
        test_pass = False
        test_log = f"Skipped test run due to syntax error: {syntax_err}"
        
    return {
        "task_id": task_id,
        "blinded_localization_pass": loc_pass,
        "root_cause_explanation_pass": cause_pass,
        "preflight_syntax_pass": syntax_pass,
        "syntax_error": syntax_err,
        "test_suite_pass": test_pass,
        "test_details": test_log[:500],
        "extracted_location": parsed["location"]
    }

if __name__ == "__main__":
    print("Testing blinded and sandboxed evaluator...")
    sample_resp = """DEFECT_LOCATION: Blueprint.__init__
ROOT_CAUSE: Blueprint names containing dots cause collision during nested blueprint route resolution.
PROPOSED_CODE:
```python
class Blueprint:
    def __init__(self, name: str, import_name: str, url_prefix: str = None):
        if "." in name:
            raise ValueError(f"Blueprint names may not contain dots: '{name}'")
        self.name = name
        self.import_name = import_name
        self.url_prefix = url_prefix

    def make_endpoint(self, endpoint: str) -> str:
        return f"{self.name}.{endpoint}"
```"""
    meta_p = TASKS_DIR / "task_01_flask_blueprint_dot" / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    
    res = evaluate_response("task_01_flask_blueprint_dot", sample_resp, meta)
    print("Evaluation result:", res)
    assert res["blinded_localization_pass"] is True
    assert res["root_cause_explanation_pass"] is True
    assert res["preflight_syntax_pass"] is True
    assert res["test_suite_pass"] is True
    print("Blinded & sandboxed evaluator self-test PASSED!")
