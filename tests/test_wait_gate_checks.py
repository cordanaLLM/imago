# Copyright 2026 Lusoris
"""Verification of the required-checks wait clocks (ADR-0036).

tools/ci/wait_gate_checks.py polls the check runs of a commit. The tests feed it a
simulated forge and a simulated clock: a gate check that sits queued for 40 minutes and
then succeeds must pass, a gate check that never starts must fail at the 120-minute outer
bound, and a check that runs past its own 30-minute bound or ends in any conclusion other
than success must fail.
"""

from __future__ import annotations

import datetime
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "wait_gate_checks.py"
WORKFLOW = ROOT / ".github" / "workflows" / "required-aggregator.yml"
# The outer bound the order sets (ADR-0036); the script must end its wait there.
OUTER_MINUTES = 120

_spec = importlib.util.spec_from_file_location("wait_gate_checks", SCRIPT)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

START = datetime.datetime(2026, 10, 19, 3, 0, tzinfo=datetime.UTC)
KEEP = re.compile(r"^(?!Build Image \()")
OWN = "required-checks"


class SimClock:
    """A clock that moves only when the wait sleeps."""

    def __init__(self) -> None:
        self.elapsed = 0.0

    def monotonic(self) -> float:
        return self.elapsed

    def now(self) -> datetime.datetime:
        return START + datetime.timedelta(seconds=self.elapsed)

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds


def stamp(minutes: float) -> str:
    return (START + datetime.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def check(
    name: str, clock: SimClock, queued: float, runs: float | None, *, conclusion: str = "success", run_id: int = 1
):
    """One check run as the forge reports it at the clock's time.

    It is queued until minute `queued`, then runs for `runs` minutes (None = never ends).
    """
    minute = clock.elapsed / 60
    if minute < queued:
        return {"id": run_id, "name": name, "status": "queued", "conclusion": None, "started_at": None}
    if runs is None or minute < queued + runs:
        return {"id": run_id, "name": name, "status": "in_progress", "conclusion": None, "started_at": stamp(queued)}
    return {"id": run_id, "name": name, "status": "completed", "conclusion": conclusion, "started_at": stamp(queued)}


def run_wait(forge) -> tuple[int, float]:
    clock = SimClock()
    code = gate.wait(lambda: forge(clock), KEEP, OWN, clock)
    return code, clock.elapsed / 60


def test_gate_queued_40_minutes_then_green_passes():
    """Planted: the #182 shape, a gate check waiting for a runner past the old 30-min bound."""
    code, minutes = run_wait(lambda c: [check("Go Build & Unit Tests", c, 0, 3), check("Pytest", c, 40, 4)])
    assert code == 0
    assert 44 <= minutes < 46


def test_gate_never_started_fails_at_outer_bound():
    code, minutes = run_wait(lambda c: [check("Go Build & Unit Tests", c, 0, 3), check("Pytest", c, 10**6, 4)])
    assert code == 1
    assert OUTER_MINUTES - 1 <= minutes <= OUTER_MINUTES


def test_gate_running_past_its_own_bound_fails():
    code, minutes = run_wait(lambda c: [check("Pytest", c, 50, None)])
    assert code == 1
    assert 50 + gate.GATE_RUN_MINUTES <= minutes < 50 + gate.GATE_RUN_MINUTES + 1


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", "neutral", "timed_out"])
def test_gate_with_other_conclusion_fails(conclusion):
    code, _ = run_wait(lambda c: [check("Pytest", c, 0, 2, conclusion=conclusion)])
    assert code == 1


def test_conclusion_is_judged_only_when_every_check_completed():
    """Planted: the CodeQL check of code scanning reads non-success while other checks still run."""

    def forge(c):
        codeql = check("CodeQL", c, 0, 1, conclusion="neutral" if c.elapsed < 600 else "success")
        return [codeql, check("Pytest", c, 0, 12)]

    code, minutes = run_wait(forge)
    assert code == 0
    assert minutes >= 12


def test_failure_is_reported_once_every_check_completed():
    code, minutes = run_wait(lambda c: [check("Go", c, 0, 1, conclusion="failure"), check("Pytest", c, 0, 12)])
    assert code == 1
    assert minutes >= 12


def test_own_check_and_excluded_names_do_not_hold_the_wait():
    code, _ = run_wait(
        lambda c: [
            check("Pytest", c, 0, 2),
            check(OWN, c, 0, None),
            check("Build Image (base-generic)", c, 0, None),
        ]
    )
    assert code == 0


def test_newest_run_per_name_decides():
    code, _ = run_wait(
        lambda c: [check("Pytest", c, 0, 1, conclusion="cancelled", run_id=1), check("Pytest", c, 0, 2, run_id=2)]
    )
    assert code == 0


def test_no_gate_check_yet_waits_and_then_passes():
    code, minutes = run_wait(lambda c: [] if c.elapsed < 120 else [check("Pytest", c, 2, 1)])
    assert code == 0
    assert minutes >= 3


def test_repeated_read_errors_fail():
    def forge(_clock):
        raise TimeoutError("read timed out")

    code, minutes = run_wait(forge)
    assert code == 1
    assert minutes < 2


def test_poll_count_covers_the_outer_bound():
    assert gate.MAX_POLLS * gate.POLL_S >= gate.OUTER_MINUTES * 60


def test_job_bound_sits_just_above_the_outer_bound():
    """The job bound must not cut the wait short, nor leave a stuck wait running for long."""
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["required-checks"]
    assert OUTER_MINUTES < job["timeout-minutes"] <= OUTER_MINUTES + 10
