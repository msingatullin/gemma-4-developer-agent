#!/usr/bin/env python3
"""CPU-only pytest scoring contract tests, no Docker/upstream/model calls."""
import ast
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).with_name("evaluate_real_repo_patches.py")


def load_counter():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "verified_pytest_pass_count"]
    if len(nodes) != 1:
        raise AssertionError("Expected exactly one pytest pass counter")
    mod = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    scope = {"re": re}
    exec(compile(mod, str(SOURCE), "exec"), scope)
    return scope["verified_pytest_pass_count"]


class PytestCountContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.count = staticmethod(load_counter())

    def test_normal_pass(self):
        self.assertEqual(self.count(0, "================= 2 passed in 0.3s ================="), 2)

    def test_failed_exit_cannot_pass(self):
        self.assertEqual(self.count(1, "1 failed, 2 passed in 0.3s"), 0)

    def test_zero_selected(self):
        self.assertEqual(self.count(5, "no tests ran in 0.02s"), 0)

    def test_all_skipped(self):
        self.assertEqual(self.count(0, "3 skipped in 0.3s"), 0)

    def test_empty_output(self):
        self.assertEqual(self.count(0, ""), 0)

    def test_xfailed_does_not_count(self):
        self.assertEqual(self.count(0, "2 xfailed in 0.3s"), 0)

    def test_partial_skip(self):
        self.assertEqual(self.count(0, "1 passed, 3 skipped in 0.3s"), 1)

    def test_collection_error(self):
        self.assertEqual(self.count(2, "ERROR collecting tests; 3 passed"), 0)


if __name__ == "__main__":
    unittest.main()
