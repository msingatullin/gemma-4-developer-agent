#!/usr/bin/env python3
"""Authentic organizer swegemma ContainerManager + run_command, CPU sandbox only.

The code under test is read DIRECTLY from the official downloaded swegemma wheel
installation, not reimplemented. We bypass only swegemma's eager top-level
__init__ eager imports of GPU/model libraries, keeping its sandbox/tools
modules unmodified. Never runs an LLM, competition submit, paid GPU/API.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

SOURCE_SHA256 = "9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3"
EXPECTED_SOURCE_TREE = "2ba551370f1a4204efbab1f82ba6cfd611634723"


def hash_path(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def official_modules(wheel: Path):
    if hash_path(wheel) != SOURCE_SHA256:
        raise ValueError("Official swegemma wheel mismatch")
    dist = importlib.metadata.distribution("swegemma")
    if dist.version != "0.2.11":
        raise ValueError("Wrong installed swegemma version")
    folder = Path(dist.locate_file("swegemma")).resolve()
    # Only suppress __init__.py, which imports model server, GPU and unrelated
    # evaluator features eagerly. The imported docker.py and execution.py source
    # themselves are EXACTLY the unchanged official organizers' wheel.
    for package, rel in (
        ("swegemma", folder),
        ("swegemma.sandbox", folder / "sandbox"),
        ("swegemma.tools", folder / "tools"),
    ):
        mod = types.ModuleType(package)
        mod.__path__ = [str(rel)]
        mod.__package__ = package
        mod.__file__ = str(rel / "__init__.py")
        sys.modules[package] = mod
    from swegemma.sandbox.docker import ContainerConfig, ContainerManager
    from swegemma.tools.execution import run_command
    return ContainerConfig, ContainerManager, run_command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--source-tar", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError("Refuse overwrite prior run")
    if not args.source_tar.is_file():
        raise FileNotFoundError(args.source_tar)
    container_config, Manager, native_run_command = official_modules(args.wheel)
    cfg = container_config(
        image="gemma-paper-cpu:py310-20261110",
        network_mode="none",
        mem_limit="768m",
        cpu_period=100000,
        cpu_quota=100000,
        working_dir="/workspace",
        timeout_seconds=18,
        reuse_containers=False,
    )
    manager = Manager(config=cfg)
    report = {
        "experiment": "G0-NATIVE-TOOLS-003",
        "organizer_wheel": args.wheel.name,
        "organizer_wheel_sha256": SOURCE_SHA256,
        "official_modules": [
            "swegemma.sandbox.docker.ContainerManager",
            "swegemma.tools.execution.run_command",
        ],
        "source_tar_sha256": hash_path(args.source_tar),
        "expected_historical_git_tree": EXPECTED_SOURCE_TREE,
        "image": cfg.image,
        "container_network": "none",
        "cpu_quota_cores": 1,
        "memory_limit": "768m",
        "model_calls": 0,
        "kaggle_submissions": 0,
        "cases": [],
        "setup": {},
        "cleanup": {},
    }
    cid = None
    try:
        cid = manager.start()
        print("CONTAINER_CREATED", cid[:16], flush=True)
        container = manager.client.containers.get(cid)
        container.reload()
        actual_network = container.attrs["HostConfig"]["NetworkMode"]
        memory = container.attrs["HostConfig"]["Memory"]
        period = container.attrs["HostConfig"]["CpuPeriod"]
        quota = container.attrs["HostConfig"]["CpuQuota"]
        assert actual_network == "none", actual_network
        assert quota == 100000 and period == 100000, (quota, period)
        assert 740000000 <= memory <= 820000000, memory
        report["setup"]["container_id"] = cid
        report["setup"]["actual_network"] = actual_network
        report["setup"]["actual_memory_bytes"] = memory
        report["setup"]["cpu_period"] = period
        report["setup"]["cpu_quota"] = quota

        manager.copy_to(cid, args.source_tar, "/tmp")
        setup_script = (
            "set -e; "
            "mkdir -p /workspace; "
            "tar -xf /tmp/" + args.source_tar.name + " -C /workspace; "
            "cd /workspace; "
            "git init -q; git add --force --all; "
            "git -c user.name='G0 CPU' -c user.email='g0@example.invalid' "
            "commit -q -m 'Frozen SWE historical tree'; "
            "git rev-parse HEAD^{tree}"
        )
        prep = manager.exec(cid, setup_script, timeout=18)
        report["setup"]["git_prep"] = {
            "status": prep.status,
            "exit_code": prep.exit_code,
            "stdout": prep.stdout,
            "stderr": prep.stderr[:500],
        }
        if prep.exit_code != 0:
            raise RuntimeError("Historical tree setup failed: " + prep.stderr[:350])
        actual_tree = prep.stdout.strip().splitlines()[-1]
        if actual_tree != EXPECTED_SOURCE_TREE:
            raise ValueError(
                f"Historical source tree mismatch {actual_tree} != {EXPECTED_SOURCE_TREE}"
            )
        report["setup"]["verified_git_tree"] = actual_tree

        context = SimpleNamespace(
            docker=manager,
            container_id=cid,
            harness=SimpleNamespace(command_timeout_seconds=18, max_stdout_chars=3000),
            budget=SimpleNamespace(time_minutes=None, tool_calls=None),
            check_budget=lambda **kw: None,
            remaining_time_seconds=None,
        )
        cases = [
            (
                "working_directory",
                "pwd && git rev-parse --show-toplevel",
                "ok",
                "/workspace",
            ),
            (
                "filename_first",
                "git ls-files '*.py' | grep -i -F 'blueprint' | "
                "grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10",
                "ok",
                "src/flask/blueprints.py",
            ),
            (
                "source_content",
                "git grep -n -i -F 'Blueprint' -- '*.py' "
                "':!tests/**' ':!**/tests/**' ':!**/test_*.py' "
                "':!docs/**' ':!**/docs/**' ':!examples/**' ':!**/examples/**' "
                "| head -20",
                "ok",
                "src/flask/blueprints.py",
            ),
            (
                "unavailable_original_v17_temp_locator",
                "python3 /tmp/ast_locator.py --query Blueprint",
                "error",
                "No such file or directory",
            ),
            (
                "source_tree_unchanged",
                "git status --porcelain",
                "ok",
                "",
            ),
        ]
        for label, cmd, expectation, substr in cases:
            begin = time.monotonic()
            raw = native_run_command(context, cmd)
            response = json.loads(raw)
            status = response.get("status")
            if expectation == "ok":
                assert status == "ok", (label, response)
                output = response.get("stdout", "")
                assert substr in output, (label, output)
                if label == "source_tree_unchanged":
                    assert output.strip() == "", repr(output)
            else:
                assert status == "error", (label, response)
                details = response.get("details", {})
                assert details.get("exit_code") == 2, (label, details)
                assert substr in str(details), (label, details)
            report["cases"].append({
                "name": label,
                "command": cmd,
                "response": response,
                "wall_seconds": round(time.monotonic() - begin, 4),
                "verdict": "PASS",
            })
            print(label, status, "PASS", flush=True)
        report["verdict"] = "PASS_NATIVE_ORGANIZER_TOOL_BRIDGE_5_CASES"
    except Exception as exc:
        report["verdict"] = "FAIL_OR_BLOCKED_NATIVE_TOOL_BRIDGE"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:2200]
        print("RUN_FAILED", type(exc).__name__, str(exc)[:450], flush=True)
    finally:
        if cid:
            try:
                manager.stop(cid)
                report["cleanup"]["attempted"] = True
            except Exception as exc:
                report["cleanup"]["stop_error"] = str(exc)[:500]
            try:
                manager.client.containers.get(cid)
                report["cleanup"]["container_removed"] = False
            except Exception:
                report["cleanup"]["container_removed"] = True
        else:
            report["cleanup"]["no_container_created"] = True
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print("REPORT_SHA256", hash_path(args.report), flush=True)
        print("FINAL_VERDICT", report["verdict"], flush=True)
        print("CONTAINER_CLEANED", report["cleanup"], flush=True)


if __name__ == "__main__":
    main()
