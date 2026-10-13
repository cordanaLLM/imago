# Copyright 2026 Lusoris
"""Verification that the pull-request metadata gate refuses incomplete metadata.

`.github/workflows/pr-project-gate.yml` fails a pull request without a milestone, without
an issue or epic reference in its title or body, or without a `tier/*` or `area/*` label.
The tests below run the step script of the workflow with planted metadata: complete
metadata passes, each missing part fails with its own error, and near misses at the edge
of each pattern fail as well. They also hold the triggers that re-run the gate when the
metadata changes.
"""

from __future__ import annotations

import json
import os
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
