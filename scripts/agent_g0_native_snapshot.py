#!/usr/bin/env python3
"""G0-004: REAL organizer swegemma.extract_snapshot into isolated CPU Docker.

Tests organizer's actual ContainerManager, snapshot extraction and run_command.
Does NOT run a model, generate a patch, submit, invoke an agent or touch prod.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import shutil
import sys
import types
from pathlib import Path
from types import SimpleNamespace

OFFICIAL_SWEGEMMA_SHA = "9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3"
FROZEN_TREE = "2ba551370f1a4204efbab1f82ba6cfd611634723"
IMAGE = "gemma-agent-g0-cpu-git:20261112"
IMAGE_DIGEST = "sha256:dfc9164e95596719ef4b420ed713b3ce8b6616fa3ce5917dd6bcd45bfd99b6ee"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def official_symbols(wheel: Path):
    if sha(wheel) != OFFICIAL_SWEGEMMA_SHA:
        raise ValueError("Wheel hash invalid")
    dist = importlib.metadata.distribution("swegemma")
    if dist.version != "0.2.11":
        raise ValueError("Wrong swegemma version")
    root = Path(dist.locate_file("swegemma")).resolve()
    # Suppress only top-level swegemma/__init__ eager optional model imports,
    # NOT the official sandbox, tools or snapshot source code under test.
    for name, folder in (
        ("swegemma", root),
        ("swegemma.harness", root / "harness"),
    ):
        m = types.ModuleType(name)
        m.__package__ = name
        m.__path__ = [str(folder)]
        m.__file__ = str(folder / "__init__.py")
        sys.modules[name] = m
    from swegemma.harness.container_setup import extract_snapshot
    from swegemma.sandbox.docker import ContainerConfig, ContainerManager
    from swegemma.tools.execution import run_command
    return extract_snapshot, ContainerConfig, ContainerManager, run_command


def check_result(r, status: str, substring: str):
    assert r["status"] == status, r
    assert substring in r.get("stdout", "") or substring in str(r), r


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wheel", required=True, type=Path)
    p.add_argument("--pinned-tar", required=True, type=Path)
    p.add_argument("--gzip-out", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    if a.gzip_out.exists() or a.report.exists():
        raise FileExistsError("Never overwrite a prior run")
    if not a.pinned_tar.is_file():
        raise FileNotFoundError(a.pinned_tar)
    extract_snapshot, ContainerConfig, ContainerManager, native_run_command = official_symbols(a.wheel)

    with a.gzip_out.open("xb") as out:
        with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=out) as gz:
            with a.pinned_tar.open("rb") as inp:
                shutil.copyfileobj(inp, gz)
    gz_sha = sha(a.gzip_out)
    with gzip.open(a.gzip_out, "rb") as inp:
        if hashlib.sha256(inp.read()).hexdigest() != sha(a.pinned_tar):
            raise RuntimeError("gzip source round-trip mismatch")

    config = ContainerConfig(
        image=IMAGE,
        network_mode="none",
        mem_limit="768m",
        cpu_period=100_000,
        cpu_quota=100_000,
        working_dir="/workspace",
        timeout_seconds=18,
        reuse_containers=False,
    )
    manager = ContainerManager(config=config)
    report = {
        "experiment_id": "G0-NATIVE-SNAPSHOT-004",
        "official_wheel_sha256": OFFICIAL_SWEGEMMA_SHA,
        "organizer_methods": [
            "swegemma.harness.container_setup.extract_snapshot",
            "swegemma.sandbox.docker.ContainerManager",
            "swegemma.tools.execution.run_command",
        ],
        "image": IMAGE,
        "expected_image_digest": IMAGE_DIGEST,
        "source_pinned_tar_sha256": sha(a.pinned_tar),
        "source_pinned_tar_gzip_sha256": gz_sha,
        "pinned_git_tree": FROZEN_TREE,
        "model_calls": 0,
        "kaggle_submissions": 0,
        "cases": [],
        "cleanup": {},
    }
    cid = None
    try:
        image = manager.client.images.get(IMAGE)
        assert image.id == IMAGE_DIGEST, (image.id, IMAGE_DIGEST)
        cid = manager.start()
        container = manager.client.containers.get(cid)
        container.reload()
        host = container.attrs["HostConfig"]
        assert host["NetworkMode"] == "none", host
        assert host["CpuQuota"] == 100_000 and host["CpuPeriod"] == 100_000
        assert 740_000_000 < host["Memory"] < 820_000_000
        report["container_id"] = cid

        initial = manager.exec(cid, "test ! -f /tmp/ast_locator.py && echo ABSENT_BEFORE", timeout=12)
        assert initial.exit_code == 0 and "ABSENT_BEFORE" in initial.stdout
        report["cases"].append({"case": "clean_tmp_locator_absence", "status": "PASS"})

        # This is the real, unmodified organizer snapshot staging method.
        extract_snapshot(manager, cid, a.gzip_out)
        report["cases"].append({"case": "official_extract_snapshot", "status": "PASS"})

        setup = manager.exec(
            cid,
            "set -e; cd /workspace; git init -q; git add --force --all; "
            "git -c user.name='G0 CPU' -c user.email='g0@example.invalid' "
            "commit -q -m 'Historical pinned source'; git rev-parse HEAD^{tree}",
            timeout=18,
        )
        assert setup.exit_code == 0, setup.stderr
        actual_tree = setup.stdout.strip().splitlines()[-1]
        assert actual_tree == FROZEN_TREE, (actual_tree, FROZEN_TREE)
        report["cases"].append({
            "case": "pinned_git_tree_byte_content", "status": "PASS", "git_tree": actual_tree
        })

        context = SimpleNamespace(
            docker=manager, container_id=cid,
            harness=SimpleNamespace(command_timeout_seconds=18, max_stdout_chars=4500),
            budget=SimpleNamespace(time_minutes=None, tool_calls=None),
            check_budget=lambda **kw: None,
            remaining_time_seconds=None,
        )
        commands = [
            ("working_directory", "pwd", "ok", "/workspace"),
            (
                "original_source_file",
                "git ls-files '*.py' | grep -i -F 'blueprint' | "
                "grep -Ev '(^|/)(tests?|docs?|examples?)/' | head -10",
                "ok", "src/flask/blueprints.py",
            ),
            (
                "original_v17_locator_absent_after_official_extract",
                "test ! -f /tmp/ast_locator.py && echo NO_STAGED_AST_LOCATOR",
                "ok", "NO_STAGED_AST_LOCATOR",
            ),
            (
                "clean_tracked_tree",
                "git status --porcelain",
                "ok", "",
            ),
        ]
        for label, cmd, expected, substr in commands:
            response = json.loads(native_run_command(context, cmd))
            check_result(response, expected, substr)
            if label == "clean_tracked_tree":
                assert response.get("stdout", "").strip() == "", response
            report["cases"].append({
                "case": label, "status": "PASS", "command": cmd,
                "tool_response": response,
            })
            print(label, "PASS", flush=True)
        report["verdict"] = "PASS_OFFICIAL_SNAPSHOT_AND_TOOL_BRIDGE"
    except Exception as exc:
        report["verdict"] = "FAIL_OR_BLOCKED_OFFICIAL_SNAPSHOT"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:1800]
        print("OFFICIAL_SNAPSHOT_CHECK_FAILED", type(exc).__name__, str(exc)[:420], flush=True)
    finally:
        if cid:
            try:
                manager.stop(cid)
                report["cleanup"]["attempted"] = True
            except Exception as exc:
                report["cleanup"]["error"] = str(exc)[:400]
            try:
                manager.client.containers.get(cid)
                report["cleanup"]["removed"] = False
            except Exception:
                report["cleanup"]["removed"] = True
        else:
            report["cleanup"]["container_created"] = False
        a.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print("FINAL_VERDICT", report["verdict"], flush=True)
        print("RAW_EVIDENCE_SHA256", sha(a.report), flush=True)
        print("CLEANUP", report["cleanup"], flush=True)


if __name__ == "__main__":
    main()
