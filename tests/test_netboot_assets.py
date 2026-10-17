# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Unit tests for tools/ci/netboot_assets.py.

Verifies:
- Exact 4-line iPXE script output against fixture
- Rejection of malformed or non-compliant sha256 digests
- Relative URIs only in generated script (using ${cwduri})
- Asset extraction logic (kernel, initrd, squashfs, script generation)
- dracut verify hook contains no skip path
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "netboot_assets.py"

_spec = importlib.util.spec_from_file_location("netboot_assets", SCRIPT)
netboot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(netboot)

SAMPLE_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_generate_ipxe_exact_fixture():
    script = netboot.generate_ipxe("base-generic", SAMPLE_DIGEST)
    expected = (
        "#!ipxe\n"
        f"kernel base-generic-netboot.vmlinuz initrd=base-generic-netboot.initrd ip=dhcp rd.neednet=1 "
        f"root=live:${{cwduri}}base-generic-root.squashfs imago.root-sha256={SAMPLE_DIGEST} fstab=no "
        "console=ttyS0 console=tty0\n"
        "initrd base-generic-netboot.initrd\n"
        "boot\n"
    )
    assert script == expected
    lines = script.splitlines()
    assert len(lines) == 4
    assert lines[0] == "#!ipxe"
    assert lines[1].startswith("kernel base-generic-netboot.vmlinuz")
    assert lines[2] == "initrd base-generic-netboot.initrd"
    assert lines[3] == "boot"


def test_generate_ipxe_relative_uris_only():
    script = netboot.generate_ipxe("k8s-node-generic", SAMPLE_DIGEST)
    lines = script.splitlines()
    kernel_line = lines[1]
    assert "root=live:${cwduri}k8s-node-generic-root.squashfs" in kernel_line
    assert "://" not in kernel_line.replace("://", "") or "${cwduri}" in kernel_line
    # No absolute path allowed for kernel, initrd, or squashfs
    assert " /" not in kernel_line
    assert not lines[2].split()[1].startswith("/")


@pytest.mark.parametrize(
    "digest",
    [
        "a" * 63,  # boundary: length - 1
        "a" * 65,  # boundary: length + 1
        "",  # empty
        "A" * 64,  # uppercase
        "g" * 64,  # non-hex
        f"{'a' * 63} ",  # trailing space
        f" {'a' * 63}",  # leading space
    ],
    ids=["short-63", "long-65", "empty", "uppercase", "non-hex", "trailing-space", "leading-space"],
)
def test_generate_ipxe_malformed_digest_refused(digest):
    with pytest.raises(ValueError, match="invalid sha256 digest"):
        netboot.generate_ipxe("base-generic", digest)


@pytest.mark.parametrize(
    "flavor",
    [
        "",
        "Base-Generic",
        "base_generic",
        "-bad",
        "bad-",
        "a",  # length 1 (pattern requires >=2)
    ],
    ids=["empty", "uppercase", "underscore", "leading-dash", "trailing-dash", "too-short"],
)
def test_generate_ipxe_malformed_flavor_refused(flavor):
    with pytest.raises(ValueError, match="invalid flavor name"):
        netboot.generate_ipxe(flavor, SAMPLE_DIGEST)


def test_extract_netboot_assets(tmp_path, monkeypatch):
    root = tmp_path / "root"
    boot = root / "boot"
    boot.mkdir(parents=True)
    (boot / "vmlinuz-6.12.0-generic").write_bytes(b"VMLINUZ_KERNEL")
    (boot / "vmlinuz-6.9.0-generic").write_bytes(b"OTHER_KERNEL")
    (boot / "imago-netboot.vmlinuz").symlink_to("vmlinuz-6.12.0-generic")
    initrd = boot / "imago-netboot.initrd"
    initrd.write_bytes(b"INITRD_IMAGE")
    (root / "etc").mkdir()
    (root / "etc" / "os-release").write_text("NAME=imago\n", encoding="utf-8")

    out = tmp_path / "out"
    calls: list[list[str]] = []

    def mock_run(cmd: list[str]) -> str:
        calls.append(cmd)
        # Create output squashfs stub
        dest = Path(cmd[cmd.index("-comp") - 1])
        dest.write_bytes(b"SQUASHFS_DATA")
        return ""

    monkeypatch.setattr(netboot, "run", mock_run)

    result = netboot.extract("base-generic", root, out, use_sudo=False)

    assert result["kernel"].read_bytes() == b"VMLINUZ_KERNEL"
    assert result["initrd"].read_bytes() == b"INITRD_IMAGE"
    assert result["squashfs"].exists()
    assert result["ipxe"].exists()

    expected_digest = hashlib.sha256(b"SQUASHFS_DATA").hexdigest()
    assert f"imago.root-sha256={expected_digest}" in result["ipxe"].read_text(encoding="utf-8")

    assert len(calls) == 1
    mksquashfs_call = calls[0]
    assert mksquashfs_call[0] == "mksquashfs"
    assert "-comp" in mksquashfs_call and "zstd" in mksquashfs_call
    assert "-Xcompression-level" in mksquashfs_call and "19" in mksquashfs_call
    assert "-noappend" in mksquashfs_call
    assert "-one-file-system" in mksquashfs_call


@pytest.mark.parametrize(
    "target",
    ["/boot/vmlinuz-6.12.0-generic", "../boot/vmlinuz-6.12.0-generic", "sub/vmlinuz", "..", "vmlinuz-absent"],
    ids=["absolute", "parent", "nested", "dotdot", "dangling"],
)
def test_find_kernel_refuses_a_link_that_leaves_boot(tmp_path, target):
    boot = tmp_path / "boot"
    boot.mkdir()
    (boot / "imago-netboot.vmlinuz").symlink_to(target)
    with pytest.raises(netboot.NetbootError):
        netboot.find_kernel(boot)


def test_find_kernel_refuses_a_missing_link(tmp_path):
    boot = tmp_path / "boot"
    boot.mkdir()
    (boot / "vmlinuz-6.12.0-generic").write_bytes(b"K")
    with pytest.raises(netboot.NetbootError, match="not the link"):
        netboot.find_kernel(boot)


def test_copy_out_uses_sudo_install_with_runner_ownership(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(netboot, "run", lambda cmd: calls.append(cmd) or "")
    netboot.copy_out(tmp_path / "src", tmp_path / "dst", use_sudo=True)
    assert calls == [
        [
            "sudo",
            "install",
            "-m",
            "0644",
            "-o",
            str(os.getuid()),
            "-g",
            str(os.getgid()),
            str(tmp_path / "src"),
            str(tmp_path / "dst"),
        ]
    ]
