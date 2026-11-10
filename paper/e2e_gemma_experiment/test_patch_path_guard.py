#!/usr/bin/env python3
"""Pure-CPU security tests for the model-generated unified-diff allowlist.

Run from repository root:
python -m unittest discover -s paper/e2e_gemma_experiment -p 'test_patch_path_guard.py' -v

The guarded function is extracted from source via AST, so no Docker,
upstream repositories, model runtime or dependencies are required.
"""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("evaluate_real_repo_patches.py")
TARGET = "src/flask/config.py"


def load_guard():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate_candidate_diff_paths"
    ]
    if len(nodes) != 1:
        raise AssertionError("Expected exactly one validate_candidate_diff_paths")
    mod = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    env = {}
    exec(compile(mod, str(SOURCE), "exec"), env)
    return env["validate_candidate_diff_paths"]


class PatchPathGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = staticmethod(load_guard())

    def diff(self, old="a/" + TARGET, new="b/" + TARGET, extra=""):
        return ("diff --git a/" + TARGET + " b/" + TARGET + "\n"
                "--- " + old + "\n+++ " + new + "\n"
                "@@ -1 +1 @@\n-old\n+new\n" + extra)

    def test_allow_exact_target(self):
        self.assertTrue(self.validate(self.diff(), TARGET)[0])

    def test_deny_modified_tests(self):
        self.assertFalse(self.validate(self.diff(new="b/tests/test_config.py"), TARGET)[0])

    def test_deny_parent_escape(self):
        self.assertFalse(self.validate(self.diff(new="b/../config.py"), TARGET)[0])

    def test_deny_absolute_path(self):
        self.assertFalse(self.validate(self.diff(new="/etc/passwd"), TARGET)[0])

    def test_deny_delete(self):
        self.assertFalse(self.validate(self.diff(new="/dev/null"), TARGET)[0])

    def test_deny_multi_file(self):
        d = self.diff() + "\n--- a/tests/test_config.py\n+++ b/tests/test_config.py\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertFalse(self.validate(d, TARGET)[0])

    def test_deny_rename(self):
        d = self.diff(extra="rename from src/flask/config.py\nrename to tests/test_config.py\n")
        self.assertFalse(self.validate(d, TARGET)[0])

    def test_deny_binary(self):
        self.assertFalse(self.validate(self.diff(extra="GIT binary patch\n"), TARGET)[0])

    def test_deny_missing_hunk(self):
        d = "diff --git a/" + TARGET + " b/" + TARGET + "\n--- a/" + TARGET + "\n+++ b/" + TARGET
        self.assertFalse(self.validate(d, TARGET)[0])

    def test_deny_mismatched_git_header(self):
        d = self.diff().replace("diff --git a/" + TARGET, "diff --git a/tests/test_config.py")
        self.assertFalse(self.validate(d, TARGET)[0])


if __name__ == "__main__":
    unittest.main()
