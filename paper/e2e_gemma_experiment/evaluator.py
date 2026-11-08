#!/usr/bin/env python3
"""
Two-Tier Blinded Diagnostic and Execution Evaluator for Gemma 4:

Tier 1 (Primary): Objective Pre-Registered Rubric
- Exact canonical target symbol matching from DEFECT_LOCATION
- Multi-concept required semantic criteria for ROOT_CAUSE (all required concept sets must be satisfied)
- Forbidden hallucination / misdiagnosis rejection

Tier 2 (Auxiliary / Proxy): Lexical Heuristic
- Substring component matching for localization
- Bag-of-words overlap and exception token matching for root cause

Execution Safety:
- collect_only mode (DEFAULT): Completely disables candidate code execution.
- Sandboxed execution is strictly opt-in (execute_candidate=True) with resource limits.
"""
import re
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TASKS_DIR = BASE_DIR / "tasks"

# Pre-registered Objective Rubrics for all 15 tasks
OBJECTIVE_DIAGNOSTIC_RUBRICS = {
    "task_01_flask_blueprint_dot": {
        "required_symbols": ["blueprint.__init__", "blueprint"],
        "required_concept_sets": [
            ["dot", "period", "dotted"],
            ["blueprint", "name"],
            ["endpoint", "collision", "subdomain", "url_prefix", "route", "delimiter"]
        ],
        "forbidden_misdiagnoses": ["syntaxerror", "circular import"]
    },
    "task_02_flask_config_mode": {
        "required_symbols": ["config.from_file", "from_file"],
        "required_concept_sets": [
            ["mode", "parameter", "argument"],
            ["binary", "'rb'", "rb", "bytes", "tomllib", "pickle"],
            ["text", "'r'", "hardcoded", "default", "open"]
        ],
        "forbidden_misdiagnoses": ["keyerror", "missing file"]
    },
    "task_03_requests_redirect_body": {
        "required_symbols": ["session.resolve_redirects", "resolve_redirects", "rebuild_method"],
        "required_concept_sets": [
            ["303", "see other"],
            ["body", "data", "payload"],
            ["get", "method", "strip", "drop", "clear", "none"]
        ],
        "forbidden_misdiagnoses": ["timeout", "connectionerror"]
    },
    "task_04_requests_socket_error": {
        "required_symbols": ["send_http_request", "httpadapter.send", "adapter.send"],
        "required_concept_sets": [
            ["socket.error", "socket", "low-level"],
            ["connectionerror", "requests.exceptions"],
            ["wrap", "catch", "reraise", "raise", "translate", "abstraction"]
        ],
        "forbidden_misdiagnoses": ["sslerror", "dns error"]
    },
    "task_05_click_choice_case": {
        "required_symbols": ["choice.convert", "choice"],
        "required_concept_sets": [
            ["case_sensitive", "case sensitive"],
            ["case", "lowercase", "case-insensitive", "lower", "exact"],
            ["match", "lookup", "compare", "search", "choice"]
        ],
        "forbidden_misdiagnoses": ["badparametertype", "missing option"]
    },
    "task_06_jinja2_undefined_slice": {
        "required_symbols": ["strictundefined.__getitem__", "strictundefined"],
        "required_concept_sets": [
            ["slice", "slicing", "subscript"],
            ["undefinederror", "undefined"],
            ["strict", "strictundefined", "fail", "loud"]
        ],
        "forbidden_misdiagnoses": ["template syntax", "recursion error"]
    },
    "task_07_urllib3_query_encoding": {
        "required_symbols": ["parse_url_query", "parse_url"],
        "required_concept_sets": [
            ["plus", "'+'"],
            ["space", "spaces"],
            ["query", "encoding", "unquote", "preserve", "normalize"]
        ],
        "forbidden_misdiagnoses": ["schememissing", "host invalid"]
    },
    "task_08_rich_markup_escape": {
        "required_symbols": ["escape", "markup.escape"],
        "required_concept_sets": [
            ["bracket", "brackets", "'['", "']'"],
            ["escape", "backslash", "escaping"],
            ["unclosed", "single", "tag", "balanced", "regex"]
        ],
        "forbidden_misdiagnoses": ["colortype", "render error"]
    },
    "task_09_pluggy_hook_order": {
        "required_symbols": ["hookcaller.execute", "hookcaller._add_hookimpl", "hookcaller"],
        "required_concept_sets": [
            ["trylast", "tryfirst"],
            ["order", "ordering", "position", "sequence", "priority"],
            ["end", "last", "append", "final"]
        ],
        "forbidden_misdiagnoses": ["hook missing", "spec mismatch"]
    },
    "task_10_marshmallow_empty_str": {
        "required_symbols": ["stringfield.deserialize", "stringfield"],
        "required_concept_sets": [
            ["empty string", '""', "''", "empty"],
            ["none", "null"],
            ["falsy", "allow_none", "truthy", "check", "override"]
        ],
        "forbidden_misdiagnoses": ["validationerror", "regex mismatch"]
    },
    "task_11_pydantic_strip_whitespace": {
        "required_symbols": ["validate_str", "validator"],
        "required_concept_sets": [
            ["strip", "whitespace"],
            ["none", "null", "non-string"],
            ["attributeerror", "typeerror", "before", "order", "check"]
        ],
        "forbidden_misdiagnoses": ["missing field", "int conversion"]
    },
    "task_12_attrs_frozen_repr": {
        "required_symbols": ["frozenmodel.__setattr__", "frozenmodel"],
        "required_concept_sets": [
            ["frozeninstanceerror"],
            ["attributeerror"],
            ["exception", "type", "raise", "frozen", "mutate", "assign"]
        ],
        "forbidden_misdiagnoses": ["recursionerror", "unhashable"]
    },
    "task_13_itsdangerous_expired": {
        "required_symbols": ["timestampsigner.unsign", "timestampsigner"],
        "required_concept_sets": [
            ["signatureexpired"],
            ["badtimesignature"],
            ["expired", "expiration", "age", "max_age", "timeout"]
        ],
        "forbidden_misdiagnoses": ["badsignature", "secret key missing"]
    },
    "task_14_werkzeug_cookie_quote": {
        "required_symbols": ["dump_cookie", "cookie"],
        "required_concept_sets": [
            ["comma", "','"],
            ["quote", "quotes", "quoting"],
            ["rfc", "rfc 6265", "cookie", "value", "characters"]
        ],
        "forbidden_misdiagnoses": ["httponly", "samesite"]
    },
    "task_15_pytest_approx_none": {
        "required_symbols": ["approx_compare", "approx"],
        "required_concept_sets": [
            ["none", "null"],
            ["typeerror"],
            ["operand", "abs", "subtraction", "compare", "comparison"]
        ],
        "forbidden_misdiagnoses": ["zerodivision", "tolerance error"]
    }
}

