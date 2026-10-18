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
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "ci" / "netboot_smoke.py"

_spec = importlib.util.spec_from_file_location("netboot_smoke", TOOL)
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


SCRIPT = (
    "#!ipxe\nkernel f-netboot.vmlinuz initrd=f-netboot.initrd imago.root-sha256="
    + "a" * 64
    + "\ninitrd f-netboot.initrd\nboot\n"
)


def test_boot_script_adds_the_seed_and_keeps_the_digest():
    script = smoke.boot_script(SCRIPT, "ds=nocloud;s=http://192.0.2.2:1/seed/", expect_mismatch=False)
    assert "imago.root-sha256=" + "a" * 64 + " ds=nocloud;s=http://192.0.2.2:1/seed/" in script


def test_boot_script_replaces_the_digest_for_the_negative_run():
    script = smoke.boot_script(SCRIPT, "ds=x", expect_mismatch=True)
    assert "a" * 64 not in script
    assert "imago.root-sha256=" + "0" * 64 in script


@pytest.mark.parametrize("digest", ["", "0" * 64], ids=["absent", "already-wrong"])
def test_boot_script_refuses_a_negative_run_that_changes_nothing(digest):
    script = SCRIPT.replace("imago.root-sha256=" + "a" * 64, f"imago.root-sha256={digest}" if digest else "")
    with pytest.raises(smoke.BootError):
        smoke.boot_script(script, "ds=x", expect_mismatch=True)


def test_stage_links_assets_and_leaves_the_asset_directory_alone(tmp_path):
    assets = tmp_path / "assets"
    staging = tmp_path / "staging"
    assets.mkdir()
    staging.mkdir()
    for name in ("f-netboot.vmlinuz", "f-netboot.initrd", "f-root.squashfs"):
        (assets / name).write_bytes(name.encode())
    (assets / "f.ipxe").write_text(SCRIPT, encoding="utf-8")
    before = sorted(p.name for p in assets.iterdir())
    assert smoke.stage(assets, staging, "f") == SCRIPT
    assert (staging / "f-root.squashfs").read_bytes() == b"f-root.squashfs"
    assert sorted(p.name for p in assets.iterdir()) == before
    assert (assets / "f.ipxe").read_text(encoding="utf-8") == SCRIPT


def test_stage_refuses_a_missing_asset(tmp_path):
    (tmp_path / "f.ipxe").write_text(SCRIPT, encoding="utf-8")
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(smoke.BootError, match="f-netboot.vmlinuz"):
        smoke.stage(tmp_path, staging, "f")


def test_script_runs_isolated_from_a_foreign_directory(tmp_path):
    """The workflow calls python3 -I tools/ci/netboot_smoke.py; the sibling import must hold there."""
    result = subprocess.run(
        [sys.executable, "-I", str(TOOL), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--expect-mismatch" in result.stdout


def test_cleanup_reports_a_qemu_that_is_not_reaped(capsys):
    process = MagicMock()
    process.pid = 0  # refused by the guard, so no signal is sent
    process.wait.side_effect = smoke.subprocess.TimeoutExpired("qemu", 1)
    smoke.kill_process_group(process)
    assert "QEMU pid 0 not reaped" in capsys.readouterr().err


def test_cleanup_is_quiet_for_a_qemu_that_already_exited(capsys):
    process = MagicMock()
    process.pid = 0
    process.kill.side_effect = ProcessLookupError()
    smoke.kill_process_group(process)
    assert capsys.readouterr().err == ""
