#!/usr/bin/env python3
"""Static preflight validation for Gemma 4 ADK submission directories or ZIPs.

Enforces:
1. Valid agent.yaml declaring supported model and allowed tools.
2. Safe relative !include paths and no root-escaping references or symlinks.
3. eval_config.yaml present with calibrated per-task time/step limits.
4. No curly braces { } in prompt templates (breaks ADK state substitution).
5. sampling.yaml configured with thinking_config.include_thoughts: true.
6. Clean ZIP packaging without path traversal or symlinks.
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


def validate(root: Path) -> list:
    errors = []
    root = root.resolve()

    # 1. Agent configuration
    agent_yaml = root / "agent.yaml"
    if not agent_yaml.is_file():
        return ["Missing agent.yaml at submission root"]

    config_files = {agent_yaml}
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

    # 2. eval_config.yaml verification
    eval_config = root / "eval_config.yaml"
    if not eval_config.is_file():
        errors.append("Missing eval_config.yaml at submission root (causes 12-hour container timeout on Kaggle)")
    else:
        try:
            ev_text = eval_config.read_text(encoding="utf-8")
            m_time = re.search(r"max_time_minutes:\s*(\d+)", ev_text)
            m_calls = re.search(r"max_tool_calls:\s*(\d+)", ev_text)
            m_timeout = re.search(r"timeout_seconds:\s*(\d+)", ev_text)
            if not m_time:
                errors.append("eval_config.yaml: missing 'max_time_minutes'")
            elif int(m_time.group(1)) > 10:
                errors.append(f"eval_config.yaml: max_time_minutes={m_time.group(1)} exceeds 10m safety threshold")
            if not m_calls:
                errors.append("eval_config.yaml: missing 'max_tool_calls'")
            elif int(m_calls.group(1)) > 50:
                errors.append(f"eval_config.yaml: max_tool_calls={m_calls.group(1)} exceeds 50 calls budget")
            if not m_timeout:
                errors.append("eval_config.yaml: missing 'timeout_seconds'")
        except Exception as exc:
            errors.append(f"eval_config.yaml: parse error: {exc}")

    # 3. Prompt template integrity (no curly braces)
    prompts_dir = root / "prompts"
    if prompts_dir.is_dir():
        for pfile in prompts_dir.rglob("*.md"):
            try:
                ptext = pfile.read_text(encoding="utf-8")
                if "{" in ptext or "}" in ptext:
                    errors.append(f"{pfile.relative_to(root)} contains curly braces '{{' or '}}' (breaks ADK templating)")
            except Exception as exc:
                errors.append(f"{pfile.relative_to(root)}: unreadable: {exc}")

    # 4. sampling.yaml check
    sampling_yaml = root / "configs" / "sampling.yaml"
    if sampling_yaml.is_file():
        try:
            stext = sampling_yaml.read_text(encoding="utf-8")
            if "include_thoughts: false" in stext:
                errors.append("sampling.yaml has include_thoughts: false (suppresses reasoning parser on Gemma 4 Thinking)")
        except Exception as exc:
            errors.append(f"sampling.yaml: unreadable: {exc}")

    # 5. Skills verification
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

    # 6. Symlink prohibition
    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"Symlink not allowed: {path.relative_to(root)}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate Gemma 4 submission directory or zip")
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
    print("PASS: static submission checks passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
