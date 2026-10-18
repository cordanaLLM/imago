# Copyright 2026 Lusoris
"""Planted cases for the Docker daemon probe in tests/test_container_integration.py.

A fake `docker` script first on PATH plays a slow daemon, a daemon that answers on the
second call, a stopped daemon and a missing CLI; the bounds are injected small.
"""

import os
from pathlib import Path

import pytest

from tests.harness.live import REQUIRE_LIVE_ENV
from tests.test_container_integration import DockerProbe, check_docker, probe_docker

SLOW_THEN_ANSWER = """
echo call >> "{calls}"
if [ "$(wc -l < "{calls}")" -eq 1 ]; then
    sleep 5
fi
echo 29.0.0
"""


def fake_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    """Put a fake `docker` first on PATH; return the file that counts its calls."""
    calls = tmp_path / "calls"
    script = tmp_path / "bin" / "docker"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\n" + body.format(calls=calls) + "\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{script.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    return calls


def call_count(calls: Path) -> int:
    return len(calls.read_text(encoding="utf-8").splitlines())


def test_slow_daemon_exhausts_attempts(tmp_path, monkeypatch):
    calls = fake_docker(tmp_path, monkeypatch, 'echo call >> "{calls}"\nsleep 5')
    probe = probe_docker(attempt_timeout_s=0.2, attempts=2)
    assert not probe.available
    assert "no answer within 2 attempt(s) of 0.2 s" in probe.reason
    assert 0.4 <= probe.seconds < 3.0
    assert call_count(calls) == 2


def test_slow_daemon_stops_at_deadline(tmp_path, monkeypatch):
    calls = fake_docker(tmp_path, monkeypatch, 'echo call >> "{calls}"\nsleep 5')
    probe = probe_docker(attempt_timeout_s=0.3, attempts=5, deadline_s=0.5)
    assert not probe.available
    assert probe.seconds < 1.5
    assert call_count(calls) == 2, "the second attempt gets only the time left before the deadline"


def test_slow_then_answering_succeeds_on_retry(tmp_path, monkeypatch):
    calls = fake_docker(tmp_path, monkeypatch, SLOW_THEN_ANSWER)
    probe = probe_docker(attempt_timeout_s=0.2, attempts=2)
    assert probe == DockerProbe(True, probe.seconds, "")
    assert call_count(calls) == 2


def test_single_shot_probe_misses_slow_then_answering(tmp_path, monkeypatch):
    """The old probe shape (one attempt, short timeout) reports no daemon on the case the retry passes."""
    calls = fake_docker(tmp_path, monkeypatch, SLOW_THEN_ANSWER)
    probe = probe_docker(attempt_timeout_s=0.2, attempts=1)
    assert not probe.available
    assert call_count(calls) == 1


def test_daemon_down_fails_without_retry(tmp_path, monkeypatch):
    body = (
        'echo call >> "{calls}"\n'
        'echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. '
        'Is the docker daemon running?" >&2\nexit 1'
    )
    calls = fake_docker(tmp_path, monkeypatch, body)
    probe = probe_docker(attempt_timeout_s=0.2, attempts=3)
    assert not probe.available
    assert probe.reason.startswith("Cannot connect to the Docker daemon at unix:///var/run/docker.sock")
    assert call_count(calls) == 1


def test_other_error_is_retried_and_named(tmp_path, monkeypatch):
    calls = fake_docker(tmp_path, monkeypatch, 'echo call >> "{calls}"\necho "permission denied" >&2\nexit 1')
    probe = probe_docker(attempt_timeout_s=0.2, attempts=3)
    assert not probe.available
    assert probe.reason.endswith("last cause: permission denied")
    assert call_count(calls) == 3


def test_docker_cli_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert probe_docker() == DockerProbe(False, 0.0, "docker CLI not installed")


@pytest.mark.parametrize(
    ("value", "outcome"), [("1", pytest.fail.Exception), (None, pytest.skip.Exception)], ids=["ci", "workstation"]
)
def test_check_docker_names_the_cause(monkeypatch, value, outcome):
    if value is None:
        monkeypatch.delenv(REQUIRE_LIVE_ENV, raising=False)
    else:
        monkeypatch.setenv(REQUIRE_LIVE_ENV, value)
    with pytest.raises(outcome, match="planted cause"):
        check_docker(DockerProbe(False, 0.5, "planted cause"))
