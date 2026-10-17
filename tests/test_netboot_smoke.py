# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Unit tests for tools/ci/netboot_smoke.py pure components.

Verifies:
- Detection of mismatch and multi-user marker lines in serial output
- QEMU network boot argument formulation (-boot n, RAM sizing, TEST-NET-1 IP range)
- Kernel command-line parameter injection for NoCloud seed
- Mismatch watcher state machine (success on mismatch, failure on premature exit or deadline)
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "netboot_smoke.py"

_spec = importlib.util.spec_from_file_location("netboot_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


@pytest.fixture(autouse=True)
def killpg_calls(monkeypatch):
    """Replace os.killpg with a recorder: these tests pass mock processes, so no real signal may go out."""
    calls = []
    monkeypatch.setattr(os, "killpg", lambda *a: calls.append(a))
    return calls


def test_mismatch_line_detection():
    clean_log = "systemd[1]: Reached target Multi-User System.\n"
    assert smoke.mismatch_line(clean_log) == ""

    err_log = (
        "dracut: Starting imago-netroot verification\n"
        "imago-netroot: root sha256 mismatch (expected: 0000000000000000, got: aaaaaaaaaaaaaaaa)\n"
        "Kernel panic - not syncing: Attempted to kill init!\n"
    )
    assert smoke.mismatch_line(err_log) == (
        "imago-netroot: root sha256 mismatch (expected: 0000000000000000, got: aaaaaaaaaaaaaaaa)"
    )


def test_inject_cmdline():
    script = (
        "#!ipxe\n"
        "kernel base-generic-netboot.vmlinuz initrd=base-generic-netboot.initrd console=ttyS0\n"
        "initrd base-generic-netboot.initrd\n"
        "boot\n"
    )
    injected = smoke.inject_cmdline(script, "ds=nocloud;s=http://192.0.2.2:8080/seed/")
    lines = injected.splitlines()
    assert lines[0] == "#!ipxe"
    assert "ds=nocloud;s=http://192.0.2.2:8080/seed/" in lines[1]
    assert lines[2] == "initrd base-generic-netboot.initrd"
    assert lines[3] == "boot"

    # Does not duplicate if already present
    duplicate_try = smoke.inject_cmdline(injected, "ds=nocloud;s=http://192.0.2.2:8080/seed/")
    assert duplicate_try == injected


def test_command_parameters(tmp_path):
    serial = tmp_path / "serial.log"
    cmd = smoke.command("qemu-system-x86_64", 8080, "base-generic", serial, "tcg")

    # Pure network boot: -boot n, no drive or disk attached
    assert "-boot" in cmd
    assert cmd[cmd.index("-boot") + 1] == "n"
    assert not any(arg.startswith("-hda") or arg.startswith("-drive") for arg in cmd)

    # RAM sizing: 4096 MiB required for concurrent diskless netboot components
    assert "-m" in cmd
    assert cmd[cmd.index("-m") + 1] == "4096"

    # RFC 5737 TEST-NET-1 (192.0.2.x) networking
    netdev = [arg for arg in cmd if arg.startswith("user,id=n0")]
    assert len(netdev) == 1
    assert "net=192.0.2.0/24" in netdev[0]
    assert "host=192.0.2.2" in netdev[0]
    assert "bootfile=http://192.0.2.2:8080/base-generic.ipxe" in netdev[0]

    # Zero RFC 1918 addresses
    for arg in cmd:
        assert not any(arg.startswith(prefix) for prefix in ["10.", "172.16.", "192.168."])


def test_watch_mismatch_returns_error_on_mismatch(tmp_path):
    serial = tmp_path / "serial.log"
    serial.write_text("imago-netroot: root sha256 mismatch\n", encoding="utf-8")
    proc = MagicMock()
    proc.poll.return_value = None

    found = smoke.watch_mismatch(proc, serial, "nonce123", timeout_s=5.0)
    assert found == "imago-netroot: root sha256 mismatch"
    # stop() lets a guest that printed its line power off: it waits, it does not kill.
    assert proc.wait.called


def test_watch_mismatch_fails_if_marker_reached(tmp_path):
    serial = tmp_path / "serial.log"
    serial.write_text("IMAGO-BOOT-OK nonce123\n", encoding="utf-8")
    proc = MagicMock()
    proc.poll.return_value = None

    with pytest.raises(smoke.BootError, match="image booted to multi-user marker despite wrong digest"):
        smoke.watch_mismatch(proc, serial, "nonce123", timeout_s=5.0)


def test_watch_mismatch_fails_on_deadline(tmp_path, monkeypatch, killpg_calls):
    serial = tmp_path / "serial.log"
    serial.write_text("kernel loading...\n", encoding="utf-8")
    proc = MagicMock()
    proc.poll.return_value = None

    monkeypatch.setattr(smoke.time, "sleep", lambda _s: None)

    with pytest.raises(smoke.BootError, match="no mismatch error line on serial console within"):
        smoke.watch_mismatch(proc, serial, "nonce123", timeout_s=0.01)
    assert killpg_calls == []
