# Copyright 2026 Lusoris
"""Verification that renovate.json satisfies the pull-request metadata gate requirements.

Renovate pull requests must satisfy the governance hard gates in
.github/workflows/pr-project-gate.yml:
1. Assigned active milestone (milestone > 0).
2. Tracked issue or epic reference in PR title or body (via prBodyNotes).
3. At least one 'tier/*' or 'area/*' label.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
RENOVATE_PATH = ROOT / "renovate.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pr-project-gate.yml"
LABEL_AREA_TIER_PATTERN = re.compile(r"^(tier|area)/")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a dictionary from key-value pairs, refusing duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key in JSON: {key!r}")
        result[key] = value
    return result


def load_renovate_config(path: Path = RENOVATE_PATH) -> dict[str, Any]:
    """Load renovate.json with strict duplicate key rejection."""
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)


def parse_gate_regexes(workflow_path: Path = WORKFLOW_PATH) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """Parse issue-ref and tier/area label regexes from pr-project-gate.yml.

    Translates POSIX [[:space:]] in the issue-ref pattern to Python \\s.
    """
    content = workflow_path.read_text(encoding="utf-8")

    issue_match = re.search(r"grep\s+-Eqi\s+'([^']+)'", content)
    assert issue_match is not None, "issue-ref pattern not found in pr-project-gate.yml"
    issue_posix = issue_match.group(1)
    issue_python = issue_posix.replace("[[:space:]]", r"\s")
    issue_regex = re.compile(issue_python, re.IGNORECASE)

    label_match = re.search(r"grep\s+-Eq\s+'([^']+)'", content)
    assert label_match is not None, "label pattern not found in pr-project-gate.yml"
    label_gate_regex = re.compile(label_match.group(1))

    return issue_regex, label_gate_regex


def check_renovate_config(
    config: dict[str, Any],
    issue_regex: re.Pattern[str] | None = None,
) -> list[str]:
    """Check a Renovate config against the PR metadata gate requirements.

    Returns a list of identified problems (empty when all gate requirements pass).
    """
    if issue_regex is None:
        issue_regex, _ = parse_gate_regexes()

    problems: list[str] = []

    # 1. Milestone Check: must be an int > 0
    milestone = config.get("milestone")
    if not isinstance(milestone, int) or isinstance(milestone, bool) or milestone <= 0:
        problems.append(f"milestone must be an int > 0, got {milestone!r}")

    # 2. Issue/Epic Reference Check: prBodyNotes joined must match issue-ref regex
    notes = config.get("prBodyNotes")
    if not isinstance(notes, list) or not notes:
        problems.append("missing or empty prBodyNotes with issue reference")
    else:
        joined_notes = "\n".join(str(note) for note in notes)
        if not issue_regex.search(joined_notes):
            problems.append(f"prBodyNotes joined does not match issue reference regex: {joined_notes!r}")

    # 3. Label Check: at least one label matches ^(tier|area)/
    labels = config.get("labels")
    if not isinstance(labels, list) or not any(
        isinstance(lbl, str) and LABEL_AREA_TIER_PATTERN.search(lbl) for lbl in labels
    ):
        problems.append("labels must contain at least one 'tier/*' or 'area/*' label")

    return problems


def test_renovate_pr_metadata():
    """Verify renovate.json satisfies all metadata gate requirements."""
    config = load_renovate_config()
    issue_regex, label_gate_regex = parse_gate_regexes()

    problems = check_renovate_config(config, issue_regex=issue_regex)
    assert not problems, f"renovate.json has gate compliance problems: {problems}"

    # Assert milestone is an int > 0
    milestone = config.get("milestone")
    assert isinstance(milestone, int) and not isinstance(milestone, bool)
    assert milestone > 0

    # Assert each prBodyNotes string joined matches the issue-ref regex
    notes = config.get("prBodyNotes")
    assert isinstance(notes, list) and len(notes) > 0
    joined_notes = "\n".join(notes)
    assert issue_regex.search(joined_notes) is not None

    # Assert some label matches ^(tier|area)/
    labels = config.get("labels")
    assert isinstance(labels, list)
    assert any(LABEL_AREA_TIER_PATTERN.search(label) for label in labels)

    # Assert workflow gate's raw label grep pattern matches JSON-serialized labels
    assert label_gate_regex.search(json.dumps(labels)) is not None


def test_checker_refuses_unpatched_config():
    """Verify the checker refuses a config without milestone, labels=['dependencies'], and no ref note."""
    issue_regex, _ = parse_gate_regexes()
    unpatched = {
        "labels": ["dependencies"],
    }
    problems = check_renovate_config(unpatched, issue_regex=issue_regex)
    assert len(problems) == 3
    assert any("milestone" in p for p in problems)
    assert any("labels" in p for p in problems)
    assert any("prBodyNotes" in p for p in problems)


@pytest.mark.parametrize(
    ("mutation", "expected_problem_keyword"),
    [
        ({"milestone": None}, "milestone"),
        ({"milestone": 0}, "milestone"),
        ({"milestone": -1}, "milestone"),
        ({"milestone": "1"}, "milestone"),
        ({"milestone": True}, "milestone"),
        ({"labels": ["dependencies"]}, "labels"),
        ({"labels": []}, "labels"),
        ({"labels": ["kind/chore"]}, "labels"),
        ({"prBodyNotes": []}, "prBodyNotes"),
        ({"prBodyNotes": None}, "prBodyNotes"),
        ({"prBodyNotes": ["Automated update without issue reference"]}, "prBodyNotes"),
    ],
    ids=[
        "missing-milestone",
        "zero-milestone",
        "negative-milestone",
        "string-milestone",
        "bool-milestone",
        "dependencies-label-only",
        "empty-labels",
        "kind-label-only",
        "empty-pr-body-notes",
        "none-pr-body-notes",
        "note-without-ref",
    ],
)
def test_checker_refuses_individual_defects(mutation, expected_problem_keyword):
    """Verify the checker catches each individual defect."""
    config = load_renovate_config()
    for key, value in mutation.items():
        if value is None:
            config.pop(key, None)
        else:
            config[key] = value

    problems = check_renovate_config(config)
    assert len(problems) >= 1
    assert any(expected_problem_keyword in p for p in problems)


def test_load_renovate_config_rejects_duplicate_keys():
    """Verify reject_duplicate_keys raises ValueError on duplicate JSON keys."""
    duplicate_json = '{"milestone": 1, "milestone": 2}'
    with pytest.raises(ValueError, match="duplicate key in JSON"):
        json.loads(duplicate_json, object_pairs_hook=reject_duplicate_keys)
