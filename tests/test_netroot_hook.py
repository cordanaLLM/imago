# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""The imago-netroot hook refuses every root image whose sha256 is not the one on the command line.

The hook is taken from what `80-netboot-initrd.sh` writes, then run with `sh` against
stand-ins for `/proc/cmdline`, `/dev/kmsg`, dracut's `die()` and the original
`dmsquash-live-root`, so the test runs the exact text the initrd carries.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.harness.mock_runner import GIT_BASH, MockSandbox
from tests.test_provisioners_execution import PROVISIONERS_DIR, check_bash

HOOK = "usr/lib/dracut/modules.d/95imago-netroot/imago-netroot-verify.sh"
ROOT_BYTES = b"imago test root image\n"
GOOD = hashlib.sha256(ROOT_BYTES).hexdigest()


@pytest.fixture(scope="module")
def hook_text(tmp_path_factory) -> str:
    check_bash(GIT_BASH)
    res = MockSandbox(tmp_path_factory.mktemp("prov")).run_script(PROVISIONERS_DIR / "80-netboot-initrd.sh")
    assert res.returncode == 0, res.stderr
    text = res.read_file(HOOK)
    assert text is not None
    return text


def run_hook(hook_text: str, tmp_path: Path, cmdline: str, image: str | None = "root.squashfs"):
    if shutil.which("sh") is None:
        pytest.skip("no POSIX sh")
    (tmp_path / "root.squashfs").write_bytes(ROOT_BYTES)
    (tmp_path / "cmdline").write_text(cmdline + "\n", encoding="utf-8")
    (tmp_path / "kmsg").write_text("", encoding="utf-8")
    (tmp_path / "lib.sh").write_text(f'die() {{ echo "DIE $*" >> "{tmp_path}/died"; exit 1; }}\n', encoding="utf-8")
    orig = tmp_path / "orig.sh"
    orig.write_text(f'#!/bin/sh\necho "ORIG $*" > "{tmp_path}/orig.out"\n', encoding="utf-8")
    orig.chmod(0o755)
    text = (
        hook_text.replace("/proc/cmdline", str(tmp_path / "cmdline"))
        .replace("/dev/kmsg", str(tmp_path / "kmsg"))
        .replace("/lib/dracut-lib.sh", str(tmp_path / "lib.sh"))
        .replace("/sbin/dmsquash-live-root.orig", str(orig))
    )
    hook = tmp_path / "hook.sh"
    hook.write_text(text, encoding="utf-8")
    args = ["sh", str(hook)] + ([str(tmp_path / image)] if image else [])
    proc = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
    died = tmp_path / "died"
    ran = tmp_path / "orig.out"
    return proc, died.read_text() if died.exists() else "", ran.exists(), (tmp_path / "kmsg").read_text()


def test_matching_digest_hands_the_image_to_dmsquash_live(hook_text, tmp_path):
    proc, died, ran, kmsg = run_hook(hook_text, tmp_path, f"ip=dhcp imago.root-sha256={GOOD} console=ttyS0")
    assert proc.returncode == 0, proc.stderr
    assert died == "" and ran
    assert f"imago-netroot: root sha256 verified {GOOD}" in kmsg


@pytest.mark.parametrize(
    ("cmdline", "reason"),
    [
        (f"imago.root-sha256={'0' * 64}", "mismatch"),
        ("ip=dhcp console=ttyS0", "missing"),
        ("imago.root-sha256=", "missing"),
        (f"imago.root-sha256={GOOD[:63]}", "malformed"),
        (f"imago.root-sha256={GOOD}0", "malformed"),
        (f"imago.root-sha256={GOOD.upper()}", "malformed"),
        ("imago.root-sha256=skip", "malformed"),
        (f"imago.root-sha256={GOOD[:62]}*g", "malformed"),
    ],
    ids=["mismatch", "absent", "empty", "63-hex", "65-hex", "uppercase", "skip-word", "glob"],
)
def test_refused_digest_dies_before_mount(hook_text, tmp_path, cmdline, reason):
    proc, died, ran, kmsg = run_hook(hook_text, tmp_path, cmdline)
    assert proc.returncode != 0
    assert not ran, "dmsquash-live-root ran despite a refused digest"
    assert f"DIE imago-netroot: root sha256 {reason}" in died
    assert f"imago-netroot: root sha256 {reason}" in kmsg


def test_unreadable_image_dies(hook_text, tmp_path):
    proc, died, ran, _ = run_hook(hook_text, tmp_path, f"imago.root-sha256={GOOD}", image="absent.squashfs")
    assert proc.returncode != 0 and not ran
    assert "image unreadable" in died


def test_hook_has_no_skip_path(hook_text):
    """The only exits are die() and the exec of the original; no option bypasses the check."""
    assert hook_text.count("exec ") == 1
    assert "exit 0" not in hook_text
    for word in ("skip", "ignore", "insecure", "getargbool"):
        assert word not in hook_text
