#!/usr/bin/env python3
"""
Containerized Evaluator for Authentic Upstream Repositories (Flask & Requests)
Fulfills Blocker 3 Requirements:
1. Deterministic extraction of PROPOSED_CODE from model response.
2. Robust patch application (Unified diff, AST function/method splice, or full-file overwrite).
3. Post-application AST syntax verification.
4. Execution in isolated Docker container (python:3.12-slim) with:
   - --network none (strictly 0 network calls guaranteed by Linux namespace)
   - --cap-drop ALL (no Linux capabilities)
   - --user 1000:1000 (unprivileged user)
   - --memory 1g (RAM limit)
   - --cpus 1.0 (CPU core limit)
5. Rigorous test evaluation:
   - F2P test execution (validates fix)
   - P2P regression test execution (verifies zero regressions)
   - Classification: RESOLVED | FAILED_F2P | REGRESSION | SYNTAX_ERROR | TIMEOUT | PATCH_APPLY_ERROR
6. Pre-flight validation controls:
   - Positive Control (gold patch -> RESOLVED)
   - Negative Control (base unchanged -> FAILED_F2P)
   - Malformed Control (syntax error -> SYNTAX_ERROR)
   - Deliberate Regression Control (regressing code -> REGRESSION)
"""

import os
import re
import ast
import json
import time
import shutil
import hashlib
import textwrap
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = REPO_ROOT / "paper" / "e2e_gemma_experiment" / "real_repo_sample"
WORK_BASE = Path("/tmp/eval_real_runs")
UPSTREAM_CACHE = Path("/home/mikhail/upstream_repos")

# Load verified offline P2P test list for Requests
REQUESTS_OFFLINE_TESTS_FILE = ARCHIVE_DIR / "requests_offline_p2p_tests.json"
REQUESTS_OFFLINE_TESTS = json.loads(REQUESTS_OFFLINE_TESTS_FILE.read_text(encoding="utf-8"))
REQUESTS_OFFLINE_FILTER = " or ".join(REQUESTS_OFFLINE_TESTS)

TASKS_MAP = {
    "pallets__flask-4045": {
        "instance_id": "pallets__flask-4045",
        "repo": "pallets/flask",
        "repo_bare": UPSTREAM_CACHE / "flask.git",
        "base_commit": "d8c37f43724cd9fb0870f77877b7c4c7e38a19e0",
        "python_version": "3.10",
        "target_file": "src/flask/blueprints.py",
        "test_file": "tests/test_blueprints.py",
        "test_filter": "test_dotted_name_not_allowed or test_route_decorator_custom_endpoint_with_dots",
        "f2p_tests": [
            "tests/test_blueprints.py::test_dotted_name_not_allowed",
            "tests/test_blueprints.py::test_route_decorator_custom_endpoint_with_dots"
        ],
        "regression_args": ["tests/test_blueprints.py"],
        "pinned_pkgs": ["werkzeug==2.0.1", "pytest==6.2.5", "setuptools==57.5.0"]
    },
    "pallets__flask-4992": {
        "instance_id": "pallets__flask-4992",
        "repo": "pallets/flask",
        "repo_bare": UPSTREAM_CACHE / "flask.git",
        "base_commit": "4c288bc97ea371817199908d0d9b12de9dae327e",
        "python_version": "3.11",
        "target_file": "src/flask/config.py",
        "test_file": "tests/test_config.py",
        "test_filter": "test_config_from_file_toml",
        "f2p_tests": [
            "tests/test_config.py::test_config_from_file_toml"
        ],
        "regression_args": ["tests/test_config.py"],
        "pinned_pkgs": ["pytest==7.4.4", "werkzeug==2.3.8"]
    },
    "pallets__flask-5063": {
        "instance_id": "pallets__flask-5063",
        "repo": "pallets/flask",
        "repo_bare": UPSTREAM_CACHE / "flask.git",
        "base_commit": "182ce3dd15dfa3537391c3efaf9c3ff407d134d4",
        "python_version": "3.11",
        "target_file": "src/flask/cli.py",
        "test_file": "tests/test_cli.py",
        "test_filter": "test_subdomain or test_host",
        "f2p_tests": [
            "tests/test_cli.py::TestRoutes::test_subdomain",
            "tests/test_cli.py::TestRoutes::test_host"
        ],
        "regression_args": ["tests/test_cli.py", "-k", "TestRoutes"],
        "pinned_pkgs": ["pytest==7.4.4", "werkzeug==2.3.8", "blinker==1.9.0"]
    },
    "psf__requests-1963": {
        "instance_id": "psf__requests-1963",
        "repo": "psf/requests",
        "repo_bare": UPSTREAM_CACHE / "requests.git",
        "base_commit": "110048f9837f8441ea536804115e80b69f400277",
        "python_version": "3.9",
        "target_file": "requests/sessions.py",
        "test_file": "test_requests.py",
        "test_filter": "test_requests_are_updated_each_time",
        "f2p_tests": [
            "test_requests.py::TestRedirects::test_requests_are_updated_each_time"
        ],
        "regression_args": ["test_requests.py", "-k", REQUESTS_OFFLINE_FILTER],
        "pinned_pkgs": ["pytest==6.2.5"]
    },
    "psf__requests-2148": {
        "instance_id": "psf__requests-2148",
        "repo": "psf/requests",
        "repo_bare": UPSTREAM_CACHE / "requests.git",
        "base_commit": "fe693c492242ae532211e0c173324f09ca8cf227",
        "python_version": "3.9",
        "target_file": "requests/models.py",
        "test_file": "test_requests.py",
        "test_filter": "test_iter_content_handles_socket_error",
        "f2p_tests": [
            "test_requests.py::RequestsTestCase::test_iter_content_handles_socket_error"
        ],
        "regression_args": ["test_requests.py", "-k", REQUESTS_OFFLINE_FILTER],
        "pinned_pkgs": ["pytest==6.2.5"]
    }
}

