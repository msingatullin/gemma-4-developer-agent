#!/usr/bin/env python3
"""
Build 15 reproducible, self-contained software defect tasks from real open-source Python projects.
Each task includes:
- source.py: Buggy implementation
- test_task.py: Reproducing pytest test
- gold_patch.diff: Verified fix patch
- meta.json: Task metadata, target symbol, root cause explanation, expected failure
"""
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

TASKS_DIR = Path(__file__).parent / "tasks"

TASK_SPECS = [
    {
        "id": "task_01_flask_blueprint_dot",
        "repo": "pallets/flask",
        "issue": "Raise error when blueprint name contains a dot (#4045)",
        "target_symbol": "Blueprint.__init__",
        "root_cause": "Blueprint names containing dots cause collision in nested blueprint endpoint resolution.",
        "expected_exception": "ValueError",
        "buggy_code": '''class Blueprint:
    def __init__(self, name: str, import_name: str, url_prefix: str = None):
        self.name = name
        self.import_name = import_name
        self.url_prefix = url_prefix

    def make_endpoint(self, endpoint: str) -> str:
        return f"{self.name}.{endpoint}"
''',
        "test_code": '''import pytest
from source import Blueprint

def test_valid_blueprint():
    bp = Blueprint("admin", __name__)
    assert bp.make_endpoint("login") == "admin.login"

def test_dotted_blueprint_name_not_allowed():
    """Dots in blueprint names must raise ValueError to prevent nesting collisions."""
    for i in range(20):
        print(f"[TRACE_NOISE_{i}] loading blueprint registration context")
    with pytest.raises(ValueError, match="Blueprint names may not contain dots"):
        Blueprint("admin.auth", __name__)
''',
        "fixed_code": '''class Blueprint:
    def __init__(self, name: str, import_name: str, url_prefix: str = None):
        if "." in name:
            raise ValueError(f"Blueprint names may not contain dots: '{name}'")
        self.name = name
        self.import_name = import_name
        self.url_prefix = url_prefix

    def make_endpoint(self, endpoint: str) -> str:
        return f"{self.name}.{endpoint}"
'''
    },
    {
        "id": "task_02_flask_config_mode",
        "repo": "pallets/flask",
        "issue": "Add mode parameter to Config.from_file() (#4992)",
        "target_symbol": "Config.from_file",
        "root_cause": "from_file hardcoded text mode 'r', breaking binary load formats like tomllib or pickle.",
        "expected_exception": "TypeError",
        "buggy_code": '''import json
from pathlib import Path

class Config(dict):
    def from_file(self, filename: str, load_func):
        """Loads configuration from file in text mode only."""
        with open(filename, "r") as f:
            obj = load_func(f)
        if obj:
            self.update(obj)
        return True
''',
        "test_code": '''import pytest
import json
import io
from source import Config

def test_from_file_text_default(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text('{"DEBUG": true}')
    cfg = Config()
    cfg.from_file(str(p), json.load)
    assert cfg["DEBUG"] is True

def test_from_file_binary_mode(tmp_path):
    """Config.from_file must support mode='rb' for binary deserializers."""
    p = tmp_path / "cfg.bin"
    p.write_bytes(b'{"SECRET_KEY": "secure_bytes"}')
    cfg = Config()
    def binary_loader(f):
        data = f.read()
        if not isinstance(data, bytes):
            raise TypeError(f"Expected bytes, got {type(data).__name__}")
        import json
        return json.loads(data.decode())
    
    cfg.from_file(str(p), binary_loader, mode="rb")
    assert cfg["SECRET_KEY"] == "secure_bytes"
''',
        "fixed_code": '''import json
from pathlib import Path

class Config(dict):
    def from_file(self, filename: str, load_func, mode: str = "r"):
        """Loads configuration from file supporting both text and binary modes."""
        with open(filename, mode) as f:
            obj = load_func(f)
        if obj:
            self.update(obj)
        return True
'''
    },
    {
        "id": "task_03_requests_redirect_body",
        "repo": "psf/requests",
        "issue": "Session.resolve_redirects copies original request body on 303 redirect (#1963)",
        "target_symbol": "Session.resolve_redirects",
        "root_cause": "On HTTP 303 See Other, the method should change to GET and the request body must be dropped.",
        "expected_exception": "AssertionError",
        "buggy_code": '''class Response:
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
''',
        "test_code": '''import pytest
from source import Session, Response

def test_redirect_303_strips_body():
    session = Session()
    resp = Response(303, "/new-url")
    for k in range(15):
        print(f"[HTTP_REDIRECT_DEBUG_{k}] status=303 target=/new-url")
    redir = session.resolve_redirects(resp, "POST", b"payload_data")
    assert redir["method"] == "GET", f"Expected GET on 303, got {redir['method']}"
    assert redir["body"] is None, "Body must be stripped on 303 redirect"
''',
        "fixed_code": '''class Response:
    def __init__(self, status_code: int, location: str):
        self.status_code = status_code
        self.headers = {"location": location}

class Session:
    def resolve_redirects(self, resp: Response, req_method: str, req_body: bytes) -> dict:
        """Resolve redirect with HTTP spec compliance."""
        if resp.status_code == 303:
            return {
                "method": "GET",
                "body": None,
                "url": resp.headers.get("location")
            }
        elif resp.status_code in (301, 302, 307):
            return {
                "method": req_method,
                "body": req_body,
                "url": resp.headers.get("location")
            }
        return None
'''
    },
    {
        "id": "task_04_requests_socket_error",
        "repo": "psf/requests",
        "issue": "socket.error not wrapped in requests.ConnectionError (#2148)",
        "target_symbol": "send_http_request",
        "root_cause": "Low-level socket.error escapes abstraction boundary instead of being wrapped in ConnectionError.",
        "expected_exception": "requests.ConnectionError",
        "buggy_code": '''import socket

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
''',
        "test_code": '''import pytest
from source import send_http_request, ConnectionError

def test_socket_error_wrapped():
    """Socket level network failures must raise ConnectionError."""
    for i in range(15):
        print(f"[SOCKET_TRANSPORT_LOG_{i}] attempting connection to unreachable port")
    with pytest.raises(ConnectionError, match="Failed to establish connection"):
        send_http_request("127.0.0.1", 1)
''',
        "fixed_code": '''import socket

class RequestException(Exception):
    pass

class ConnectionError(RequestException):
    pass

def send_http_request(host: str, port: int):
    """Dispatches socket connection wrapping socket.error in ConnectionError."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.001)
    try:
        s.connect((host, port))
    except (socket.error, OSError) as err:
        raise ConnectionError(f"Failed to establish connection to {host}:{port}: {err}") from err
    return b"HTTP/1.1 200 OK"
'''
    },
    {
        "id": "task_05_click_choice_case",
        "repo": "pallets/click",
        "issue": "Support case_sensitive parameter in click.Choice",
        "target_symbol": "Choice.convert",
        "root_cause": "Choice validation only performed exact string lookup, ignoring case_sensitive=False setting.",
        "expected_exception": "ValueError",
        "buggy_code": '''class Choice:
    def __init__(self, choices: list[str], case_sensitive: bool = True):
        self.choices = choices
        self.case_sensitive = case_sensitive

    def convert(self, value: str) -> str:
        if value in self.choices:
            return value
        raise ValueError(f"'{value}' is not one of {self.choices}")
''',
        "test_code": '''import pytest
from source import Choice

def test_choice_exact_match():
    c = Choice(["apple", "banana"])
    assert c.convert("apple") == "apple"

def test_choice_case_insensitive():
    c = Choice(["red", "green", "blue"], case_sensitive=False)
    for i in range(12):
        print(f"[CLICK_PARSER_DIAG_{i}] evaluating token against grammar")
    assert c.convert("RED") == "red"
    assert c.convert("GrEeN") == "green"
''',
        "fixed_code": '''class Choice:
    def __init__(self, choices: list[str], case_sensitive: bool = True):
        self.choices = choices
        self.case_sensitive = case_sensitive

    def convert(self, value: str) -> str:
        if self.case_sensitive:
            if value in self.choices:
                return value
        else:
            lower_map = {c.lower(): c for c in self.choices}
            if value.lower() in lower_map:
                return lower_map[value.lower()]
        raise ValueError(f"'{value}' is not one of {self.choices}")
'''
    },
    {
        "id": "task_06_jinja2_undefined_slice",
        "repo": "pallets/jinja",
        "issue": "StrictUndefined slice operation raises TypeError instead of UndefinedError",
        "target_symbol": "StrictUndefined.__getitem__",
        "root_cause": "Slicing an undefined variable returned empty list instead of failing loudly under strict mode.",
        "expected_exception": "UndefinedError",
        "buggy_code": '''class UndefinedError(Exception):
    pass

class StrictUndefined:
    def __init__(self, name: str):
        self._name = name

    def __getitem__(self, item):
        if isinstance(item, slice):
            return []
        raise UndefinedError(f"'{self._name}' is undefined")
''',
        "test_code": '''import pytest
from source import StrictUndefined, UndefinedError

def test_strict_undefined_slice():
    u = StrictUndefined("items")
    for i in range(18):
        print(f"[JINJA_AST_EVAL_{i}] evaluating AST subscript node")
    with pytest.raises(UndefinedError, match="'items' is undefined"):
        _ = u[:5]
''',
        "fixed_code": '''class UndefinedError(Exception):
    pass

class StrictUndefined:
    def __init__(self, name: str):
        self._name = name

    def __getitem__(self, item):
        raise UndefinedError(f"'{self._name}' is undefined")
'''
    },
    {
        "id": "task_07_urllib3_query_encoding",
        "repo": "urllib3/urllib3",
        "issue": "parse_url normalizes spaces to empty instead of preserving plus signs",
        "target_symbol": "parse_url_query",
        "root_cause": "Query parser replaced '+' unconditionally with space before URL recreation.",
        "expected_exception": "AssertionError",
        "buggy_code": '''def parse_url_query(query: str) -> dict:
    """Parses URL query strings into dictionary."""
    if not query:
        return {}
    params = {}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v.replace("+", " ")
        else:
            params[part] = ""
    return params
''',
        "test_code": '''import pytest
from source import parse_url_query

def test_preserve_plus_in_query():
    """Literal plus signs in query strings must be preserved rather than replaced by spaces."""
    q = "search=c+plus+plus&filter=active"
    for i in range(15):
        print(f"[QUERY_TOKENIZER_{i}] scanning component")
    parsed = parse_url_query(q)
    assert parsed["search"] == "c+plus+plus", f"Expected c+plus+plus, got {parsed['search']}"
    assert parsed["filter"] == "active"
''',
        "fixed_code": '''def parse_url_query(query: str) -> dict:
    """Parses URL query strings without corrupting percent-encoded tokens."""
    if not query:
        return {}
    params = {}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
        else:
            params[part] = ""
    return params
'''
    },
    {
        "id": "task_08_rich_markup_escape",
        "repo": "Textualize/rich",
        "issue": "Markup escape() fails to escape single unclosed brackets",
        "target_symbol": "escape",
        "root_cause": "escape() only replaced balanced tags, leaving unescaped brackets in logging messages.",
        "expected_exception": "AssertionError",
        "buggy_code": '''import re

def escape(text: str) -> str:
    """Escapes markup tags in Rich text."""
    return re.sub(r"\\[([a-z]+)\\]", r"\\[\\1\\]", text)
''',
        "test_code": '''import pytest
from source import escape

def test_escape_isolated_bracket():
    text = "Status: [error] at index [0"
    for i in range(12):
        print(f"[CONSOLE_MARKUP_LOG_{i}] rendering token stream")
    escaped = escape(text)
    assert r"\\[error\\]" in escaped or r"\\[error]" in escaped
    assert r"\\[0" in escaped
''',
        "fixed_code": '''def escape(text: str) -> str:
    """Escapes opening and closing brackets so markup parser treats text as literal."""
    return text.replace("[", r"\\[").replace("]", r"\\]")
'''
    },
    {
        "id": "task_09_pluggy_hook_order",
        "repo": "pytest-dev/pluggy",
        "issue": "Pluggy hook execution order violation when tryfirst and trylast coexist",
        "target_symbol": "HookCaller.execute",
        "root_cause": "Hooks with trylast were appended before standard hooks rather than placed at the very end.",
        "expected_exception": "AssertionError",
        "buggy_code": '''class HookCaller:
    def __init__(self, name: str):
        self.name = name
        self.hooks = []

    def register(self, fn, tryfirst: bool = False, trylast: bool = False):
        self.hooks.append({"fn": fn, "tryfirst": tryfirst, "trylast": trylast})

    def execute(self) -> list:
        # Buggy implementation: preserves FIFO for tryfirst instead of LIFO specification
        first = [h["fn"]() for h in self.hooks if h["tryfirst"]]
        middle = [h["fn"]() for h in self.hooks if not h["tryfirst"] and not h["trylast"]]
        last = [h["fn"]() for h in self.hooks if h["trylast"]]
        return first + middle + last
''',
        "test_code": '''import pytest
from source import HookCaller

def test_hook_order_lifo_for_tryfirst():
    caller = HookCaller("pytest_runtest_protocol")
    caller.register(lambda: "first_1", tryfirst=True)
    caller.register(lambda: "first_2", tryfirst=True)
    caller.register(lambda: "standard")
    
    for i in range(15):
        print(f"[PLUGGY_DISPATCH_DIAG_{i}] running plugin hook wrappers")
    
    res = caller.execute()
    # Pluggy specification: later tryfirst hooks take higher priority (LIFO)
    assert res == ["first_2", "first_1", "standard"], f"Unexpected hook order: {res}"
''',
        "fixed_code": '''class HookCaller:
    def __init__(self, name: str):
        self.name = name
        self.hooks = []

    def register(self, fn, tryfirst: bool = False, trylast: bool = False):
        self.hooks.append({"fn": fn, "tryfirst": tryfirst, "trylast": trylast})

    def execute(self) -> list:
        # Fixed: later tryfirst hooks run first (LIFO order per pluggy spec)
        first = [h["fn"]() for h in reversed(self.hooks) if h["tryfirst"]]
        middle = [h["fn"]() for h in self.hooks if not h["tryfirst"] and not h["trylast"]]
        last = [h["fn"]() for h in self.hooks if h["trylast"]]
        return first + middle + last
'''
    },
    {
        "id": "task_10_marshmallow_empty_str",
        "repo": "marshmallow-code/marshmallow",
        "issue": "String field deserialize converts empty string to None when allow_none=True",
        "target_symbol": "StringField.deserialize",
        "root_cause": "Empty string check was falsy (if not value: return None), overriding explicit empty string.",
        "expected_exception": "AssertionError",
        "buggy_code": '''class StringField:
    def __init__(self, allow_none: bool = False):
        self.allow_none = allow_none

    def deserialize(self, value):
        if not value:
            if self.allow_none:
                return None
            return ""
        return str(value)
''',
        "test_code": '''import pytest
from source import StringField

def test_deserialize_empty_string_retained():
    f = StringField(allow_none=True)
    for i in range(12):
        print(f"[MARSHMALLOW_VALIDATOR_{i}] processing schema payload")
    res = f.deserialize("")
    assert res == "", f"Expected empty string '', got {res!r}"
    assert f.deserialize(None) is None
''',
        "fixed_code": '''class StringField:
    def __init__(self, allow_none: bool = False):
        self.allow_none = allow_none

    def deserialize(self, value):
        if value is None:
            if self.allow_none:
                return None
            raise ValueError("Field cannot be null")
        return str(value)
'''
    },
    {
        "id": "task_11_pydantic_strip_whitespace",
        "repo": "pydantic/pydantic",
        "issue": "str_strip_whitespace=True drops None validation error",
        "target_symbol": "validate_str",
        "root_cause": "Attribute error when calling .strip() on None input before type check.",
        "expected_exception": "TypeError",
        "buggy_code": '''def validate_str(value, strip_whitespace: bool = True):
    if strip_whitespace:
        value = value.strip()
    if not isinstance(value, str):
        raise TypeError("Input must be a valid string")
    return value
''',
        "test_code": '''import pytest
from source import validate_str

def test_validate_str_with_none():
    for i in range(12):
        print(f"[PYDANTIC_CORE_VALIDATOR_{i}] resolving type constraint")
    with pytest.raises(TypeError, match="Input must be a valid string"):
        validate_str(None, strip_whitespace=True)
''',
        "fixed_code": '''def validate_str(value, strip_whitespace: bool = True):
    if not isinstance(value, str):
        raise TypeError("Input must be a valid string")
    if strip_whitespace:
        value = value.strip()
    return value
'''
    },
    {
        "id": "task_12_attrs_frozen_repr",
        "repo": "python-attrs/attrs",
        "issue": "Frozen dataclass __setattr__ raises AttributeError instead of FrozenInstanceError",
        "target_symbol": "FrozenModel.__setattr__",
        "root_cause": "Improper exception type raised when setting attributes on frozen model.",
        "expected_exception": "FrozenInstanceError",
        "buggy_code": '''class FrozenInstanceError(Exception):
    pass

class FrozenModel:
    def __init__(self, **kwargs):
        self.__dict__["_frozen"] = False
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.__dict__["_frozen"] = True

    def __setattr__(self, key, value):
        if self.__dict__.get("_frozen"):
            raise AttributeError(f"Cannot assign to frozen model: {key}")
        self.__dict__[key] = value
''',
        "test_code": '''import pytest
from source import FrozenModel, FrozenInstanceError

def test_frozen_mutation_error():
    m = FrozenModel(x=10, y=20)
    for i in range(15):
        print(f"[ATTRS_DESCRIPTOR_GUARD_{i}] inspecting attribute setter")
    with pytest.raises(FrozenInstanceError, match="Cannot assign to frozen model"):
        m.x = 99
''',
        "fixed_code": '''class FrozenInstanceError(Exception):
    pass

class FrozenModel:
    def __init__(self, **kwargs):
        self.__dict__["_frozen"] = False
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.__dict__["_frozen"] = True

    def __setattr__(self, key, value):
        if self.__dict__.get("_frozen"):
            raise FrozenInstanceError(f"Cannot assign to frozen model: {key}")
        self.__dict__[key] = value
'''
    },
    {
        "id": "task_13_itsdangerous_expired",
        "repo": "pallets/itsdangerous",
        "issue": "TimestampSigner raises BadTimeSignature instead of SignatureExpired",
        "target_symbol": "TimestampSigner.unsign",
        "root_cause": "Expired tokens raised generic BadTimeSignature instead of specific SignatureExpired.",
        "expected_exception": "SignatureExpired",
        "buggy_code": '''import time

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
''',
        "test_code": '''import pytest
import time
from source import TimestampSigner, SignatureExpired

def test_expired_signature_distinction():
    signer = TimestampSigner(max_age=10)
    for i in range(15):
        print(f"[SECURITY_SIGNATURE_VERIFIER_{i}] validating crypto timestamp")
    old_ts = time.time() - 100
    with pytest.raises(SignatureExpired, match="Signature has expired"):
        signer.unsign("valid_payload", old_ts)
''',
        "fixed_code": '''import time

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
            raise SignatureExpired(f"Signature has expired by {age - self.max_age:.1f}s")
        return token
'''
    },
    {
        "id": "task_14_werkzeug_cookie_quote",
        "repo": "pallets/werkzeug",
        "issue": "dump_cookie omits quotes when cookie value contains commas",
        "target_symbol": "dump_cookie",
        "root_cause": "Commas were not included in the quote-trigger character set for RFC 6265 cookie dumping.",
        "expected_exception": "AssertionError",
        "buggy_code": '''def dump_cookie(key: str, value: str) -> str:
    """Serializes cookie key-value pair."""
    # Bug: only quotes when space is present, ignores comma and semicolon
    if " " in value:
        value = f'"{value}"'
    return f"{key}={value}; Path=/"
''',
        "test_code": '''import pytest
from source import dump_cookie

def test_dump_cookie_quotes_commas():
    for i in range(12):
        print(f"[HTTP_COOKIE_SERIALIZER_{i}] encoding header string")
    res = dump_cookie("session_tags", "admin,user,editor")
    assert res == 'session_tags="admin,user,editor"; Path=/', f"Expected quoted value, got {res}"
''',
        "fixed_code": '''def dump_cookie(key: str, value: str) -> str:
    """Serializes cookie key-value pair quoting commas and semicolons."""
    if any(c in value for c in [" ", ",", ";"]):
        value = f'"{value}"'
    return f"{key}={value}; Path=/"
'''
    },
    {
        "id": "task_15_pytest_approx_none",
        "repo": "pytest-dev/pytest",
        "issue": "approx() comparison with None raises TypeError instead of returning False (#5221)",
        "target_symbol": "approx_compare",
        "root_cause": "abs(actual - expected) executed directly without checking if operand is None, crashing with TypeError.",
        "expected_exception": "TypeError",
        "buggy_code": '''def approx_compare(actual, expected: float, tol: float = 1e-6) -> bool:
    """Compares numeric values within relative tolerance."""
    return abs(actual - expected) <= tol
''',
        "test_code": '''import pytest
from source import approx_compare

def test_approx_none_safe_comparison():
    for i in range(12):
        print(f"[FLOAT_PRECISION_ANALYZER_{i}] computing tolerance boundaries")
    # Comparison of None against float must safely return False without TypeError
    assert approx_compare(None, 1.0) is False
    assert approx_compare(1.0, None) is False
''',
        "fixed_code": '''def approx_compare(actual, expected: float, tol: float = 1e-6) -> bool:
    """Compares numeric values returning False safely if operand is None."""
    if actual is None or expected is None:
        return False
    return abs(actual - expected) <= tol
'''
    }
]

