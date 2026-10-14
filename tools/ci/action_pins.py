#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Fail unless every action is pinned to a real commit and the workflows pass the audits.

The check runs zizmor online with ten audits, named as in the zizmor 1.30.1 audit
documentation (https://docs.zizmor.sh/audits/):

- `unpinned-uses`: a `uses:` clause pinned to a tag or branch instead of a commit;
- `impostor-commit`: a commit that is not reachable from the named repository (it lives
  in a fork of it, or nowhere);
- `ref-version-mismatch`: a version comment that names another release than the
  pinned commit, or no release;
- `template-injection`: a `${{ }}` expression expanded inside a `run:` script;
- `excessive-permissions`: a `read-all` or `write-all` grant;
- `undocumented-permissions`: a grant beyond `contents: read` without a comment that
  says what it is for;
- `anonymous-definition`: a job without a `name:`;
- `artipacked`: a checkout that keeps the job token in `.git/config`;
- `concurrency-limits`: a workflow without a concurrency group;
- `superfluous-actions`: an action whose work a runner tool already does.

The check fails closed. It refuses to run without a GitHub token or with zizmor's
offline switches set, because `impostor-commit` needs the API. It loads no zizmor
configuration and honours no ignore comments, so the repository cannot relax a rule.
Before the real scan it audits a planted workflow outside the checkout and fails unless
each named audit reports it: an audit the pinned zizmor no longer knows, or one that
no longer reaches the API, turns the job red instead of green.

A finding the repository cannot fix yet is listed in the exception file
(`.github/zizmor-exceptions.json`): one audit, one workflow path, a reason that starts
with its category, and an expiry. The check fails on an entry that has expired, that
runs longer than its category allows, that lacks or adds a field, that names an audit
the check does not gate, that repeats another entry, or that matches no finding.

Usage:
  python3 -I tools/ci/action_pins.py --binary zizmor \
      --exceptions .github/zizmor-exceptions.json .github/workflows
"""

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

# Each audit with the fix the error line asks for.
ADVICE = {
    "anonymous-definition": "give the job a name",
    "artipacked": "set persist-credentials: false on the checkout",
    "concurrency-limits": "give the workflow a concurrency group per workflow and ref",
    "excessive-permissions": "grant the permissions the job needs, never read-all or write-all",
    "impostor-commit": "pin this action to a release commit of its repository",
    "ref-version-mismatch": "pin this action to a release commit of its repository",
    "superfluous-actions": "run the runner tool that does the same work in a script step",
    "template-injection": "pass the expression to the script through env",
    "undocumented-permissions": "say in a comment on the line what the permission is for",
    "unpinned-uses": "pin this action to a release commit of its repository",
}
AUDITS = tuple(sorted(ADVICE))
TOKEN_ENV = ("GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN")
OFFLINE_ENV = ("ZIZMOR_OFFLINE", "ZIZMOR_NO_ONLINE_AUDITS")
# zizmor exits 0 without findings and 11 to 14 by the highest severity it found.
CLEAN_EXIT = 0
FINDINGS_EXIT = range(11, 15)
SCAN_TIMEOUT_S = 600
MAX_FINDINGS = 4096
MAX_EXCEPTIONS = 256

# An exception holds exactly these fields, the shape of the Praetor engine's exceptions.
EXCEPTION_FIELDS = ("expires", "path", "reason", "rule")
# Rectification interval in days by category. Category A states its own interval in the
# reason; no entry runs longer than MAX_EXCEPTION_DAYS.
CATEGORY_DAYS = {"A": 90, "B": 3, "C": 10, "D": 120}
MAX_EXCEPTION_DAYS = 90
CATEGORY = re.compile(r"category ([ABCD]):")

# One planted defect per audit. The workflow grants write-all and has no concurrency
# group, the job has no name and an uncommented write grant, the checkout commit is v7.0.1
# under a v6.0.0 comment and keeps the token, the setup-go commit exists nowhere, the
# third step uses a tag, the fourth opens a pull request that gh does as well, and the last
# one expands the head branch name into its script.
PLANT = """\
name: plant
on: pull_request
permissions: write-all
jobs:
  plant:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v6.0.0
      - uses: actions/setup-go@0000000000000000000000000000000000000001 # v7.0.0
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: peter-evans/create-pull-request@5f6978faf089d4d20b00c7766989d076bb2fc7f1 # v8.1.1
      - run: echo "${{ github.head_ref }}"
"""


class PinCheckError(Exception):
    """The check could not establish a trustworthy result."""


def preflight(env: dict[str, str]) -> None:
    """Raise unless zizmor can run its online audits."""
    if not any(env.get(name) for name in TOKEN_ENV):
        raise PinCheckError(f"no GitHub token in {', '.join(TOKEN_ENV)}; impostor-commit needs the API")
    switched = [name for name in OFFLINE_ENV if env.get(name)]
    if switched:
        raise PinCheckError(f"{', '.join(switched)} would disable the online audits")


def command(binary: str, target: pathlib.Path) -> list[str]:
    return [
        binary, "--format", "json", "--no-config", "--no-ignores", "--no-progress",
        "--persona", "pedantic", "--strict-collection", str(target),
    ]  # fmt: skip


def scan(binary: str, target: pathlib.Path) -> list[dict]:
    """Run zizmor on the target and return its findings."""
    result = subprocess.run(
        command(binary, target), capture_output=True, text=True, timeout=SCAN_TIMEOUT_S, check=False
    )
    if result.returncode != CLEAN_EXIT and result.returncode not in FINDINGS_EXIT:
        tail = result.stderr.strip().splitlines()[-3:]
        raise PinCheckError(f"zizmor could not audit {target} (exit {result.returncode}): {' | '.join(tail)}")
    findings = json.loads(result.stdout)
    if not isinstance(findings, list):
        raise PinCheckError("zizmor output is not a JSON list")
    return [item for item in findings[:MAX_FINDINGS] if isinstance(item, dict)]


def location(finding: dict) -> tuple[str, int]:
    """Return the file and the 1-based line of the first location of a finding."""
    first = (finding.get("locations") or [{}])[0]
    path = first.get("symbolic", {}).get("key", {}).get("Local", {}).get("verbatim_path", "?")
    row = first.get("concrete", {}).get("location", {}).get("start_point", {}).get("row", -1)
    return str(path), int(row) + 1


def pin_findings(findings: list[dict]) -> list[tuple[str, str, int]]:
    """Keep the findings of the named audits as (audit, file, line)."""
    return sorted((str(item["ident"]), *location(item)) for item in findings if item.get("ident") in AUDITS)


def canary(binary: str) -> None:
    """Raise unless every named audit reports the planted workflow."""
    with tempfile.TemporaryDirectory(prefix="action-pins-canary-") as scratch:
        workflows = pathlib.Path(scratch) / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "plant.yml").write_text(PLANT, encoding="utf-8")
        found = {audit for audit, _path, _line in pin_findings(scan(binary, pathlib.Path(scratch)))}
    missing = sorted(set(AUDITS) - found)
    if missing:
        raise PinCheckError(f"zizmor did not report the planted workflow for: {', '.join(missing)}")
    print(f"action audit canary: refused {', '.join(AUDITS)}")


def refuse_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    """Build a JSON object, refusing a key that appears twice."""
    keys = [key for key, _value in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise PinCheckError(f"exception file repeats the key {', '.join(repeated)}")
    return dict(pairs)


def check_entry(entry: object, today: datetime.date) -> tuple[str, str]:
    """Return (audit, path) of a valid exception entry, or raise."""
    if not isinstance(entry, dict) or tuple(sorted(entry)) != EXCEPTION_FIELDS:
        raise PinCheckError(f"exception {entry!r} needs exactly the fields {', '.join(EXCEPTION_FIELDS)}")
    if not all(isinstance(entry[field], str) and entry[field].strip() for field in EXCEPTION_FIELDS):
        raise PinCheckError(f"exception {entry!r} has an empty or non-text field")
    rule, path = entry["rule"], entry["path"]
    if rule not in AUDITS:
        raise PinCheckError(f"exception {rule} on {path} names an audit the check does not gate")
    category = CATEGORY.match(entry["reason"])
    if not category:
        raise PinCheckError(f"exception {rule} on {path}: the reason must start with 'category A|B|C|D:'")
    expires = datetime.date.fromisoformat(entry["expires"])
    if expires < today:
        raise PinCheckError(f"exception {rule} on {path} expired on {expires}; fix the finding or renew it")
    longest = min(CATEGORY_DAYS[category.group(1)], MAX_EXCEPTION_DAYS)
    if expires > today + datetime.timedelta(days=longest):
        raise PinCheckError(f"exception {rule} on {path} runs past {longest} days for its category")
    return rule, str(pathlib.PurePosixPath(path))


def load_exceptions(source: pathlib.Path, today: datetime.date) -> dict[tuple[str, str], dict]:
    """Read the exception file and return its entries by (audit, path)."""
    entries = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=refuse_duplicate_keys)
    if not isinstance(entries, list) or len(entries) > MAX_EXCEPTIONS:
        raise PinCheckError(f"{source} must be a JSON list of at most {MAX_EXCEPTIONS} entries")
    excepted: dict[tuple[str, str], dict] = {}
    for entry in entries:
        key = check_entry(entry, today)
        if key in excepted:
            raise PinCheckError(f"exception {key[0]} on {key[1]} is listed twice")
        excepted[key] = entry
    return excepted


def split_excepted(found: list[tuple[str, str, int]], excepted: dict[tuple[str, str], dict]) -> list:
    """Print the excepted findings, refuse an entry that matches none, return the rest."""
    used = set()
    kept = []
    for audit, path, line in found:
        key = (audit, str(pathlib.PurePosixPath(path)))
        if key not in excepted:
            kept.append((audit, path, line))
            continue
        used.add(key)
        entry = excepted[key]
        print(f"::warning file={path},line={line}::{audit} excepted until {entry['expires']}: {entry['reason']}")
    unmatched = sorted(set(excepted) - used)
    if unmatched:
        names = "; ".join(f"{audit} on {path}" for audit, path in unmatched)
        raise PinCheckError(f"exception matches no finding, remove it: {names}")
    return kept


def run(binary: str, target: pathlib.Path, exceptions: pathlib.Path, today: datetime.date) -> int:
    preflight(dict(os.environ))
    excepted = load_exceptions(exceptions, today)
    canary(binary)
    found = split_excepted(pin_findings(scan(binary, target)), excepted)
    for audit, path, line in found:
        print(f"::error file={path},line={line}::{audit}: {ADVICE[audit]}")
    print(f"action audit check: {len(found)} finding(s) in {target}, {len(excepted)} excepted")
    return 1 if found else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--binary", required=True, help="zizmor executable to run")
    parser.add_argument("--exceptions", required=True, type=pathlib.Path, help="JSON list of excepted findings")
    parser.add_argument("target", type=pathlib.Path, help="workflow directory to audit")
    args = parser.parse_args(argv)
    try:
        return run(args.binary, args.target, args.exceptions, datetime.datetime.now(datetime.UTC).date())
    except (PinCheckError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"::error::action pin check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