def extract_candidate_code(model_output: str) -> tuple:
    """
    Deterministically extracts proposed code or unified diff from model response.
    Returns: (extracted_code, code_type) where code_type is 'diff' or 'python'
    """
    if not model_output or not model_output.strip():
        return "", "empty"

    # 1. Match PROPOSED_CODE: ```(python|diff)? ... ```
    m = re.search(r"PROPOSED_CODE:\s*```(?:python|diff)?\s*\n(.*?)\n```", model_output, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if code.startswith(("diff --git", "--- ", "@@ ")):
            return code, "diff"
        return code, "python"

    # 2. Match any fenced code block
    m2 = re.search(r"```(?:python|diff)?\s*\n(.*?)\n```", model_output, re.DOTALL)
    if m2:
        code = m2.group(1).strip()
        if code.startswith(("diff --git", "--- ", "@@ ")):
            return code, "diff"
        return code, "python"

    # 3. Check if raw output is a diff
    if model_output.strip().startswith(("diff --git", "--- ", "@@ ")):
        return model_output.strip(), "diff"

    # 4. Fallback to raw text
    return model_output.strip(), "python"

def check_python_syntax(code_str: str) -> tuple:
    """Check if code parses into valid Python AST."""
    try:
        ast.parse(code_str)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"
    except Exception as e:
        return False, str(e)

def splice_ast_into_source(base_source: str, candidate_code: str) -> tuple:
    """
    Splices candidate function/method/class definitions into base source code
    using Python AST line ranges and indentation detection.
    """
    # If candidate is a full file (contains imports and top-level definitions matching full scale)
    if ("import " in candidate_code and len(candidate_code.splitlines()) > 50) or len(candidate_code.splitlines()) >= len(base_source.splitlines()) * 0.7:
        # Candidate appears to be a full replacement
        valid, err = check_python_syntax(candidate_code)
        if valid:
            return candidate_code, "FULL_FILE_REPLACE"
        return None, f"FULL_FILE_SYNTAX_ERROR: {err}"

    # Try to parse candidate
    valid, cand_err = check_python_syntax(candidate_code)
    if not valid:
        return None, f"CANDIDATE_SYNTAX_ERROR: {cand_err}"

    cand_tree = ast.parse(candidate_code)
    base_tree = ast.parse(base_source)

    # Collect top-level definitions in candidate
    cand_defs = [n for n in cand_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if not cand_defs:
        return None, "NO_FUNCTION_OR_CLASS_DEF_IN_CANDIDATE"

    lines = base_source.splitlines(keepends=True)
    modified = False

    for cand_node in cand_defs:
        target_name = cand_node.name
        matched = False
        current_source = "".join(lines)
        base_tree = ast.parse(current_source)

        # Extract just this definition's source code
        cand_lines_raw = candidate_code.splitlines(keepends=True)
        cand_sub_lines = cand_lines_raw[cand_node.lineno - 1 : cand_node.end_lineno]
        cand_sub_code = "".join(cand_sub_lines)

        # Check top-level match in base
        for base_node in base_tree.body:
            if isinstance(base_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and base_node.name == target_name:
                orig_line = lines[base_node.lineno - 1]
                indent = orig_line[:len(orig_line) - len(orig_line.lstrip())]
                dedented = textwrap.dedent(cand_sub_code.strip())
                reindented = textwrap.indent(dedented, indent) + "\n"
                lines = lines[:base_node.lineno - 1] + [reindented] + lines[base_node.end_lineno:]
                matched = True
                modified = True
                break

        if matched:
            continue

        # Check method inside class match
        for class_node in [n for n in base_tree.body if isinstance(n, ast.ClassDef)]:
            for item in class_node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target_name:
                    orig_line = lines[item.lineno - 1]
                    indent = orig_line[:len(orig_line) - len(orig_line.lstrip())]
                    dedented = textwrap.dedent(cand_sub_code.strip())
                    reindented = textwrap.indent(dedented, indent) + "\n"
                    lines = lines[:item.lineno - 1] + [reindented] + lines[item.end_lineno:]
                    matched = True
                    modified = True
                    break
            if matched:
                break

    if not modified:
        return None, "NO_MATCHING_DEFINITION_IN_BASE_FILE"

    new_source = "".join(lines)
    valid_final, final_err = check_python_syntax(new_source)
    if not valid_final:
        return None, f"POST_SPLICE_SYNTAX_ERROR: {final_err}"

    return new_source, "AST_SPLICE_SUCCESS"

def validate_candidate_diff_paths(candidate_code: str, target_rel_path: str) -> tuple:
    """Fail closed unless every file in a unified diff is exactly the allowlisted source file.

    This prevents candidates from changing tests, the evaluation harness or unrelated
    files (and prevents absolute paths / parent directory escapes) via patch headers.
    """
    expected = target_rel_path.replace("\\", "/")
    if not expected or expected.startswith("/") or ".." in expected.split("/"):
        return False, "UNSAFE_TARGET_PATH"
    old_paths, new_paths, git_paths = [], [], []
    git_header_count = 0
    for line in candidate_code.splitlines():
        if line.startswith("diff --git "):
            git_header_count += 1
            if git_header_count > 1:
                return False, "MULTIPLE_DIFF_HEADERS"
            tokens = line.split()
            if len(tokens) != 4:
                return False, "MALFORMED_DIFF_GIT_HEADER"
            git_paths.extend(tokens[2:4])
        elif line.startswith("--- "):
            old_paths.append(line[4:].split("\t", 1)[0].strip())
        elif line.startswith("+++ "):
            new_paths.append(line[4:].split("\t", 1)[0].strip())
        elif line.startswith(("Index:", "*** ", "Only in ", "Property changes on:",
                              "rename from ", "rename to ", "copy from ", "copy to ",
                              "GIT binary patch", "Binary files ", "new file mode ",
                              "deleted file mode ", "symlink ")):
            return False, "UNSUPPORTED_DIFF_OPERATION"
    if len(old_paths) != 1 or len(new_paths) != 1:
        return False, "REQUIRE_EXACTLY_ONE_FILE_PATCH"
    for raw in old_paths + new_paths + git_paths:
        if raw == "/dev/null" or not raw.startswith(("a/", "b/")):
            return False, "UNSAFE_DIFF_PATH"
        resolved = raw[2:]
        if resolved != expected or resolved.startswith("/") or ".." in resolved.split("/"):
            return False, "DIFF_TARGET_NOT_ALLOWLISTED"
    if not any(line.startswith("@@ ") for line in candidate_code.splitlines()):
        return False, "MISSING_DIFF_HUNK"
    return True, "ALLOWED_SINGLE_FILE_DIFF"


def apply_candidate_to_repo(task_work_dir: Path, target_rel_path: str, candidate_code: str, code_type: str) -> tuple:
    """
    Applies candidate code to target file in task directory.
    Returns: (success: bool, status_msg: str)
    """
    target_abs = task_work_dir / target_rel_path
    if not target_abs.exists():
        return False, f"Target file does not exist: {target_abs}"

    if code_type == "diff":
        # Never let a model-produced patch modify tests, other modules or parents.
        safe, reason = validate_candidate_diff_paths(candidate_code, target_rel_path)
        if not safe:
            return False, f"DIFF_REJECTED: {reason}"
        # Noninteractive, fail closed on fuzzy matches; checkout is disposable.
        res = subprocess.run(
            ["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-d", str(task_work_dir)],
            input=candidate_code.encode("utf-8"), capture_output=True
        )
        if res.returncode == 0:
            valid, err = check_python_syntax(target_abs.read_text(encoding="utf-8"))
            if valid:
                return True, "DIFF_PATCH_APPLIED"
            return False, f"DIFF_POST_SYNTAX_ERROR: {err}"
        return False, f"DIFF_APPLY_FAILED: {res.stderr.decode('utf-8', errors='replace')}"

    # Python code
    base_content = target_abs.read_text(encoding="utf-8")
    new_content, splice_status = splice_ast_into_source(base_content, candidate_code)
    if new_content is not None:
        target_abs.write_text(new_content, encoding="utf-8")
        return True, splice_status

    return False, f"CODE_APPLY_ERROR: {splice_status}"

def build_safe_docker_command(task_work_dir: Path, cmd: list, image: str) -> list:
    """Construct a credential-free, immutable-image, read-only test sandbox.

    The image must already contain a compatible Python interpreter, pytest
    and pinned dependencies for the task. No host user/site-packages mounts.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}", image):
        raise ValueError("PAPER_EVAL_IMAGE must be an immutable image@sha256:<64hex> reference")
    # Resolve only after rejecting symbolic links, otherwise .resolve() masks them.
    if task_work_dir.is_symlink():
        raise ValueError("Symlinked evaluation directory is not allowed")
    work = task_work_dir.resolve(strict=True)
    root = WORK_BASE.resolve()
    if root not in work.parents:
        raise ValueError("Evaluation directory must be inside WORK_BASE")
    if not work.is_dir():
        raise ValueError("Unsafe evaluation directory")
    if not cmd or cmd[0] != "python" or cmd[1:3] != ["-m", "pytest"]:
        raise ValueError("Only Python pytest is permitted in the evaluation sandbox")
    return [
        "docker", "run", "--rm", "--pull", "never",
        "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only", "--user", "65534:65534",
        "--pids-limit", "64", "--memory", "1g", "--cpus", "1.0",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m,mode=1777",
        "--env", "HOME=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONPATH=/workspace/src:/workspace",
        "--mount", f"type=bind,source={work},target=/workspace,readonly",
        "--workdir", "/workspace", image
    ] + cmd


def run_in_docker(task_work_dir: Path, cmd: list, python_version: str, timeout_sec: int = 60) -> tuple:
    """Use only prebuilt digest-pinned images; refuse implicit downloads/runs."""
    if not re.fullmatch(r"3\\.(9|10|11)", python_version):
        raise ValueError("Unsupported Python interpreter profile")
    key = "PAPER_EVAL_IMAGE_PY" + python_version.replace(".", "_")
    image = os.environ.get(key, "")
    docker_cmd = build_safe_docker_command(task_work_dir, cmd, image)

    try:
        res = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout_sec)
        return res.returncode, res.stdout, res.stderr, False
    except subprocess.TimeoutExpired:
        # The Docker daemon may retain a running container when its CLI is killed.
        # Do not claim isolation teardown is complete until independently verified.
        return -1, "", f"Container CLI timed out after {timeout_sec}s; verify daemon teardown", True

def verified_pytest_pass_count(exit_code: int, output: str) -> int:
    """Require successful execution AND at least one explicit passed test.

    This avoids scoring an all-skipped/no-tests-collected run as success.
    """
    if exit_code != 0:
        return 0
    matches = re.findall(r"(?<![A-Za-z])([0-9]+)\s+passed\b", output)
    return int(matches[-1]) if matches else 0


def evaluate_patch_on_task(instance_id: str, candidate_output: str, run_id: str = "eval") -> dict:
    """
    Evaluates candidate model output on an isolated task clone.
    """
    assert instance_id in TASKS_MAP, f"Unknown task: {instance_id}"
    spec = TASKS_MAP[instance_id]
    
    # Run labels are not trusted as directory components.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", run_id):
        raise ValueError("Invalid run_id: must be 1..48 ASCII letters, digits, _ or -")

    task_work = WORK_BASE / f"{instance_id}_{run_id}"
    if task_work.exists():
        shutil.rmtree(task_work)
    task_work.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Checkout repo at base_commit
        checkout_cmd = [
            "git", f"--git-dir={spec['repo_bare']}", f"--work-tree={task_work}",
            "checkout", "-f", spec["base_commit"], "."
        ]
        subprocess.run(checkout_cmd, check=True, capture_output=True)

        # 2. Runtime dependencies must be baked into a prebuilt digest-pinned
        # image of the matching Python version; never copy host virtualenvs.
        python_bin = "python"

        # 3. Apply test patch
        test_patch_path = ARCHIVE_DIR / instance_id / "test_patch.diff"
        res_test_patch = subprocess.run(
            ["patch", "-p1", "-d", str(task_work)],
            input=test_patch_path.read_bytes(),
            capture_output=True
        )
        assert res_test_patch.returncode == 0, f"Failed applying test patch: {res_test_patch.stderr.decode()}"

        # 4. Extract proposed candidate code
        candidate_code, code_type = extract_candidate_code(candidate_output)
        if not candidate_code:
            return {
                "instance_id": instance_id,
                "verdict": "FAILED_F2P",
                "failure_reason": "EMPTY_PROPOSED_CODE",
                "f2p_pass": False,
                "p2p_pass": False,
                "code_type": code_type
            }

        # Preflight syntax check for python code
        if code_type == "python":
            valid_syntax, syntax_err = check_python_syntax(candidate_code)
            if not valid_syntax and "NO_FUNCTION" not in syntax_err:
                return {
                    "instance_id": instance_id,
                    "verdict": "SYNTAX_ERROR",
                    "failure_reason": syntax_err,
                    "f2p_pass": False,
                    "p2p_pass": False,
                    "code_type": code_type
                }

        # 5. Apply candidate patch to target file
        applied_ok, apply_msg = apply_candidate_to_repo(task_work, spec["target_file"], candidate_code, code_type)
        if not applied_ok:
            # Check if failure was syntax error during splice
            if "SYNTAX_ERROR" in apply_msg:
                return {
                    "instance_id": instance_id,
                    "verdict": "SYNTAX_ERROR",
                    "failure_reason": apply_msg,
                    "f2p_pass": False,
                    "p2p_pass": False,
                    "code_type": code_type
                }
            return {
                "instance_id": instance_id,
                "verdict": "PATCH_APPLY_ERROR",
                "failure_reason": apply_msg,
                "f2p_pass": False,
                "p2p_pass": False,
                "code_type": code_type
            }

        # 6. Run F2P tests in Docker sandbox
        # Select exact frozen F2P node IDs, not a broad -k expression.
        f2p_cmd = [python_bin, "-m", "pytest"] + spec["f2p_tests"] + [
            "-v", "-p", "no:cacheprovider"
        ]
        f2p_code, f2p_out, f2p_err, f2p_timed_out = run_in_docker(
            task_work, f2p_cmd, spec["python_version"], timeout_sec=45
        )
        
        if f2p_timed_out:
            return {
                "instance_id": instance_id,
                "verdict": "TIMEOUT",
                "stage": "F2P",
                "f2p_pass": False,
                "p2p_pass": False
            }

        f2p_passed_count = verified_pytest_pass_count(f2p_code, f2p_out)
        f2p_pass = f2p_passed_count >= len(spec["f2p_tests"])
        if not f2p_pass:
            return {
                "instance_id": instance_id,
                "verdict": "FAILED_F2P",
                "f2p_exit_code": f2p_code,
                "f2p_output": f2p_out[:500] if f2p_out else f2p_err[:500],
                "f2p_pass": False,
                "p2p_pass": False
            }

        # 7. Run P2P regression tests in Docker sandbox
        # Explicitly remove F2P cases from the regression subset.
        reg_cmd = [python_bin, "-m", "pytest"] + spec["regression_args"] + [
            "--deselect=" + nodeid for nodeid in spec["f2p_tests"]
        ] + ["-q", "-p", "no:cacheprovider"]
        reg_code, reg_out, reg_err, reg_timed_out = run_in_docker(
            task_work, reg_cmd, spec["python_version"], timeout_sec=45
        )

        if reg_timed_out:
            return {
                "instance_id": instance_id,
                "verdict": "TIMEOUT",
                "stage": "P2P_REGRESSION",
                "f2p_pass": True,
                "p2p_pass": False
            }

        p2p_passed_count = verified_pytest_pass_count(reg_code, reg_out)
        p2p_pass = p2p_passed_count > 0
        if not p2p_pass:
            return {
                "instance_id": instance_id,
                "verdict": "REGRESSION",
                "f2p_pass": True,
                "p2p_pass": False,
                "regression_output": reg_out[:500] if reg_out else reg_err[:500]
            }

        # Passed both F2P and P2P!
        return {
            "instance_id": instance_id,
            "verdict": "RESOLVED",
            "f2p_pass": True,
            "p2p_pass": True,
            "apply_status": apply_msg
        }

    finally:
        # Cleanup ephemeral run dir
        if task_work.exists():
            shutil.rmtree(task_work)

def run_evaluator_validation_controls() -> list:
    """
    Executes mandatory validation controls across real repositories:
    1. Positive Controls: Reference Gold Patches on ALL 5 tasks -> Must return RESOLVED.
    2. Negative Controls: Base unmodified code on ALL 5 tasks -> Must return FAILED_F2P.
    3. Malformed Control: Code with invalid Python syntax -> Must return SYNTAX_ERROR.
    4. Deliberate Regression Control: Code breaking another test -> Must return REGRESSION.
    """
    print("\n" + "="*80)
    print("[*] Running Comprehensive Evaluator Pre-Flight Validation Controls...")
    print("="*80)

    controls = []

    # 1. POSITIVE CONTROLS: Gold patches for all 5 tasks
    print("\n--- 1. POSITIVE CONTROLS (Gold Patch -> RESOLVED) across all 5 tasks ---")
    for task_id in TASKS_MAP:
        print(f"[*] Testing Positive Control on {task_id}...")
        gold_patch_text = (ARCHIVE_DIR / task_id / "gold_patch.diff").read_text()
        pos_res = evaluate_patch_on_task(task_id, f"PROPOSED_CODE:\n```diff\n{gold_patch_text}\n```", run_id="pos_ctrl")
        print(f"  Result: {pos_res['verdict']} (expected RESOLVED, F2P={pos_res.get('f2p_pass')}, P2P={pos_res.get('p2p_pass')})")
        assert pos_res["verdict"] == "RESOLVED", f"Positive control failed on {task_id}: {pos_res}"
        controls.append({
            "control_type": "POSITIVE_CONTROL_GOLD_PATCH",
            "instance_id": task_id,
            "expected_verdict": "RESOLVED",
            "actual_verdict": pos_res["verdict"],
            "f2p_pass": pos_res.get("f2p_pass"),
            "p2p_pass": pos_res.get("p2p_pass"),
            "passed": pos_res["verdict"] == "RESOLVED"
        })

    # 2. NEGATIVE CONTROLS: Unchanged base source across all 5 tasks
    print("\n--- 2. NEGATIVE CONTROLS (Unmodified Base Code -> FAILED_F2P) across all 5 tasks ---")
    for task_id, spec in TASKS_MAP.items():
        print(f"[*] Testing Negative Control on {task_id}...")
        base_src = subprocess.run(
            ["git", f"--git-dir={spec['repo_bare']}", "show", f"{spec['base_commit']}:{spec['target_file']}"],
            capture_output=True, text=True, check=True
        ).stdout
        neg_res = evaluate_patch_on_task(task_id, f"PROPOSED_CODE:\n```python\n{base_src}\n```", run_id="neg_ctrl")
        print(f"  Result: {neg_res['verdict']} (expected FAILED_F2P, F2P={neg_res.get('f2p_pass')})")
        assert neg_res["verdict"] == "FAILED_F2P", f"Negative control failed on {task_id}: {neg_res}"
        controls.append({
            "control_type": "NEGATIVE_CONTROL_UNCHANGED_BASE",
            "instance_id": task_id,
            "expected_verdict": "FAILED_F2P",
            "actual_verdict": neg_res["verdict"],
            "f2p_pass": neg_res.get("f2p_pass"),
            "p2p_pass": neg_res.get("p2p_pass"),
            "passed": neg_res["verdict"] == "FAILED_F2P"
        })

    # 3. MALFORMED CONTROL: Syntax error on pallets__flask-4992
    print("\n--- 3. MALFORMED CONTROL (Syntax error -> SYNTAX_ERROR) ---")
    malformed_code = "PROPOSED_CODE:\n```python\ndef from_file(::: broken syntax !!\n```"
    mal_res = evaluate_patch_on_task("pallets__flask-4992", malformed_code, run_id="mal_ctrl")
    print(f"  Result: {mal_res['verdict']} (expected SYNTAX_ERROR)")
    assert mal_res["verdict"] == "SYNTAX_ERROR", f"Malformed control failed: {mal_res}"
    controls.append({
        "control_type": "MALFORMED_CONTROL_SYNTAX_ERROR",
        "instance_id": "pallets__flask-4992",
        "expected_verdict": "SYNTAX_ERROR",
        "actual_verdict": mal_res["verdict"],
        "passed": mal_res["verdict"] == "SYNTAX_ERROR"
    })

    # 4. DELIBERATE REGRESSION CONTROL: Breaks existing Blueprint test on pallets__flask-4045
    print("\n--- 4. DELIBERATE REGRESSION CONTROL (F2P passes, P2P fails -> REGRESSION) ---")
    base_file = UPSTREAM_CACHE / "flask.git"
    base_source = subprocess.run(
        ["git", f"--git-dir={base_file}", "show", "d8c37f43724cd9fb0870f77877b7c4c7e38a19e0:src/flask/blueprints.py"],
        capture_output=True, text=True, check=True
    ).stdout

    # Apply gold fix + deliberate regression on endpoint 'bar' (tested in test_route_decorator_custom_endpoint)
    gold_applied = base_source.replace(
        "        self.name = name\n        self.url_prefix = url_prefix",
        "        if '.' in name:\n            raise ValueError(\"'name' may not contain a dot '.' character.\")\n\n        self.name = name\n        self.url_prefix = url_prefix"
    ).replace(
        '        if endpoint:\n            assert "." not in endpoint, "Blueprint endpoints should not contain dots"\n        if view_func and hasattr(view_func, "__name__"):\n            assert (\n                "." not in view_func.__name__\n            ), "Blueprint view function name should not contain dots"',
        '        if endpoint and "." in endpoint:\n            raise ValueError("\'endpoint\' may not contain a dot \'.\' character.")\n\n        if view_func and hasattr(view_func, "__name__") and "." in view_func.__name__:\n            raise ValueError("\'view_func\' name may not contain a dot \'.\' character.")'
    )
    reg_content = gold_applied.replace(
        "self.record(lambda s: s.add_url_rule(rule, endpoint, view_func, **options))",
        "if endpoint == 'bar':\n            raise RuntimeError('DELIBERATE_REGRESSION_TRIGGERED')\n        self.record(lambda s: s.add_url_rule(rule, endpoint, view_func, **options))"
    )

    reg_res = evaluate_patch_on_task("pallets__flask-4045", f"PROPOSED_CODE:\n```python\n{reg_content}\n```", run_id="reg_ctrl")
    print(f"  Result: {reg_res['verdict']} (expected REGRESSION)")
    assert reg_res["verdict"] == "REGRESSION", f"Deliberate regression failed: {reg_res}"
    controls.append({
        "control_type": "DELIBERATE_REGRESSION_CONTROL",
        "instance_id": "pallets__flask-4045",
        "expected_verdict": "REGRESSION",
        "actual_verdict": reg_res["verdict"],
        "passed": reg_res["verdict"] == "REGRESSION"
    })

    # Save control validation report
    ctrl_file = ARCHIVE_DIR / "evaluator_control_validation.json"
    ctrl_file.write_text(json.dumps(controls, indent=2), encoding="utf-8")
    print(f"\n[✓] All {len(controls)} Evaluator Controls Passed! Saved to {ctrl_file.name}")
    return controls

def main():
    run_evaluator_validation_controls()

if __name__ == "__main__":
    main()