def main():
    print(f"Creating {len(TASK_SPECS)} tasks in {TASKS_DIR}...")
    manifest = []
    
    for spec in TASK_SPECS:
        tid = spec["id"]
        tdir = TASKS_DIR / tid
        tdir.mkdir(parents=True, exist_ok=True)
        
        # Write files
        source_p = tdir / "source.py"
        test_p = tdir / "test_task.py"
        source_p.write_text(spec["buggy_code"], encoding="utf-8")
        test_p.write_text(spec["test_code"], encoding="utf-8")
        
        # Generate diff
        import difflib
        diff = difflib.unified_diff(
            spec["buggy_code"].splitlines(keepends=True),
            spec["fixed_code"].splitlines(keepends=True),
            fromfile="a/source.py",
            tofile="b/source.py"
        )
        gold_patch = "".join(diff)
        (tdir / "gold_patch.diff").write_text(gold_patch, encoding="utf-8")
        
        # Meta
        meta = {
            "id": tid,
            "repo": spec["repo"],
            "issue": spec["issue"],
            "target_symbol": spec["target_symbol"],
            "root_cause": spec["root_cause"],
            "expected_exception": spec["expected_exception"]
        }
        (tdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        manifest.append(meta)
        
        # Verify reproduction: pytest should FAIL on buggy code
        res_fail = subprocess.run([sys.executable, "-m", "pytest", str(test_p), "-q"], cwd=tdir, capture_output=True, text=True)
        assert res_fail.returncode != 0, f"Task {tid} did not fail on buggy source!"
        
        # Verify fix: applying fixed code should PASS
        source_p.write_text(spec["fixed_code"], encoding="utf-8")
        res_pass = subprocess.run([sys.executable, "-m", "pytest", str(test_p), "-q"], cwd=tdir, capture_output=True, text=True)
        assert res_pass.returncode == 0, f"Task {tid} did not pass on fixed source! Stderr: {res_pass.stderr}\nStdout: {res_pass.stdout}"
        
        # Reset to buggy code
        source_p.write_text(spec["buggy_code"], encoding="utf-8")
        print(f"  [VERIFIED] {tid} -> FAIL on buggy, PASS on gold patch.")

    manifest_p = Path(__file__).parent / "task_manifest.json"
    manifest_p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nSuccessfully built and verified all {len(TASK_SPECS)} tasks! Manifest saved to {manifest_p}")

if __name__ == "__main__":
    main()
