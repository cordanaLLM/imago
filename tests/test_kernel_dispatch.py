# Copyright 2026 Lusoris
"""Verification that dispatch-kernel-requirements.yml fails when it cannot dispatch.

The dispatch step once ran only when KERNEL_FORGE_TOKEN was set. Without the secret it
was skipped and the job passed, so a requirement change never reached nucleus while
the run reported green. The workflow now runs a guard step that fails without the
token, and the dispatch step carries no condition. The tests below read the workflow,
execute the guard script with and without a token, and refuse the planted variants
that would pass without dispatching.
"""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.harness.mock_runner import GIT_BASH
from tests.test_provisioners_execution import check_bash

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "dispatch-kernel-requirements.yml"
DISPATCH_ACTION = "peter-evans/repository-dispatch@"
GUARD = "Require Dispatch Token"
TOKEN = "KERNEL_FORGE_TOKEN"
TOKEN_SOURCE = "${{ secrets.KERNEL_FORGE_TOKEN }}"
MISSING_TOKEN_ERROR = "::error::KERNEL_FORGE_TOKEN is not set"
GUARD_TIMEOUT_S = 30


def steps() -> list[dict]:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["jobs"]["dispatch"]["steps"]


def step_index(predicate) -> int:
    matches = [i for i, step in enumerate(steps()) if predicate(step)]
    assert len(matches) == 1, matches
    return matches[0]


def dispatch_can_skip(step: dict) -> bool:
    return "if" in step


def run_guard(script: str, token: str | None) -> subprocess.CompletedProcess:
    check_bash(GIT_BASH)
    # Only PATH is passed on, so a token in the test environment cannot leak in.
    env = {"PATH": os.environ.get("PATH", "")}
    if token is not None:
        env[TOKEN] = token
    return subprocess.run(
        [str(GIT_BASH), "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=GUARD_TIMEOUT_S,
        check=False,
    )


def guard_refuses_missing_token(script: str) -> bool:
    missing = [run_guard(script, token) for token in (None, "")]
    present = run_guard(script, "planted-token")
    return all(res.returncode != 0 for res in missing) and present.returncode == 0


def guard_script() -> str:
    return steps()[step_index(lambda step: step.get("name") == GUARD)]["run"]


def test_dispatch_step_always_runs():
    dispatch = steps()[step_index(lambda step: step.get("uses", "").startswith(DISPATCH_ACTION))]
    assert not dispatch_can_skip(dispatch)


def test_planted_conditional_dispatch_can_skip():
    planted = {"uses": DISPATCH_ACTION, "if": "env.KERNEL_FORGE_TOKEN != ''"}
    assert dispatch_can_skip(planted)


def test_guard_runs_before_the_dispatch_and_reads_the_secret():
    guard = step_index(lambda step: step.get("name") == GUARD)
    dispatch = step_index(lambda step: step.get("uses", "").startswith(DISPATCH_ACTION))
    assert guard < dispatch
    assert steps()[guard]["env"][TOKEN] == TOKEN_SOURCE
    assert not dispatch_can_skip(steps()[guard])


@pytest.mark.parametrize("token", [None, ""], ids=["unset", "empty"])
def test_guard_fails_without_a_token(token):
    res = run_guard(guard_script(), token)
    assert res.returncode == 1
    assert MISSING_TOKEN_ERROR in res.stdout


def test_guard_passes_with_a_token():
    res = run_guard(guard_script(), "planted-token")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "::error::" not in res.stdout


@pytest.mark.parametrize(
    "script",
    [
        'echo "::warning::KERNEL_FORGE_TOKEN is not set"',
        'if [ -z "${GITHUB_TOKEN:-}" ]; then exit 1; fi',
        "exit 1",
    ],
    ids=["warns-only", "wrong-variable", "always-fails"],
)
def test_planted_guards_are_refused(script):
    assert not guard_refuses_missing_token(script)


def test_workflow_guard_refuses_a_missing_token():
    assert guard_refuses_missing_token(guard_script())
