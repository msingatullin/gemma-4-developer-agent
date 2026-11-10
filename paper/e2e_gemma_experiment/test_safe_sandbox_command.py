#!/usr/bin/env python3
"""CPU-only structural tests; no Docker image or upstream repository needed."""
import ast
from pathlib import Path
import re
import tempfile
import unittest

SOURCE = Path(__file__).with_name("evaluate_real_repo_patches.py")


def load_builder():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    matches = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "build_safe_docker_command"
    ]
    if len(matches) != 1:
        raise AssertionError("Expected exactly one Docker command builder")
    program = ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[]))
    env = {"Path": Path, "re": re}
    exec(compile(program, str(SOURCE), "exec"), env)
    return env["build_safe_docker_command"]


class SandboxCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = staticmethod(load_builder())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "case"
        self.work.mkdir()
        # Match the evaluator's root ownership boundary, but avoid host dirs.
        self.builder.__globals__["WORK_BASE"] = self.root
        self.image = "local/paper-eval@sha256:" + ("a" * 64)
        self.command = ["python", "-m", "pytest", "tests/test_config.py", "-q"]

    def test_digest_pinned_image_allowed(self):
        cmd = self.builder(self.work, self.command, self.image)
        self.assertEqual(cmd[-1], self.command[-1])
        self.assertIn(self.image, cmd)
        self.assertIn("--pull", cmd)
        self.assertIn("never", cmd)

    def test_local_content_sha256_id_allowed(self):
        image_id = "sha256:" + ("b" * 64)
        cmd = self.builder(self.work, self.command, image_id)
        self.assertIn(image_id, cmd)

    def test_mutable_tag_rejected(self):
        with self.assertRaises(ValueError):
            self.builder(self.work, self.command, "python:3.12-slim")

    def test_missing_image_rejected(self):
        with self.assertRaises(ValueError):
            self.builder(self.work, self.command, "")

    def test_network_disabled(self):
        cmd = self.builder(self.work, self.command, self.image)
        i = cmd.index("--network")
        self.assertEqual(cmd[i + 1], "none")

    def test_read_only_worktree(self):
        cmd = self.builder(self.work, self.command, self.image)
        self.assertIn("--read-only", cmd)
        i = cmd.index("--mount")
        self.assertTrue(cmd[i + 1].endswith("target=/workspace,readonly"))

    def test_no_host_home_mount(self):
        cmd = self.builder(self.work, self.command, self.image)
        joined = " ".join(cmd)
        self.assertNotIn("/home/mikhail", joined)
        self.assertNotIn("/tmp/real_tasks_cpu_eval", joined)

    def test_restrict_capabilities(self):
        cmd = self.builder(self.work, self.command, self.image)
        self.assertIn("no-new-privileges", cmd)
        self.assertIn("ALL", cmd)
        self.assertIn("--pids-limit", cmd)

    def test_reject_non_pytest_command(self):
        with self.assertRaises(ValueError):
            self.builder(self.work, ["sh", "-c", "true"], self.image)

    def test_reject_outside_root(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(ValueError):
                self.builder(Path(other), self.command, self.image)

    def test_reject_symlink_workdir(self):
        link = self.root / "linked"
        link.symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.builder(link, self.command, self.image)


if __name__ == "__main__":
    unittest.main()
