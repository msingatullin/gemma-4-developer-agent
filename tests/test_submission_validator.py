"""Regression tests for the static submission preflight. Run: python -m unittest discover -s tests -p 'test_submission_validator.py' -v"""
import importlib.util
import sys
from unittest.mock import patch
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "submission_validator", REPO / "tools" / "validate_submission.py"
)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class SubmissionValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "prompts").mkdir()
        (self.root / "configs").mkdir()
        (self.root / "sub_agents").mkdir()
        (self.root / "agent.yaml").write_text(
            "name: coder\nmodel: gemma-4-31b-it-qat-w4a16-ct\n"
            "instruction: !include prompts/system.md\n"
            "generate_content_config: !include configs/sampling.yaml\n"
            "tools:\n  - read_file\n  - submit_patch\n"
            "  - agent_tool:\n      config_path: sub_agents/analyzer.yaml\n",
            encoding="utf-8",
        )
        (self.root / "prompts" / "system.md").write_text(
            "Fix the issue.\n", encoding="utf-8"
        )
        (self.root / "configs" / "sampling.yaml").write_text(
            "temperature: 0.15\n", encoding="utf-8"
        )
        (self.root / "sub_agents" / "analyzer.yaml").write_text(
            "name: analyzer\nmodel: gemma-4-31b-it-qat-w4a16-ct\n"
            "instruction: !include ../prompts/system.md\n"
            "tools:\n  - read_file\n",
            encoding="utf-8",
        )

    def assert_invalid(self, expected):
        errors = validator.validate(self.root)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_dual_agent(self):
        self.assertEqual(validator.validate(self.root), [])

    def test_missing_root_config(self):
        (self.root / "agent.yaml").unlink()
        self.assert_invalid("Missing agent.yaml")

    def test_missing_include(self):
        (self.root / "prompts" / "system.md").unlink()
        self.assert_invalid("missing referenced file")

    def test_parent_reference_within_root_is_allowed(self):
        self.assertEqual(validator.validate(self.root), [])

    def test_path_escape(self):
        config = self.root / "sub_agents" / "analyzer.yaml"
        config.write_text(
            "model: gemma-4-31b-it-qat-w4a16-ct\n"
            "instruction: !include ../../outside.md\n",
            encoding="utf-8",
        )
        self.assert_invalid("escapes submission root")

    def test_mixed_models_rejected(self):
        config = self.root / "sub_agents" / "analyzer.yaml"
        config.write_text(
            "model: gemma-4-e4b-it-qat-w4a16-ct\n",
            encoding="utf-8",
        )
        self.assert_invalid("Different base models")

    def test_unknown_tool_rejected(self):
        config = self.root / "sub_agents" / "analyzer.yaml"
        config.write_text(
            "model: gemma-4-31b-it-qat-w4a16-ct\n"
            "tools:\n  - internet_search\n",
            encoding="utf-8",
        )
        self.assert_invalid("unknown tool entry")

    def test_skill_requires_manifest(self):
        (self.root / "skills" / "ast_indexer").mkdir(parents=True)
        self.assert_invalid("missing SKILL.md")

    def test_zip_path_traversal_rejected(self):
        archive = self.root / "malicious.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../escape", "bad")
        with patch.object(sys, "argv", ["validate_submission.py", str(archive)]):
            self.assertEqual(validator.main(), 1)

    def test_zip_valid_archive_round_trip(self):
        archive = self.root / "valid.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in self.root.rglob("*"):
                if path.is_file() and path != archive:
                    zf.write(path, path.relative_to(self.root))
        with tempfile.TemporaryDirectory() as target:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(target)
            self.assertEqual(validator.validate(Path(target)), [])


if __name__ == "__main__":
    unittest.main()
