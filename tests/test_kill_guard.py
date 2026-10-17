# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""The process-group guard refuses every id that could signal processes beyond QEMU's group.

`os.killpg(1, sig)` is `kill(-1, sig)`. A `MagicMock` process has a pid that indexes to 1,
which once ended the desktop session from this suite. Every refusal test runs with
`os.killpg` replaced by a recorder, so a broken guard records the call instead of making it.
"""

from __future__ import annotations

import importlib.util
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.aegis import boot_once

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


boot_smoke = _load("boot_smoke")
netboot_smoke = _load("netboot_smoke")


@pytest.fixture
def killpg_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(os, "killpg", lambda *a: calls.append(a))
    return calls


def test_mock_process_is_refused(killpg_calls):
    """Planted case: the exact shape that killed the session sends no signal."""
    proc = MagicMock()
    assert boot_smoke.signal_group(proc.pid) is False
    netboot_smoke.kill_process_group(proc)
    boot_once.kill_process_group(proc.pid)
    assert killpg_calls == []
    assert proc.kill.called


@pytest.mark.parametrize("pgid", [1, 0, -1, -4242, True, False, 2.0, "1234", None])
def test_unsafe_ids_are_refused(killpg_calls, pgid):
    assert boot_smoke.signal_group(pgid) is False
    boot_once.kill_process_group(pgid)
    assert killpg_calls == []


def test_own_group_is_refused(killpg_calls):
    own = os.getpgrp()
    assert boot_smoke.signal_group(own) is False
    boot_once.kill_process_group(own)
    assert killpg_calls == []


def test_boundary_two_is_the_first_id_signalled(killpg_calls):
    if os.getpgrp() == 2:
        pytest.skip("this process leads group 2")
    assert boot_smoke.signal_group(2, signal.SIGTERM) is True
    assert killpg_calls == [(2, signal.SIGTERM)]


def test_real_child_group_is_killed():
    """Positive case with a real process: a child in its own session dies, the caller lives."""
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        assert boot_smoke.signal_group(child.pid) is True
        assert child.wait(timeout=10) == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