def parse_structured_response(response_text: str) -> dict:
    """Extract DEFECT_LOCATION, ROOT_CAUSE, and PROPOSED_CODE from model output."""
    loc_match = re.search(r"DEFECT_LOCATION:\s*([^\n]+)", response_text, re.IGNORECASE)
    location = loc_match.group(1).strip() if loc_match else ""
    
    cause_match = re.search(r"ROOT_CAUSE:\s*(.*?)(?=PROPOSED_CODE|```|$)", response_text, re.IGNORECASE | re.DOTALL)
    root_cause = cause_match.group(1).strip() if cause_match else ""
    
    # Extract candidate code
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
    """Pre-flight compilation gate via compile(). Pure static check; does not execute code."""
    if not code:
        return False, "Empty code patch"
    try:
        compile(code, "<candidate_patch>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} at line {e.lineno}"
    except Exception as e:
        return False, f"CompilationError: {e}"

# ---------------------------------------------------------------------------
# Tier 1 (Primary): Objective Pre-Registered Rubric
# ---------------------------------------------------------------------------

def evaluate_objective_localization(model_location: str, task_id: str) -> bool:
    """Check if model location matches pre-registered canonical symbols."""
    rubric = OBJECTIVE_DIAGNOSTIC_RUBRICS.get(task_id)
    if not rubric or not model_location:
        return False
        
    m_clean = re.sub(r"[^\w.]", "", model_location.lower())
    for req in rubric["required_symbols"]:
        req_clean = re.sub(r"[^\w.]", "", req.lower())
        if req_clean in m_clean or m_clean in req_clean:
            return True
    return False

def evaluate_objective_root_cause(model_cause: str, task_id: str) -> bool:
    """
    Check if model root cause satisfies all pre-registered required concept sets
    and does not trigger forbidden hallucinated misdiagnoses.
    """
    rubric = OBJECTIVE_DIAGNOSTIC_RUBRICS.get(task_id)
    if not rubric or not model_cause:
        return False
        
    cause_lower = model_cause.lower()
    
    # 1. Check forbidden misdiagnoses
    for forbidden in rubric.get("forbidden_misdiagnoses", []):
        if forbidden.lower() in cause_lower:
            return False
            
    # 2. Check each required concept set (must have at least one term from each set)
    for concept_set in rubric.get("required_concept_sets", []):
        set_satisfied = any(term.lower() in cause_lower for term in concept_set)
        if not set_satisfied:
            return False
            
    return True

# ---------------------------------------------------------------------------
# Tier 2 (Auxiliary / Proxy): Lexical Heuristic
# ---------------------------------------------------------------------------

def evaluate_heuristic_lexical_localization(model_location: str, target_symbol: str) -> bool:
    """Auxiliary proxy: Substring match of 3+ char symbol components."""
    if not model_location or not target_symbol:
        return False
    m_clean = model_location.lower().replace("`", "").strip()
    target_parts = [p.lower() for p in target_symbol.split(".")]
    return any(p in m_clean for p in target_parts if len(p) >= 3)

def evaluate_heuristic_lexical_root_cause(model_cause: str, meta: dict) -> bool:
    """Auxiliary proxy: Exception name match or >=25% word overlap with gold sentence."""
    if not model_cause:
        return False
    cause_clean = model_cause.lower()
    exp_exc = meta.get("expected_exception", "").lower()
    exc_found = (exp_exc in cause_clean) if exp_exc else False
    
    gold_words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", meta.get("root_cause", ""))]
    matches = sum(1 for w in gold_words if w in cause_clean)
    concept_ratio = matches / max(len(gold_words), 1)
    return exc_found or (concept_ratio >= 0.25)

# ---------------------------------------------------------------------------
# Main Evaluator Entry Point
# ---------------------------------------------------------------------------

def evaluate_response(
    task_id: str,
    response_text: str,
    meta: dict,
    execute_candidate: bool = False
) -> dict:
    """
    Evaluate model response with two-tier diagnostics and safe execution gating.
    
    Args:
        task_id: Identifier of the task
        response_text: Full response string from Gemma 4
        meta: Task metadata dictionary
        execute_candidate: If False (DEFAULT), candidate code execution is completely skipped.
                           If True, runs code in sandboxed subprocess.
    """
    parsed = parse_structured_response(response_text)
    
    # --- Tier 1 (Primary): Objective Pre-Registered Rubric ---
    obj_loc_pass = evaluate_objective_localization(parsed["location"], task_id)
    obj_cause_pass = evaluate_objective_root_cause(parsed["root_cause"], task_id)
    obj_diagnostic_pass = obj_loc_pass and obj_cause_pass
    
    # --- Tier 2 (Auxiliary / Proxy): Lexical Heuristic ---
    target_sym = meta.get("target_symbol", "")
    heur_loc_pass = evaluate_heuristic_lexical_localization(parsed["location"], target_sym)
    heur_cause_pass = evaluate_heuristic_lexical_root_cause(parsed["root_cause"], meta)
    
    # --- Pre-flight Static Syntax Check (Does not execute code) ---
    syntax_pass, syntax_err = check_preflight_syntax(parsed["code"])
    
    # --- Execution Gate ---
    if not execute_candidate:
        test_pass = None
        test_details = "Candidate code execution strictly disabled (collect_only mode)."
        exec_status = "COLLECT_ONLY_SKIPPED"
    else:
        if syntax_pass:
            from sandbox import run_in_sandbox
            tdir = TASKS_DIR / task_id
            test_file = tdir / "test_task.py"
            test_pass, test_log = run_in_sandbox(test_file, parsed["code"], timeout_seconds=15)
            test_details = test_log[:500]
            exec_status = "EXECUTED_SANDBOX"
        else:
            test_pass = False
            test_details = f"Skipped execution due to syntax error: {syntax_err}"
            exec_status = "SYNTAX_ERROR_ABORT"
            
    return {
        "task_id": task_id,
        "extracted_location": parsed["location"],
        "extracted_root_cause": parsed["root_cause"][:300],
        
        # Tier 1: Objective Rubrics (Primary Metric)
        "objective_localization_pass": obj_loc_pass,
        "objective_root_cause_pass": obj_cause_pass,
        "objective_diagnostic_pass": obj_diagnostic_pass,
        
        # Tier 2: Lexical Heuristic (Auxiliary Proxy)
        "heuristic_lexical_localization_pass": heur_loc_pass,
        "heuristic_lexical_root_cause_pass": heur_cause_pass,
        
        # Static Syntax Compilation
        "preflight_syntax_pass": syntax_pass,
        "syntax_error": syntax_err,
        
        # Execution Outcomes
        "test_suite_pass": test_pass,
        "execution_status": exec_status,
        "test_details": test_details
    }

if __name__ == "__main__":
    print("Self-testing two-tier evaluator...")
    sample_good = """DEFECT_LOCATION: Blueprint.__init__
ROOT_CAUSE: Blueprint names containing a dot cause collision during route and nested endpoint resolution.
PROPOSED_CODE:
```python
class Blueprint:
    pass
```"""
    meta_p = TASKS_DIR / "task_01_flask_blueprint_dot" / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    
    # Test 1: collect_only (default: execute_candidate=False)
    res_collect = evaluate_response("task_01_flask_blueprint_dot", sample_good, meta, execute_candidate=False)
    print("Collect-only result:", res_collect)
    assert res_collect["objective_localization_pass"] is True
    assert res_collect["objective_root_cause_pass"] is True
    assert res_collect["objective_diagnostic_pass"] is True
    assert res_collect["heuristic_lexical_localization_pass"] is True
    assert res_collect["heuristic_lexical_root_cause_pass"] is True
    assert res_collect["preflight_syntax_pass"] is True
    assert res_collect["test_suite_pass"] is None
    assert res_collect["execution_status"] == "COLLECT_ONLY_SKIPPED"
    
    # Test 2: Bogus location fails objective rubric
    sample_bad_loc = """DEFECT_LOCATION: random_module.helper
ROOT_CAUSE: Blueprint names containing a dot cause collision during route resolution.
PROPOSED_CODE:
```python
pass
```"""
    res_bad_loc = evaluate_response("task_01_flask_blueprint_dot", sample_bad_loc, meta, execute_candidate=False)
    assert res_bad_loc["objective_localization_pass"] is False
    assert res_bad_loc["objective_diagnostic_pass"] is False
    
    print("ALL EVALUATOR SELF-TESTS PASSED!")
