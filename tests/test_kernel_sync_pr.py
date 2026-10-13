# Copyright 2026 Lusoris
"""Verification that the kernel pin pull request passes the metadata gate and is signed.

`sync-kernel-manifest.yml` opened its first pull request (#102) without a milestone,
labels or an issue reference, so `pr-project-gate.yml` refused it, and its commit was
unsigned in a repository that requires signed commits. The tests below render the pull
request the workflow proposes and run the gate's step script against it, run the step
that resolves the milestone with a stubbed `gh`, and hold the signing input.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.harness.mock_runner import GIT_BASH
from tests.test_pr_project_gate import LABEL_ERROR, MILESTONE_ERROR, REFERENCE_ERROR, run_gate
from tests.test_provisioners_execution import check_bash

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "sync-kernel-manifest.yml"
PR_ACTION = "peter-evans/create-pull-request@"
MILESTONE_STEP = "milestone"
MILESTONE_OUTPUT = "${{ steps.milestone.outputs.number }}"
NO_MILESTONE_ERROR = "::error::the repository has no open milestone"
STEP_TIMEOUT_S = 30
SAMPLE = {"steps.meta.outputs.stream": "realtime", "steps.meta.outputs.version": "7.2.8-lusoris2"}
EXPRESSION = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")


def steps() -> list[dict]:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["jobs"]["sync"]["steps"]


def pr_inputs() -> dict:
    found = [step for step in steps() if step.get("uses", "").startswith(PR_ACTION)]
    assert len(found) == 1
    return found[0]["with"]


def render(text: str) -> str:
    """Fill the workflow expressions with sample values; unknown ones stay visible."""
    return EXPRESSION.sub(lambda m: SAMPLE.get(m[1], f"<{m[1]}>"), text)


def proposed_pr() -> dict:
    inputs = pr_inputs()
    labels = [label.strip() for label in re.split(r"[,\n]", inputs.get("labels", "")) if label.strip()]
    milestone = inputs.get("milestone")
    return {
        "title": render(inputs["title"]),
        "body": render(inputs.get("body", "")),
        "milestone": "1.0" if milestone == MILESTONE_OUTPUT else "",
        "labels": labels,
    }


def test_proposed_pr_passes_the_metadata_gate():
    result = run_gate(**proposed_pr())
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [("milestone", "", MILESTONE_ERROR), ("body", "", REFERENCE_ERROR), ("labels", ["kind/chore"], LABEL_ERROR)],
    ids=["no-milestone", "no-reference", "kind-label-only"],
)
def test_gate_refuses_the_proposal_without_each_part(field, value, error):
    result = run_gate(**{**proposed_pr(), field: value})
    assert result.returncode != 0
    assert error in result.stdout + result.stderr


def test_pin_commit_is_signed_through_the_forge():
    assert pr_inputs().get("sign-commits") is True


def milestone_step() -> dict:
    found = [step for step in steps() if step.get("id") == MILESTONE_STEP]
    assert len(found) == 1
    return found[0]


def resolve_milestone(tmp_path: Path, open_milestones: list[dict]) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the milestone step with a gh stub that prints the given open milestones."""
    check_bash(GIT_BASH)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    listing = tmp_path / "listing.json"
    listing.write_text(json.dumps(open_milestones), encoding="utf-8")
    stub = bin_dir / "gh"
    stub.write_text(f'#!/bin/sh\n[ "$1" = api ] || exit 2\ncat "{listing}"\n', encoding="utf-8")
    stub.chmod(0o700)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "example/imago",
        "RUNNER_TEMP": str(tmp_path),
    }
    result = subprocess.run(
        [str(GIT_BASH), "-c", milestone_step()["run"]],
        env=env,
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT_S,
        check=False,
    )
    return result, output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [([5, 2, 1], "1"), ([5, 2], "2"), ([7], "7")],
    ids=["current-release", "after-the-first-closes", "single"],
)
def test_milestone_step_takes_the_lowest_open_number(tmp_path, numbers, expected):
    result, output = resolve_milestone(tmp_path, [{"number": n, "title": f"m{n}"} for n in numbers])
    assert result.returncode == 0, result.stderr
    assert output == f"number={expected}\n"


def test_milestone_step_fails_without_an_open_milestone(tmp_path):
    result, output = resolve_milestone(tmp_path, [])
    assert result.returncode != 0
    assert NO_MILESTONE_ERROR in result.stderr
    assert output == ""


def test_pr_takes_the_resolved_milestone():
    assert pr_inputs().get("milestone") == MILESTONE_OUTPUT
    names = [step.get("id") for step in steps()]
    pr_at = next(i for i, step in enumerate(steps()) if step.get("uses", "").startswith(PR_ACTION))
    assert names.index(MILESTONE_STEP) < pr_at
