# Copyright 2026 Lusoris
"""Verification of workflow_dispatch flavor input and release matrix dispatch mechanics.

Ensures that manual dispatches can build any canonical flavor while scheduled and
release runs build the 3 generic flavors, and that unknown flavors are refused fail-closed.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.test_flavors import EXPECTED_FLAVORS

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-matrix.yml"


def load_workflow() -> dict:
    """Load release-matrix.yml workflow definition."""
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_dispatch_choice_options() -> None:
    """Verify dispatch choice input matches the canonical 44 flavors and defaults to base-generic."""
    workflow = load_workflow()
    triggers = workflow[True] if True in workflow else workflow["on"]
    flavor_input = triggers["workflow_dispatch"]["inputs"]["flavor"]
    assert flavor_input["type"] == "choice"
    assert flavor_input["default"] == "base-generic"
    options = flavor_input["options"]
    assert len(options) == 44
    assert set(options) == set(EXPECTED_FLAVORS)
    assert len(EXPECTED_FLAVORS) == 44


def test_matrix_flavor_expression() -> None:
    """Verify matrix.flavor references inputs.flavor and defaults to the 3 generic flavors."""
    workflow = load_workflow()
    expr = workflow["jobs"]["build-matrix"]["strategy"]["matrix"]["flavor"]
    assert isinstance(expr, str)
    assert "inputs.flavor" in expr
    match = re.search(r"\|\|\s*'(\[[^']+\])'", expr)
    assert match, f"Could not find non-dispatch JSON array in expression: {expr}"
    generic_flavors = json.loads(match.group(1))
    assert generic_flavors == ["base-generic", "docker-generic", "k8s-node-generic"]


def refuse_step() -> dict:
    """Return the refuse step, which must directly follow the checkout it reads from."""
    steps = load_workflow()["jobs"]["build-matrix"]["steps"]
    assert steps[0].get("uses", "").startswith("actions/checkout@"), "steps[0] is not the checkout"
    assert steps[1].get("name") == "Refuse an Unknown Flavor", "steps[1] is not the refuse step"
    return steps[1]


def test_refuse_step_structure() -> None:
    """Verify the refuse step follows the checkout, uses env FLAVOR, and has no inline expression."""
    step = refuse_step()
    env = step.get("env", {})
    assert env.get("FLAVOR") == "${{ matrix.flavor }}"
    run_cmd = step.get("run", "")
    assert "${{" not in run_cmd


@pytest.mark.parametrize(
    ("flavor", "expect_success"),
    [
        ("base-intel", True),
        ("base-inte", False),
        ("base-intel-x", False),
        ("", False),
        ("../x", False),
    ],
)
def test_refuse_step_execution(flavor: str, expect_success: bool) -> None:
    """Execute refuse step shell body and verify exit codes and error output."""
    run_cmd = refuse_step()["run"]
    env = {**os.environ, "FLAVOR": flavor}
    proc = subprocess.run(
        ["bash", "-c", run_cmd],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if expect_success:
        assert proc.returncode == 0, f"Expected 0 for {flavor!r}, got {proc.returncode}: {proc.stderr}"
    else:
        assert proc.returncode != 0, f"Expected non-zero for {flavor!r}, got 0"
        combined = proc.stdout + proc.stderr
        assert "::error::" in combined, f"Expected '::error::' in output for {flavor!r}, got: {combined}"


def group_isolates_dispatch_flavor(group: str) -> bool:
    """A manual run's group must carry its flavor, and schedule and release runs must not."""
    gated = "github.event_name == 'workflow_dispatch' && inputs.flavor"
    return group.startswith("release-matrix-${{ github.ref }}-") and gated in group


def test_concurrency_group_per_dispatched_flavor() -> None:
    """Manual runs of different flavors must not share the group that lets one cancel another."""
    concurrency = load_workflow()["concurrency"]
    assert concurrency["cancel-in-progress"] is False, "a release run must never be cancelled"
    assert group_isolates_dispatch_flavor(concurrency["group"]), concurrency["group"]


@pytest.mark.parametrize(
    "group",
    [
        "release-matrix-${{ github.ref }}",
        "release-matrix-${{ github.ref }}-${{ inputs.flavor }}",
        "release-matrix-${{ github.run_id }}-${{ github.event_name == 'workflow_dispatch' && inputs.flavor || 'generic' }}",
    ],
)
def test_concurrency_check_refuses_shared_or_unscoped_groups(group: str) -> None:
    """One group per ref, a flavor without the event gate, and a per-run group are all refused."""
    assert not group_isolates_dispatch_flavor(group)


JOB_TIMEOUT_CEILING_MINUTES = 360  # GitHub's own per-job default; a bound must be tighter


def test_every_job_has_a_timeout_below_the_platform_default() -> None:
    """Every job names timeout-minutes, so a lost runner fails the run instead of waiting 6 h."""
    jobs = load_workflow()["jobs"]
    assert jobs, "release-matrix.yml defines no jobs"
    for name, job in jobs.items():
        bound = job.get("timeout-minutes")
        assert isinstance(bound, int), f"job {name} has no integer timeout-minutes"
        assert 0 < bound < JOB_TIMEOUT_CEILING_MINUTES, (
            f"job {name} timeout-minutes {bound} not below {JOB_TIMEOUT_CEILING_MINUTES}"
        )
