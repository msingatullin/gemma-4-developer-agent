#!/usr/bin/env python3
import os
import sys
import re
from pathlib import Path

REQUIRED_FILES = [
    "agent.yaml",
    "configs/sampling.yaml",
    "prompts/system.md",
]

ALLOWED_TOOLS = {
    "read_file",
    "edit_file",
    "write_file",
    "run_command",
    "get_status",
    "submit_patch",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
    "agent_tool",
}

EXPECTED_MODEL = "gemma-4-31b-it-qat-w4a16-ct"


def validate_submission(submission_dir: Path) -> bool:
    print(f"=== Validating Submission Directory: {submission_dir} ===")
    errors = []

    # 1. Check required files
    for req in REQUIRED_FILES:
        fp = submission_dir / req
        if not fp.is_file():
            errors.append(f"Missing required file: {req}")

    if errors:
        for err in errors:
            print(f"[FAIL] {err}")
        return False

    # 2. Check agent.yaml
    agent_yaml_path = submission_dir / "agent.yaml"
    content = agent_yaml_path.read_text(encoding="utf-8")

    # Check model
    if f"model: {EXPECTED_MODEL}" not in content:
        errors.append(f"agent.yaml does not declare required model: '{EXPECTED_MODEL}'")

    # Check skills format
    skills_dir = submission_dir / "skills"
    if skills_dir.is_dir():
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir():
                manifest = skill_path / "SKILL.md"
                if not manifest.is_file():
                    errors.append(f"Skill directory '{skill_path.name}' is missing SKILL.md")
                else:
                    m_content = manifest.read_text(encoding="utf-8")
                    if not m_content.startswith("---"):
                        errors.append(f"SKILL.md in '{skill_path.name}' missing YAML frontmatter header (---)")
                    elif f"name: {skill_path.name}" not in m_content:
                        errors.append(f"SKILL.md in '{skill_path.name}' frontmatter must define 'name: {skill_path.name}'")

    if errors:
        for err in errors:
            print(f"[FAIL] {err}")
        return False

    print("✅ All static validation checks passed successfully!")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1]).resolve()
    else:
        base_dir = Path(__file__).resolve().parent.parent / "submission"
    success = validate_submission(base_dir)
    sys.exit(0 if success else 1)
