# Copyright 2026 Lusoris
"""Verification that the frozen routing overlay and its documentation name the same open steps.

ADR-0025 froze planning/routing.json as the record of the migration: every open step is
carried by an issue named in its evidence field, and docs/tools/planning-graph.md lists the
open steps with the issue that carries each. ADR-0029 lets a step reopen when its acceptance
is unmet. The tests below check that the overlay and the table agree, so a step marked done
or reopened in one file without the other fails here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "planning" / "routing.json"
DOC = ROOT / "docs" / "tools" / "planning-graph.md"
ISSUE_URL = re.compile(r"https://github\.com/cordanaLLM/imago/issues/(\d+)")
TABLE_ROW = re.compile(r"^\| `(step-[a-z0-9-]+)` \| \[#(\d+)\]\(https://github\.com/cordanaLLM/imago/issues/\2\) \|")
COUNT_LINE = re.compile(r"^(\w+) of the (\d+) steps are done\.", re.MULTILINE)
NUMBER_WORDS = {
    "Eighteen": 18,
    "Nineteen": 19,
    "Twenty": 20,
    "Twenty-one": 21,
    "Twenty-two": 22,
}


def steps() -> dict[str, dict]:
    return json.loads(OVERLAY.read_text(encoding="utf-8"))["steps"]


def open_steps_in_overlay(document: dict[str, dict]) -> dict[str, str]:
    carried = {}
    for name, step in document.items():
        if step["done"]:
            continue
        match = ISSUE_URL.search(step["evidence"])
        carried[name] = match.group(1) if match else ""
    return carried


def open_steps_in_doc(text: str) -> dict[str, str]:
    rows = (TABLE_ROW.match(line) for line in text.splitlines())
    return {row.group(1): row.group(2) for row in rows if row}


def test_every_open_step_names_the_issue_that_carries_it() -> None:
    missing = sorted(name for name, issue in open_steps_in_overlay(steps()).items() if not issue)
    assert not missing, f"open steps without a carrying issue in evidence: {missing}"


def test_documentation_table_lists_exactly_the_open_steps() -> None:
    overlay = open_steps_in_overlay(steps())
    doc = open_steps_in_doc(DOC.read_text(encoding="utf-8"))
    assert doc == overlay, f"planning-graph.md table {doc} differs from routing.json {overlay}"


def test_documentation_counts_the_done_steps() -> None:
    document = steps()
    match = COUNT_LINE.search(DOC.read_text(encoding="utf-8"))
    assert match, "planning-graph.md states no done count"
    done = sum(1 for step in document.values() if step["done"])
    assert NUMBER_WORDS.get(match.group(1)) == done, f"doc says {match.group(1)}, overlay has {done} done"
    assert int(match.group(2)) == len(document)


def test_a_step_reopened_without_the_table_is_refused() -> None:
    document = steps()
    name = next(name for name, step in document.items() if step["done"])
    document[name] = {
        **document[name],
        "done": False,
        "evidence": "Open; carried by https://github.com/cordanaLLM/imago/issues/1",
    }
    doc = open_steps_in_doc(DOC.read_text(encoding="utf-8"))
    assert open_steps_in_overlay(document) != doc


def test_an_open_step_without_an_issue_is_refused() -> None:
    document = steps()
    name = next(name for name, step in document.items() if step["done"])
    document[name] = {**document[name], "done": False, "evidence": "Open"}
    assert open_steps_in_overlay(document)[name] == ""
