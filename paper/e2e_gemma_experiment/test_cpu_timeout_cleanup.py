#!/usr/bin/env python3
"""CPU-only tests of fail-closed Docker timeout teardown, using mocks, not Docker."""
import ast
import os
import re
import subprocess
import uuid
from pathlib import Path
from unittest import TestCase, main, mock

SOURCE = Path(__file__).with_name("evaluate_real_repo_patches.py")


def load_runner():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_in_docker"]
    if len(matches) != 1:
        raise AssertionError("Expected exactly one runner")
    nodes = ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[]))
    ns = {
        "os": os, "re": re, "subprocess": subprocess, "uuid": uuid, "Path": Path,
        "build_safe_docker_command": lambda path, cmd, image, name: [
            "docker", "run", "--name", name, image
        ] + cmd,
    }
    exec(compile(nodes, str(SOURCE), "exec"), ns)
    return ns["run_in_docker"]


class CPUContainerTimeoutCleanup(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = staticmethod(load_runner())

    def run_mock(self, effects, version="3.9"):
        with mock.patch.dict(os.environ, {"PAPER_EVAL_IMAGE_PY3_9": "testimage"}, clear=True):
            with mock.patch.object(subprocess, "run", side_effect=effects) as call:
                result = self.runner(Path("/ignored"), ["python", "-m", "pytest"], version, 7)
                return result, call.call_args_list

    def test_success_does_not_cleanup_other_container(self):
        result, calls = self.run_mock([subprocess.CompletedProcess([], 0, "ok", "")])
        self.assertEqual(result, (0, "ok", "", False))
        self.assertEqual(len(calls), 1)

    def test_timeout_cleans_only_unique_own_container(self):
        timeout = subprocess.TimeoutExpired(["docker", "run"], 7)
        result, calls = self.run_mock([timeout, subprocess.CompletedProcess([], 0, "removed", "")])
        self.assertTrue(result[3])
        self.assertEqual(len(calls), 2)
        name = calls[0].args[0][calls[0].args[0].index("--name") + 1]
        self.assertRegex(name, r"^gemma-paper-cpu-[0-9a-f]{32}$")
        self.assertEqual(calls[1].args[0], ["docker", "rm", "-f", name])

    def test_cleanup_failure_raises(self):
        timeout = subprocess.TimeoutExpired(["docker", "run"], 7)
        with self.assertRaisesRegex(RuntimeError, "may still exist"):
            self.run_mock([timeout, subprocess.CompletedProcess([], 1, "", "permission denied")])

    def test_cleanup_timeout_raises(self):
        timeout = subprocess.TimeoutExpired(["docker", "run"], 7)
        with self.assertRaisesRegex(RuntimeError, "could not be verified"):
            self.run_mock([timeout, subprocess.TimeoutExpired(["docker", "rm"], 15)])

    def test_cleanup_missing_container_acceptable(self):
        timeout = subprocess.TimeoutExpired(["docker", "run"], 7)
        result, _ = self.run_mock([timeout, subprocess.CompletedProcess([], 1, "", "No such container")])
        self.assertTrue(result[3])

    def test_allowed_python_versions(self):
        for version in ("3.9", "3.10", "3.11"):
            with self.subTest(version=version):
                with mock.patch.dict(os.environ, {"PAPER_EVAL_IMAGE_PY" + version.replace(".", "_"): "image"}, clear=True):
                    with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok", "")) as call:
                        result = self.runner(Path("/ignored"), ["python", "-m", "pytest"], version, 5)
                        self.assertEqual(result[0], 0)
                        call.assert_called_once()

    def test_invalid_python_version_rejected_without_docker(self):
        with mock.patch.object(subprocess, "run") as call:
            with self.assertRaises(ValueError):
                self.runner(Path("/ignored"), ["python", "-m", "pytest"], "3.12", 5)
            call.assert_not_called()


if __name__ == "__main__":
    main()
