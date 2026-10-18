# Copyright 2026 Lusoris
"""Verification that the pull-request metadata gate refuses incomplete metadata.

`.github/workflows/pr-project-gate.yml` fails a pull request without a milestone, without
an issue or epic reference in its title or body, or without a `tier/*` or `area/*` label.
The tests below run the step script of the workflow with planted metadata: complete
metadata passes, each missing part fails with its own error, and near misses at the edge
of each pattern fail as well. They also hold the triggers that re-run the gate when the
metadata changes, and the concurrency group that keeps those re-runs from cancelling each other.
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
from tests.test_provisioners_execution import check_bash

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "pr-project-gate.yml"
STEP = "Verify PR Milestone, Issue Reference and Labels"
STEP_TIMEOUT_S = 30
# Every change of the metadata the gate reads must re-run it, or a green result goes stale.
METADATA_EVENTS = {"opened", "reopened", "edited", "labeled", "unlabeled", "milestoned", "demilestoned", "synchronize"}

COMPLETE = {"title": "fix(ci): planted title", "body": "Ref #6", "milestone": "1.0", "labels": ["area/ci-cd"]}
MILESTONE_ERROR = "missing an assigned milestone"
REFERENCE_ERROR = "must reference a tracked Issue or Epic"
LABEL_ERROR = "at least one 'tier/*' or 'area/*' label"
# Two runs of one pull request on one head commit, as two label events start them.
RUN_A = {"github.ref": "refs/pull/6/merge", "github.run_id": "101", "github.event.action": "labeled"}
RUN_B = {"github.ref": "refs/pull/6/merge", "github.run_id": "102", "github.event.action": "milestoned"}
EXPRESSION = re.compile(r"\$\{\{\s*([^}]*?)\s*\}\}")


def load() -> dict:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def gate_step() -> dict:
    found = [step for step in load()["jobs"]["validate-metadata"]["steps"] if step.get("name") == STEP]
    assert len(found) == 1
    return found[0]


def run_gate(**changes: object) -> subprocess.CompletedProcess[str]:
    """Run the step script with the complete metadata, changed as given."""
    check_bash(GIT_BASH)
    meta = {**COMPLETE, **changes}
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PR_TITLE": str(meta["title"]),
        "PR_BODY": str(meta["body"]),
        "PR_MILESTONE": str(meta["milestone"]),
        "PR_LABELS": json.dumps(meta["labels"]),
    }
    return subprocess.run(
        [str(GIT_BASH), "-c", gate_step()["run"]],
        env=env,
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT_S,
        check=False,
    )


def test_complete_metadata_passes():
    result = run_gate()
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "changes",
    [
        {"body": "Fixes cordanaLLM/praetor#1290"},
        {"body": "Relates to EPIC-01"},
        {"body": "", "title": "fix: planted title, closes #6"},
        {"body": "REF #6"},
        {"body": "first line\nResolves  #6"},
        {"labels": ["tier/1"]},
        {"labels": ["kind/bug", "area/ci-cd"]},
    ],
    ids=["cross-repo", "epic", "title-only", "upper-case", "second-line", "tier-label", "mixed-labels"],
)
def test_boundary_metadata_passes(changes):
    result = run_gate(**changes)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"milestone": ""}, MILESTONE_ERROR),
        ({"milestone": "null"}, MILESTONE_ERROR),
        ({"body": "No reference here"}, REFERENCE_ERROR),
        ({"body": "Ref #"}, REFERENCE_ERROR),
        ({"body": "ref#6"}, REFERENCE_ERROR),
        ({"body": "See #6"}, REFERENCE_ERROR),
        ({"labels": []}, LABEL_ERROR),
        ({"labels": ["kind/bug"]}, LABEL_ERROR),
        ({"labels": ["area/"]}, LABEL_ERROR),
        ({"labels": ["subarea/ci-cd"]}, LABEL_ERROR),
    ],
    ids=[
        "no-milestone",
        "null-milestone",
        "no-reference",
        "reference-without-number",
        "reference-without-space",
        "unknown-keyword",
        "no-label",
        "kind-label-only",
        "empty-area",
        "prefixed-area",
    ],
)
def test_planted_incomplete_metadata_fails(changes, error):
    result = run_gate(**changes)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::" in result.stdout and error in result.stdout


def test_gate_reruns_on_every_metadata_change():
    # PyYAML reads the unquoted key `on` as True; the workflow quotes it.
    types = set(load()["on"]["pull_request"]["types"])
    assert METADATA_EVENTS <= types, sorted(METADATA_EVENTS - types)


def test_gate_step_carries_no_bypass():
    step = gate_step()
    job = load()["jobs"]["validate-metadata"]
    assert "continue-on-error" not in step and "continue-on-error" not in job
    assert "if" not in step and "if" not in job
    assert step["run"].lstrip().startswith("set -euo pipefail")
    assert "|| true" not in step["run"]


def render(group: str, context: dict[str, str]) -> str:
    """Fill the `${{ name }}` expressions of a group; an unknown expression fails the test."""

    def value(match: re.Match[str]) -> str:
        name = match.group(1)
        assert name in context, f"group uses {name}, which the test does not model"
        return context[name]

    return EXPRESSION.sub(value, group)


def run_can_be_cancelled(concurrency: dict) -> bool:
    """Whether one of two runs on the same head commit can cancel the other.

    Runs in one group queue: a new run cancels the pending one, and with
    `cancel-in-progress` also the running one. Only distinct groups cancel nothing.
    """
    group = str(concurrency["group"])
    return render(group, RUN_A) == render(group, RUN_B) or concurrency.get("cancel-in-progress") is not False


def test_metadata_reruns_cancel_no_run():
    concurrency = load()["concurrency"]
    assert not run_can_be_cancelled(concurrency), concurrency


@pytest.mark.parametrize(
    "concurrency",
    [
        {"group": "pr-project-gate-${{ github.ref }}", "cancel-in-progress": True},
        {"group": "pr-project-gate-${{ github.ref }}", "cancel-in-progress": False},
        {"group": "pr-project-gate-${{ github.ref }}-${{ github.run_id }}", "cancel-in-progress": True},
    ],
    ids=["shape-before-fix", "shared-group-without-cancel", "own-group-with-cancel"],
)
def test_planted_cancelling_concurrency_is_refused(concurrency):
    assert run_can_be_cancelled(concurrency)


def test_unmodelled_group_expression_fails():
    with pytest.raises(AssertionError, match="github.sha"):
        render("pr-project-gate-${{ github.sha }}", RUN_A)
