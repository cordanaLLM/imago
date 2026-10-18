# Copyright 2026 Lusoris
"""Verification that a missing live-test prerequisite fails in CI and skips elsewhere.

`tests/harness/live.py` turns a missing Docker daemon, a missing bash and a preparation
step that exceeds its bound into a skip on a workstation and into a failure when
IMAGO_REQUIRE_LIVE_TESTS=1, which the pytest job of ci.yml sets. Each case below plants
the missing prerequisite and checks both outcomes.
"""

from pathlib import Path

import pytest

from tests.harness.live import REQUIRE_LIVE_ENV, live_tests_required, skip_or_fail
from tests.harness.mock_runner import GIT_BASH
from tests.test_container_integration import DockerProbe, check_docker, run_preparation
from tests.test_provisioners_execution import check_bash

SKIPPED = pytest.skip.Exception
FAILED = pytest.fail.Exception
# A preparation step that cannot finish within the bound given to it.
SLOW_STEP = ["sleep", "5"]
SLOW_STEP_BOUND_S = 0.05


@pytest.mark.parametrize(
    ("environ", "required"),
    [
        ({REQUIRE_LIVE_ENV: "1"}, True),
        ({}, False),
        ({REQUIRE_LIVE_ENV: ""}, False),
        ({REQUIRE_LIVE_ENV: "0"}, False),
        ({REQUIRE_LIVE_ENV: "true"}, False),
        ({REQUIRE_LIVE_ENV: " 1"}, False),
    ],
    ids=["one", "unset", "empty", "zero", "true", "padded"],
)
def test_only_exactly_one_requires_live_tests(environ, required):
    assert live_tests_required(environ) is required


def test_skip_or_fail_skips_outside_ci():
    with pytest.raises(SKIPPED, match="^no daemon$"):
        skip_or_fail("no daemon", {})


def test_skip_or_fail_fails_in_ci():
    with pytest.raises(FAILED, match=f"^no daemon; {REQUIRE_LIVE_ENV}=1 requires this test to run$"):
        skip_or_fail("no daemon", {REQUIRE_LIVE_ENV: "1"})


@pytest.mark.parametrize(("value", "outcome"), [("1", FAILED), (None, SKIPPED)], ids=["ci", "workstation"])
def test_missing_docker(monkeypatch, value, outcome):
    set_mode(monkeypatch, value)
    with pytest.raises(outcome, match="Docker daemon is required.*docker CLI not installed"):
        check_docker(DockerProbe(False, 0.0, "docker CLI not installed"))


def test_available_docker_neither_skips_nor_fails(monkeypatch):
    set_mode(monkeypatch, "1")
    assert check_docker(DockerProbe(True, 0.05, "")) is None


@pytest.mark.parametrize("bash", [None, Path("/nonexistent/imago/bash")], ids=["none", "absent-path"])
@pytest.mark.parametrize(("value", "outcome"), [("1", FAILED), (None, SKIPPED)], ids=["ci", "workstation"])
def test_missing_bash(monkeypatch, bash, value, outcome):
    set_mode(monkeypatch, value)
    with pytest.raises(outcome, match="Bash required for mock execution tests"):
        check_bash(bash)


def test_present_bash_neither_skips_nor_fails(monkeypatch):
    set_mode(monkeypatch, "1")
    assert GIT_BASH is not None
    assert check_bash(GIT_BASH) is None


@pytest.mark.parametrize(("value", "outcome"), [("1", FAILED), (None, SKIPPED)], ids=["ci", "workstation"])
def test_preparation_beyond_its_bound(monkeypatch, value, outcome):
    set_mode(monkeypatch, value)
    with pytest.raises(outcome, match=r"planted step did not finish within 0\.05 s on this host"):
        run_preparation(SLOW_STEP, SLOW_STEP_BOUND_S, "planted step")


def test_preparation_within_its_bound_returns_the_result(monkeypatch):
    set_mode(monkeypatch, "1")
    res = run_preparation(["true"], 30, "quick step")
    assert res.returncode == 0


def set_mode(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(REQUIRE_LIVE_ENV, raising=False)
    else:
        monkeypatch.setenv(REQUIRE_LIVE_ENV, value)
