#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Fail when .github/milestones.json no longer matches the milestones on the forge.

The forge is the source of the milestones and the file is its copy (GOVERNANCE.md), but
nothing compared the two: the file kept a 30-flavor description of milestone 1 and
lacked the fifth milestone after both had changed on the forge. This check reads the forge
listing that the workflow fetched (`gh api .../milestones?state=all`) and the file, pairs
the milestones by title and fails on a milestone that only one side has, on a title that
appears twice, and on a different state, due date or description.

Usage: python3 -I tools/ci/milestone_drift.py --forge forge.json --file .github/milestones.json
"""

import argparse
import json
import pathlib
import sys

FIELDS = ("state", "due_on", "description")
MAX_MILESTONES = 100


class DriftError(Exception):
    """A listing that cannot be compared, or a file that differs from the forge."""


def by_title(milestones: object, side: str) -> dict[str, dict]:
    if not isinstance(milestones, list):
        raise DriftError(f"the {side} gives {type(milestones).__name__} where a list of milestones belongs")
    if not milestones:
        raise DriftError(f"the {side} lists no milestone")
    if len(milestones) > MAX_MILESTONES:
        raise DriftError(f"the {side} lists {len(milestones)} milestones, more than {MAX_MILESTONES}")
    titled: dict[str, dict] = {}
    for milestone in milestones:
        if not isinstance(milestone, dict) or not isinstance(milestone.get("title"), str):
            raise DriftError(f"the {side} holds a milestone without a title: {milestone!r}")
        if milestone["title"] in titled:
            raise DriftError(f"the {side} lists milestone '{milestone['title']}' twice")
        titled[milestone["title"]] = milestone
    return titled


def value(milestone: dict, field: str) -> object:
    # A null and an empty description both mean that the milestone has none.
    found = milestone.get(field)
    if field == "description":
        return found or None
    return found


def differences(forge: dict[str, dict], copy: dict[str, dict]) -> list[str]:
    found = [f"milestone '{title}' is on the forge but not in the file" for title in sorted(forge.keys() - copy.keys())]
    found += [
        f"milestone '{title}' is in the file but not on the forge" for title in sorted(copy.keys() - forge.keys())
    ]
    for title in sorted(forge.keys() & copy.keys()):
        for field in FIELDS:
            if value(forge[title], field) != value(copy[title], field):
                found.append(
                    f"milestone '{title}': {field} is {value(forge[title], field)!r} on the forge "
                    f"and {value(copy[title], field)!r} in the file"
                )
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forge", required=True, type=pathlib.Path)
    parser.add_argument("--file", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        forge = by_title(json.loads(args.forge.read_text(encoding="utf-8")), "forge")
        copy = by_title(json.loads(args.file.read_text(encoding="utf-8")).get("milestones"), "file")
        found = differences(forge, copy)
    except (OSError, AttributeError, json.JSONDecodeError, DriftError) as err:
        print(f"::error::Milestone drift: {err}", file=sys.stderr)
        return 1
    for line in found:
        print(f"::error file={args.file}::{line}", file=sys.stderr)
    if found:
        print(f"{args.file} differs from the forge in {len(found)} places; copy the forge values into it.")
        return 1
    print(f"{args.file} matches the {len(forge)} milestones on the forge.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
