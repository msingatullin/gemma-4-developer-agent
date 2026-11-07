#!/usr/bin/env python3
"""Static preflight validation for Gemma 4 ADK submission directories or ZIPs.

This is NOT a replacement for the official Kaggle harness compiler.
"""
import argparse
import re
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ALLOWED_MODELS = {
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-12b-it-qat-w4a16-ct",
    "gemma-4-e4b-it-qat-w4a16-ct",
    "gemma-4-e2b-it-qat-w4a16-ct",
}
ALLOWED_TOOLS = {
    "run_command", "read_file", "edit_file", "write_file",
    "get_status", "submit_patch", "get_code_neighbors",
    "search_similar_code", "get_code_subgraph",
}
INCLUDE = re.compile(r"!include\s+([^\s#]+)")
MODEL = re.compile(r"^\s*model:\s*['\"]?([^\s'\"#]+)", re.M)
CONFIG_PATH = re.compile(r"^\s*config_path:\s*['\"]?([^\s'\"#]+)", re.M)
TOOL = re.compile(r"^\s*-\s+([a-z_][a-z_0-9]*)\s*(?::\s*)?$", re.M)


def validate(root):
    errors = []
    root = root.resolve()
    if not (root / "agent.yaml").is_file():
        return ["Missing agent.yaml at submission root"]
    config_files = {root / "agent.yaml"}
    subagents = root / "sub_agents"
    if subagents.exists():
        config_files.update(subagents.glob("*.yaml"))
    chosen_models = set()
    discovered = set()

    def safe_file(base, name, label):
        target = (base / name).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            errors.append(f"{label}: reference escapes submission root: {name}")
            return None
        if not target.is_file():
            errors.append(f"{label}: missing referenced file: {name}")
            return None
        if target.is_symlink():
            errors.append(f"{label}: symlinks are not allowed: {name}")
            return None
        return target

    queue = list(config_files)
    while queue:
        path = queue.pop()
        if path in discovered:
            continue
        discovered.add(path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(root)}: unreadable: {exc}")
            continue
        for model in MODEL.findall(text):
            chosen_models.add(model)
            if model not in ALLOWED_MODELS:
                errors.append(f"{path.relative_to(root)}: disallowed model {model}")
        for include in INCLUDE.findall(text):
            target = safe_file(path.parent, include, str(path.relative_to(root)))
            if target and target.suffix in {".yaml", ".yml"}:
                queue.append(target)
        for ref in CONFIG_PATH.findall(text):
            target = safe_file(path.parent, ref, str(path.relative_to(root)))
            if target:
                queue.append(target)
        for tool in TOOL.findall(text):
            if tool not in ALLOWED_TOOLS and tool != "agent_tool":
                errors.append(f"{path.relative_to(root)}: unknown tool entry {tool}")
    if not chosen_models:
        errors.append("No model declaration found in agent/subagent config")
    if len(chosen_models) > 1:
        errors.append(f"Different base models used across agents: {sorted(chosen_models)}")

    skills = root / "skills"
    if skills.is_dir():
        for skill in sorted(skills.iterdir()):
            if not skill.is_dir():
                continue
            manifest = skill / "SKILL.md"
            if not manifest.is_file():
                errors.append(f"{skill.relative_to(root)}: missing SKILL.md")
                continue
            data = manifest.read_text(encoding="utf-8")
            if not data.startswith("---\n") or not re.search(
                r"^name:\s*['\"]?" + re.escape(skill.name) + r"['\"]?\s*$",
                data.split("---", 2)[1] if data.count("---") >= 2 else "",
                re.M,
            ):
                errors.append(f"{manifest.relative_to(root)}: missing valid YAML frontmatter name")

    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"Symlink not allowed: {path.relative_to(root)}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="submission")
    args = parser.parse_args()
    source = Path(args.source)
    if source.is_file() and source.suffix == ".zip":
        with tempfile.TemporaryDirectory() as temp:
            with zipfile.ZipFile(source) as zf:
                for info in zf.infolist():
                    p = PurePosixPath(info.filename)
                    if p.is_absolute() or ".." in p.parts or "\\" in info.filename:
                        print(f"FAIL: unsafe zip entry: {info.filename}")
                        return 1
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        print(f"FAIL: symlink zip entry: {info.filename}")
                        return 1
                zf.extractall(temp)
            errors = validate(Path(temp))
    elif source.is_dir():
        errors = validate(source)
    else:
        errors = [f"No such directory or ZIP: {source}"]
    for error in errors:
        print("FAIL:", error)
    if errors:
        return 1
    print("PASS: static submission checks (official harness validation still required)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
