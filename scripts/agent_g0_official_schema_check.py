#!/usr/bin/env python3
"""Run the organizer's REAL adk-submission directory/YAML/root-schema submodules.

This intentionally DOES NOT run compile_submission or Gemma inference. Since
google-adk has extensive transitive host/GPU dependencies, structural-only
modules are imported through a minimal namespace package with the original
installed module files, bypassing only adk_submission/__init__.py's eager
compiler import. Requires organizer adk-submission==0.2.13, pydantic, PyYAML.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import types
from pathlib import Path

OFFICIAL_WHEEL_SHA256 = "f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d"
ALLOWED_COMPETITION_MODELS = frozenset({
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-12b-it-qat-w4a16-ct",
    "gemma-4-e4b-it-qat-w4a16-ct",
    "gemma-4-e2b-it-qat-w4a16-ct",
})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def official_structural_api():
    dist = importlib.metadata.distribution("adk-submission")
    version = dist.version
    if version != "0.2.13":
        raise RuntimeError(f"expected adk-submission 0.2.13, got {version}")
    original_package_path = Path(dist.locate_file("adk_submission")).resolve()
    if not (original_package_path / "schema.py").is_file():
        raise RuntimeError("Organizer module files missing from verified wheel installation")
    pkg = types.ModuleType("adk_submission")
    pkg.__path__ = [str(original_package_path)]
    pkg.__package__ = "adk_submission"
    pkg.__file__ = str(original_package_path / "__init__.py")
    sys.modules["adk_submission"] = pkg
    # This imports unmodified organizer source files, but deliberately does NOT
    # import google.adk / the compiler or run a task sandbox.
    from adk_submission.discovery import validate_directory
    from adk_submission.limits import SubmissionLimits
    from adk_submission.schema import SandboxedAgentConfig
    from adk_submission.yaml_loader import load_yaml
    return validate_directory, SubmissionLimits, SandboxedAgentConfig, load_yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--submission", action="append", nargs=2, metavar=("LABEL", "DIR"), required=True
    )
    args = parser.parse_args()
    if sha256(args.wheel) != OFFICIAL_WHEEL_SHA256:
        raise RuntimeError("Official Kaggle adk-submission wheel hash mismatch")
    if args.output.exists():
        raise FileExistsError("Will not overwrite existing audit output")

    validate_directory, SubmissionLimits, SandboxedAgentConfig, load_yaml = official_structural_api()
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

    report = {
        "experiment": "G0-NATIVE-SCHEMA-001",
        "source": "Organizer-owned metric/gemma-4-developer-agent-wheelhouse v31",
        "official_wheel_sha256": OFFICIAL_WHEEL_SHA256,
        "official_adk_submission_version": "0.2.13",
        "limits": "Identical keyword values copied from organizer swegemma 0.2.11 build_submission_limits",
        "scope": "REAL official directory validation + YAML includes + Pydantic schema subset, not compile_submission",
        "full_google_adk_compiler": "NOT RUN",
        "native_swegemma_agent_runner": "NOT RUN",
        "gemma_model_inference": "NOT RUN",
        "kaggle_submission": "NOT SENT",
        "cases": [],
    }

    for label, original_path in args.submission:
        directory = Path(original_path).resolve()
        row = {"case": label, "source_dir": str(directory)}
        try:
            if not directory.is_dir():
                raise FileNotFoundError(directory)
            directory_info = validate_directory(directory, limits=limits)
            config_data = load_yaml(
                directory_info.config_path, directory_info.root_dir, limits=limits
            )
            validated = SandboxedAgentConfig.model_validate(config_data)
            concrete = getattr(validated, "root", validated)
            selected_model = getattr(concrete, "model", None)
            if not isinstance(selected_model, str):
                raise ValueError(f"Expected declared model string, got {selected_model!r}")
            if selected_model not in ALLOWED_COMPETITION_MODELS:
                raise ValueError(f"Model alias not allowed: {selected_model}")

            packaged_skill_manifests = sorted(
                str(p.relative_to(directory)) for p in directory.glob("skills/*/SKILL.md")
            )
            declared_skills = config_data.get("skills", []) or []
            row.update({
                "verdict": "PASS_OFFICIAL_STRUCTURAL_SCHEMA_SUBSET",
                "root_config": str(directory_info.config_path.relative_to(directory)),
                "model_name": selected_model,
                "root_schema_class": type(concrete).__name__,
                "file_count": len(directory_info.all_files),
                "files": {
                    str(p.relative_to(directory)): sha256(p)
                    for p in sorted(directory_info.all_files)
                },
                "declared_skills": declared_skills,
                "packaged_skill_manifests": packaged_skill_manifests,
                "warning_packaged_skills_not_declared": (
                    len(packaged_skill_manifests) > 0 and not declared_skills
                ),
                "warning_no_runtime_locator_staging_verified": True,
            })
        except Exception as exc:
            row["verdict"] = "FAIL_OFFICIAL_SCHEMA_SUBSET"
            row["error_type"] = type(exc).__name__
            row["error"] = str(exc)[:2000]
        report["cases"].append(row)
        print(label, row["verdict"], row.get("error", ""), flush=True)

    report["passed"] = sum(
        x["verdict"] == "PASS_OFFICIAL_STRUCTURAL_SCHEMA_SUBSET"
        for x in report["cases"]
    )
    report["total"] = len(report["cases"])
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("REPORT_SHA256", sha256(args.output))
    print("REPORT_PATH", args.output)


if __name__ == "__main__":
    main()
