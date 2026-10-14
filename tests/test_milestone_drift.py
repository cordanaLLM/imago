# Copyright 2026 Lusoris
"""Verification that the milestone drift check fails when the file differs from the forge.

.github/milestones.json is the copy of the forge milestones. The milestone-drift workflow
fetches the forge listing and runs tools/ci/milestone_drift.py on it and the file. The
tests below build a forge listing from the committed file, change one side at a time and
check that the script fails and names the difference, and that the workflow keeps the
fetch and the check wired together.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "milestone_drift.py"
FILE = ROOT / ".github" / "milestones.json"
WORKFLOW = ROOT / ".github" / "workflows" / "milestone-drift.yml"
SCRIPT_TIMEOUT_S = 60

_spec = importlib.util.spec_from_file_location("milestone_drift", SCRIPT)
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)


def committed() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8"))


def forge_listing(document: dict) -> list[dict]:
    """The shape the forge API returns: a list with more fields than the file keeps."""
    return [
        {"number": number, "url": f"https://api.example.com/milestones/{number}", **milestone}
        for number, milestone in enumerate(document["milestones"], 1)
    ]


def run(tmp_path: Path, forge: object, document: object) -> subprocess.CompletedProcess[str]:
    (tmp_path / "forge.json").write_text(json.dumps(forge), encoding="utf-8")
    (tmp_path / "milestones.json").write_text(json.dumps(document), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(SCRIPT),
            "--forge",
            str(tmp_path / "forge.json"),
            "--file",
            str(tmp_path / "milestones.json"),
        ],
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_S,
        check=False,
    )


def test_committed_file_matches_a_forge_listing_built_from_it(tmp_path: Path) -> None:
    document = committed()
    done = run(tmp_path, forge_listing(document), document)
    assert done.returncode == 0, done.stderr
    assert f"matches the {len(document['milestones'])} milestones" in done.stdout


@pytest.mark.parametrize("field", ["state", "due_on", "description"])
def test_a_changed_field_on_the_forge_fails(tmp_path: Path, field: str) -> None:
    document = committed()
    forge = forge_listing(document)
    forge[0][field] = {"state": "closed", "due_on": "2027-01-01T00:00:00Z", "description": "changed"}[field]
    done = run(tmp_path, forge, document)
    assert done.returncode == 1
    assert f"milestone '{forge[0]['title']}': {field} is" in done.stderr


def test_a_milestone_only_on_the_forge_fails(tmp_path: Path) -> None:
    document = committed()
    forge = forge_listing(document) + [{"title": "v9.9.9 - New", "state": "open", "due_on": None, "description": ""}]
    done = run(tmp_path, forge, document)
    assert done.returncode == 1
    assert "milestone 'v9.9.9 - New' is on the forge but not in the file" in done.stderr


def test_a_milestone_only_in_the_file_fails(tmp_path: Path) -> None:
    document = committed()
    done = run(tmp_path, forge_listing(document)[1:], document)
    assert done.returncode == 1
    assert f"milestone '{document['milestones'][0]['title']}' is in the file but not on the forge" in done.stderr


def test_a_title_listed_twice_fails(tmp_path: Path) -> None:
    document = committed()
    twice = copy.deepcopy(document)
    twice["milestones"].append(twice["milestones"][0])
    done = run(tmp_path, forge_listing(document), twice)
    assert done.returncode == 1
    assert "lists milestone" in done.stderr and "twice" in done.stderr


@pytest.mark.parametrize(
    ("forge", "reason"),
    [
        ([], "lists no milestone"),
        ({"message": "Not Found", "status": "404"}, "gives dict where a list of milestones belongs"),
        (None, "gives NoneType where a list of milestones belongs"),
        ([{"state": "open"}], "holds a milestone without a title"),
    ],
    ids=["empty", "api-error", "null", "untitled"],
)
def test_a_forge_listing_that_cannot_be_compared_fails(tmp_path: Path, forge: object, reason: str) -> None:
    done = run(tmp_path, forge, committed())
    assert done.returncode == 1
    assert f"::error::Milestone drift: the forge {reason}" in done.stderr


def test_a_file_without_milestones_fails(tmp_path: Path) -> None:
    done = run(tmp_path, forge_listing(committed()), {"version": "1.0.0"})
    assert done.returncode == 1
    assert "the file gives NoneType where a list of milestones belongs" in done.stderr


def test_more_milestones_than_the_bound_fail(tmp_path: Path) -> None:
    many = [
        {"title": f"m{n}", "state": "open", "due_on": None, "description": ""} for n in range(drift.MAX_MILESTONES + 1)
    ]
    done = run(tmp_path, many, {"milestones": many})
    assert done.returncode == 1
    assert f"more than {drift.MAX_MILESTONES}" in done.stderr


def test_exactly_the_bound_passes(tmp_path: Path) -> None:
    many = [{"title": f"m{n}", "state": "open", "due_on": None, "description": ""} for n in range(drift.MAX_MILESTONES)]
    done = run(tmp_path, many, {"milestones": many})
    assert done.returncode == 0, done.stderr


def test_null_and_empty_description_are_the_same(tmp_path: Path) -> None:
    document = {"milestones": [{"title": "m", "state": "open", "due_on": None, "description": ""}]}
    forge = [{"title": "m", "state": "open", "due_on": None, "description": None}]
    done = run(tmp_path, forge, document)
    assert done.returncode == 0, done.stderr


def test_workflow_fetches_every_milestone_and_runs_the_check() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["drift"]["steps"]
    runs = "\n".join(step.get("run", "") for step in steps)
    assert "milestones?state=all&per_page=100" in runs
    assert "python3 -I tools/ci/milestone_drift.py --forge" in runs
    assert "--file .github/milestones.json" in runs
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert "schedule" in triggers
    assert ".github/milestones.json" in triggers["pull_request"]["paths"]
