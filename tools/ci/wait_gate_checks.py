#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Wait for every gate check on a commit and fail unless each one succeeds (ADR-0036).

The required-checks job ran lewagon/wait-on-check-action under a 30-minute job bound. That
bound counted the time a check sat queued for a runner: on 2026-10-19 five gate checks of
pull request #182 waited up to 62 minutes for a runner, the job was cancelled after 30, and
every gate check passed later (run 39190971221). This script keeps the action's rules and
moves the clocks:

- a check counts once a workflow created it; the newest run per name decides, the job that
  runs this script is left out, and `--keep` (a Python pattern) names the gate checks;
- once every gate check has completed, a conclusion other than `success` fails the wait;
  as in the action, no conclusion is judged earlier, because the CodeQL check of code
  scanning is updated in place while its analyses upload (run 39198928256);
- a check runs at most `GATE_RUN_MINUTES` from its own `started_at`, counted only while
  it is `in_progress`: a queued check run already carries its creation time as
  `started_at`, and the forge moves it to the job start (run 39204073732 failed five gate
  checks queued since 05:20Z at 05:51Z), so time spent queued never counts;
- the whole wait ends at `OUTER_MINUTES` of wall clock, so a check that never starts fails
  the wait instead of holding it open; the job bound sits a few minutes above it.

Usage:
  GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
      python3 -I tools/ci/wait_gate_checks.py --ref <sha> --own required-checks --keep '<pattern>'
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

# Gate jobs carry timeout-minutes of 30 at most, so a running check past 30 minutes is stuck.
GATE_RUN_MINUTES = 30
# Runner backlog held gate checks queued for up to 62 minutes on 2026-10-19; 120 minutes
# leaves that backlog room twice over and still ends a wait on a check that never starts.
OUTER_MINUTES = 120
POLL_S = 20
MAX_POLLS = OUTER_MINUTES * 60 // POLL_S + 1
MAX_PAGES = 5
PER_PAGE = 100
TIMEOUT_SECONDS = 30
MAX_API_ERRORS = 3
API = "https://api.github.com"


def parse_time(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def newest_gate_checks(runs: list[dict], keep: re.Pattern[str], own: str) -> dict[str, dict]:
    """The newest run per check name among the gate checks, without this job's own check."""
    newest: dict[str, dict] = {}
    for run in runs:
        name = run["name"]
        if name == own or not keep.search(name):
            continue
        if name not in newest or run["id"] > newest[name]["id"]:
            newest[name] = run
    return newest


def verdict(checks: dict[str, dict], now: datetime.datetime) -> tuple[str, str]:
    """`pass`, `fail` or `wait` for the gate checks at `now`, with the reason."""
    bound = datetime.timedelta(minutes=GATE_RUN_MINUTES)
    stuck = [
        n
        for n, r in checks.items()
        if r["status"] == "in_progress" and r.get("started_at") and now - parse_time(r["started_at"]) > bound
    ]
    if stuck:
        return "fail", f"running longer than {GATE_RUN_MINUTES} min: " + ", ".join(sorted(stuck))
    open_checks = sorted(n for n, r in checks.items() if r["status"] != "completed")
    if open_checks:
        return "wait", "waiting for: " + ", ".join(open_checks)
    if not checks:
        return "wait", "no gate check reported yet"
    failed = sorted(f"{n} ({r['conclusion']})" for n, r in checks.items() if r["conclusion"] != "success")
    if failed:
        return "fail", "did not succeed: " + ", ".join(failed)
    return "pass", f"{len(checks)} gate checks succeeded"


def https_opener() -> urllib.request.OpenerDirector:
    """Return an opener that speaks HTTPS only: no file://, ftp:// or plain http:// handler."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def fetch_runs(repo: str, ref: str, token: str) -> list[dict]:
    """Every check run on ref, read page by page up to MAX_PAGES."""
    runs: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{API}/repos/{repo}/commits/{ref}/check-runs?per_page={PER_PAGE}&page={page}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with https_opener().open(request, timeout=TIMEOUT_SECONDS) as response:
            batch = json.load(response)["check_runs"]
        runs += batch
        if len(batch) < PER_PAGE:
            return runs
    raise RuntimeError(f"more than {MAX_PAGES * PER_PAGE} check runs on {ref}")


class Clock:
    """Wall clock and sleep; the tests pass a simulated one."""

    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def wait(fetch: Callable[[], list[dict]], keep: re.Pattern[str], own: str, clock: Clock) -> int:
    """Poll fetch until the gate checks pass or fail, or OUTER_MINUTES of wall clock end."""
    deadline = clock.monotonic() + OUTER_MINUTES * 60
    errors = 0
    reason = "no poll ran"
    for _ in range(MAX_POLLS):
        try:
            runs = fetch()
            errors = 0
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as err:
            errors += 1
            print(f"::warning::check-runs read failed ({errors}/{MAX_API_ERRORS}): {err}")
            if errors >= MAX_API_ERRORS:
                print(f"::error::check-runs read failed {errors} times in a row", file=sys.stderr)
                return 1
            runs = None
        if runs is not None:
            state, reason = verdict(newest_gate_checks(runs, keep, own), clock.now())
            print(f"{state}: {reason}")
            if state == "pass":
                return 0
            if state == "fail":
                print(f"::error::{reason}", file=sys.stderr)
                return 1
        if clock.monotonic() + POLL_S > deadline:
            break
        clock.sleep(POLL_S)
    print(f"::error::gate checks not done after {OUTER_MINUTES} min; {reason}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", required=True)
    parser.add_argument("--own", required=True)
    parser.add_argument("--keep", required=True)
    args = parser.parse_args(argv)
    # The job log stamps each line when it arrives; unbuffered lines keep the poll times.
    sys.stdout.reconfigure(line_buffering=True)
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print("::error::GITHUB_TOKEN and GITHUB_REPOSITORY must be set", file=sys.stderr)
        return 1
    keep = re.compile(args.keep)
    return wait(lambda: fetch_runs(repo, args.ref, token), keep, args.own, Clock())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
