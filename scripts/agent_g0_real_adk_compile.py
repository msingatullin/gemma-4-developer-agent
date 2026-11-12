#!/usr/bin/env python3
"""CPU-only real organizer adk_submission.compile_submission smoke.

Full Google ADK imports are used; registry model and tools are nonexecuting stubs.
DOES NOT send a model request or invoke an agent tool or Kaggle submit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from importlib import metadata

from adk_submission import (
    compile_submission, ModelRegistry, ToolRegistry, CallbackRegistry,
    SubmissionLimits, GenerationConstraints, NumericRange,
)
from google.adk.agents.base_agent import BaseAgent

OFFICIAL_WHEELS = {
    "adk_submission-0.2.13-py3-none-any.whl": "f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d",
    "google_adk-1.36.1-py3-none-any.whl": "1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0",
}


def blocked(*args, **kwargs):
    raise RuntimeError("G0-NATIVE-COMPILE-002 forbids tool execution.")


def run_command(command: str) -> str:
    """Nonexecuting dry-run stand-in for run_command."""
    return blocked(command)


def read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Nonexecuting dry-run stand-in for read_file."""
    return blocked(filepath, start_line, end_line)


def edit_file(filepath: str, old_string: str, new_string: str) -> str:
    """Nonexecuting dry-run stand-in for edit_file."""
    return blocked(filepath, old_string, new_string)


def write_file(filepath: str, content: str) -> str:
    """Nonexecuting dry-run stand-in for write_file."""
    return blocked(filepath, content)


def get_status() -> str:
    """Nonexecuting dry-run stand-in for get_status."""
    return blocked()


def submit_patch() -> str:
    """Nonexecuting dry-run stand-in for submit_patch."""
    return blocked()


TOOL_MAP = {fn.__name__: fn for fn in (
    run_command, read_file, edit_file, write_file, get_status, submit_patch,
)}


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_inputs(wheels: Path) -> None:
    for filename, digest in OFFICIAL_WHEELS.items():
        p = wheels / filename
        if hash_file(p) != digest:
            raise RuntimeError(f"Organizer wheel SHA mismatch: {filename}")
    for dist, ver in (("adk-submission", "0.2.13"), ("google-adk", "1.36.1")):
        if metadata.version(dist) != ver:
            raise RuntimeError(f"Expected {dist}=={ver}")


def make_limits():
    limits = SubmissionLimits(
        max_total_size_bytes=3 * 1024**3,
        max_yaml_size_bytes=50 * 1024**2,
        max_skill_size_bytes=50 * 1024**2,
        max_file_count=10_000,
        max_yaml_files=1000,
        max_instruction_chars=1_000_000,
        max_total_instruction_chars=10_000_000,
        max_agents=500,
        max_sub_agent_depth=50,
        max_skills=1000,
        max_loop_iterations=500,
        allowed_file_extensions=frozenset({".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}),
        adapter_extensions=frozenset({".safetensors"}),
    )
    constraints = GenerationConstraints(
        allowed_fields=None,
        max_output_tokens=NumericRange(1, 32768),
        thinking_budget=NumericRange(0, 32768),
        defaults={
            "max_output_tokens": 16384,
            "thinking_config": {"thinking_budget": 4096},
        },
    )
    return limits, constraints


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wheels", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--submission", action="append", nargs=2, metavar=("NAME", "PATH"), required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError("Refusing to overwrite completed prior run")
    validate_inputs(a.wheels)
    limits, constraints = make_limits()
    report = {
        "experiment": "G0-NATIVE-COMPILE-002",
        "organizer_wheelhouse_version": 31,
        "wheels_sha256": OFFICIAL_WHEELS,
        "compiler": "REAL organizer adk_submission.compile_submission",
        "google_adk_version": metadata.version("google-adk"),
        "model_registry": "synthetic alias mapping; no serving",
        "tool_registry": "six explicitly named nonexecuting throwing stubs; not real SwegemmaContext",
        "model_inference": "NONE",
        "kaggle_submission": "NONE",
        "native_swegemma_task_runner": "NOT RUN",
        "cases": [],
    }
    for name, path in a.submission:
        source = Path(path).resolve()
        r = {"case": name, "input_dir": str(source)}
        try:
            if not source.is_dir():
                raise FileNotFoundError(source)
            models = ModelRegistry()
            models.register("gemma-4-e4b-it-qat-w4a16-ct", "gemma-4-e4b-it-qat-w4a16-ct")
            tools = ToolRegistry()
            for key, fn in TOOL_MAP.items():
                tools.register(key, fn)
            compiled = compile_submission(
                submission_dir=source,
                tool_registry=tools,
                model_registry=models,
                callback_registry=CallbackRegistry(),
                limits=limits,
                generation_constraints=constraints,
            )
            if not isinstance(compiled, BaseAgent):
                raise AssertionError(f"Not an ADK BaseAgent: {type(compiled)!r}")
            m = getattr(compiled, "model", None)
            model_str = m if isinstance(m, str) else type(m).__name__
            tool_objects = getattr(compiled, "tools", ())
            r.update({
                "status": "PASS_REAL_OFFICIAL_ADK_COMPILE_WITH_SYNTHETIC_REGISTRY",
                "agent_class": type(compiled).__name__,
                "model": model_str,
                "instruction_length": len(str(getattr(compiled, "instruction", ""))),
                "registered_tool_objects": len(tool_objects),
                "tool_type_names": [type(x).__name__ for x in tool_objects],
                "skills_declared_in_yaml": "skills:" in (source / "agent.yaml").read_text(),
                "packaged_skills": sorted(str(x.relative_to(source)) for x in source.glob("skills/*/SKILL.md")),
                "compiler_did_not_run_agent": True,
            })
        except Exception as exc:
            r.update({
                "status": "FAIL_REAL_ADK_COMPILE",
                "exception_type": type(exc).__name__,
                "error": str(exc)[:2500],
            })
        report["cases"].append(r)
        print(name, r["status"], r.get("exception_type", ""), r.get("error", "")[:500], flush=True)
    report["count_passed"] = sum(
        x["status"] == "PASS_REAL_OFFICIAL_ADK_COMPILE_WITH_SYNTHETIC_REGISTRY"
        for x in report["cases"]
    )
    a.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("OUTPUT_SHA256", hash_file(a.output))
    print("OUTPUT_PATH", a.output)


if __name__ == "__main__":
    main()
