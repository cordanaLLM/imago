# Copyright 2026 Lusoris
"""Verification of the skips the required-checks aggregator accepts (ADR-0026).

`.github/workflows/required-aggregator.yml` accepts a skipped check only when its name is
listed in `MAY_SKIP`. A job belongs in that list when it needs the change detector of its
workflow (job `changes`) and its condition is an alternation of event-name comparisons
and detector outputs, so that only the event or the detector can skip it. These tests
hold the list equal to those jobs, refuse planted conditions that could skip a job on
another ground, and run the step that turns the list into the action inputs.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
AGGREGATOR = WORKFLOWS / "required-aggregator.yml"

# One term of an accepted condition; the terms are joined by `||` only.
ALLOWED_TERMS = re.compile(r"github\.event_name\s*==\s*'[a-z_]+'|needs\.changes\.outputs\.[a-z_]+\s*==\s*'true'")
NAME_CHARS = re.compile(r"[A-Za-z0-9 &.]+")
WAIT_ACTION = "lewagon/wait-on-check-action@"


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def detector_decides(job: dict) -> bool:
    """True when only the event or the change detector can skip this job."""
    needs = job.get("needs", [])
    needs = [needs] if isinstance(needs, str) else needs
    condition = job.get("if")
    if "changes" not in needs or not isinstance(condition, str):
        return False
    terms = [term.strip() for term in condition.split("||")]
    return all(ALLOWED_TERMS.fullmatch(term) for term in terms)


def detector_gated_names() -> set[str]:
    names = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for job in (load(path).get("jobs") or {}).values():
            if detector_decides(job):
                names.add(job["name"])
    return names


def may_skip() -> list[str]:
    return load(AGGREGATOR)["env"]["MAY_SKIP"].splitlines()


def aggregator_steps() -> list[dict]:
    return load(AGGREGATOR)["jobs"]["required-checks"]["steps"]


def test_may_skip_equals_detector_gated_jobs():
    listed = may_skip()
    assert len(listed) == len(set(listed)), "MAY_SKIP lists a name twice"
    assert set(listed) == detector_gated_names()


def test_may_skip_names_hold_only_safe_characters():
    for name in may_skip():
        assert NAME_CHARS.fullmatch(name), f"{name!r} needs escaping in the aggregator step"


@pytest.mark.parametrize(
    "job",
    [
        {"name": "x", "if": "github.event_name == 'workflow_dispatch'"},
        {"name": "x", "needs": "changes"},
        {"name": "x", "needs": "changes", "if": "always() || needs.changes.outputs.go == 'true'"},
        {"name": "x", "needs": "changes", "if": "needs.changes.outputs.go == 'true' && false"},
        {"name": "x", "needs": "changes", "if": "needs.changes.outputs.go != 'true'"},
        {"name": "x", "needs": ["build"], "if": "needs.changes.outputs.go == 'true'"},
        {"name": "x", "needs": "changes", "if": "github.event_name == 'push' |||| x"},
    ],
    ids=["no-detector", "no-condition", "always", "and-false", "negated", "other-need", "residue"],
)
def test_planted_conditions_are_not_detector_decided(job):
    assert not detector_decides(job)


@pytest.mark.parametrize(
    "condition",
    [
        "needs.changes.outputs.go == 'true'",
        "github.event_name == 'push' || needs.changes.outputs.docs == 'true'",
        " ||\n".join(
            [
                "github.event_name == 'push'",
                "needs.changes.outputs.python == 'true'",
                "needs.changes.outputs.shell == 'true'",
            ]
        ),
    ],
)
def test_detector_conditions_are_accepted(condition):
    assert detector_decides({"name": "x", "needs": ["changes"], "if": condition})


def test_aggregator_accepts_skips_only_for_the_listed_checks():
    waits = [step for step in aggregator_steps() if step.get("uses", "").startswith(WAIT_ACTION)]
    assert len(waits) == 2
    every_other, gated = waits[0]["with"], waits[1]["with"]
    assert every_other["allowed-conclusions"] == "success"
    assert every_other["ignore-checks"] == "${{ steps.may-skip.outputs.ignore }}"
    assert every_other["running-workflow-name"] == "required-checks"
    assert gated["allowed-conclusions"] == "success,skipped"
    assert gated["check-regexp"] == "${{ steps.may-skip.outputs.regexp }}"
    assert "ignore-checks" not in gated and "check-name" not in gated


def run_list_step(names: list[str], tmp_path: Path) -> dict[str, str]:
    step = next(s for s in aggregator_steps() if s.get("id") == "may-skip")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = {"MAY_SKIP": "\n".join(names), "GITHUB_OUTPUT": str(output), "PATH": "/usr/bin:/bin"}
    subprocess.run(["bash", "-c", step["run"]], env=env, check=True, timeout=30)
    pairs = (line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    return dict(pairs)


def test_list_step_builds_exact_inputs(tmp_path):
    names = may_skip()
    outputs = run_list_step(names, tmp_path)
    assert [name.strip() for name in outputs["ignore"].split(",")] == names
    pattern = re.compile(outputs["regexp"])
    for name in names:
        assert pattern.search(name), name
    near_misses = ["required-checks", "Strict MkDocs BuildX", "Go 1x27 Build & Unit Tests"]
    near_misses += [f"{names[0]} (retry)", "Detect Changed Paths", ""]
    for name in near_misses:
        assert not pattern.search(name), name
