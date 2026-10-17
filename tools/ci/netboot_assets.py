#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Generate iPXE scripts and extract standalone netboot assets from mounted images.

Four assets are published per flavor:
  1. <flavor>-netboot.vmlinuz: the distribution kernel
  2. <flavor>-netboot.initrd: the dracut-built netboot initrd containing imago-netroot
  3. <flavor>-root.squashfs: the Zstandard-compressed root filesystem
  4. <flavor>.ipxe: the boot script resolving assets via relative URIs and ${cwduri}

Usage:
  python3 -I tools/ci/netboot_assets.py generate --flavor FLAVOR --digest SHA256 --out SCRIPT.ipxe
  python3 -I tools/ci/netboot_assets.py extract --flavor FLAVOR --root ROOT_DIR --out OUT_DIR
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys

COMMAND_TIMEOUT_S = 1800
CHUNK_BYTES = 64 * 1024
FLAVOR_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class NetbootError(Exception):
    """A netboot asset that cannot be generated, extracted, or validated."""


def run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_S,
        check=False,
    )
    if result.returncode != 0:
        raise NetbootError(f"{' '.join(command[:3])} exited {result.returncode}: {result.stderr.strip()[:400]}")
    return result.stdout


def validate_flavor(flavor: str) -> str:
    if not FLAVOR_PATTERN.fullmatch(flavor):
        raise ValueError(f"invalid flavor name: {flavor!r}")
    return flavor


def validate_digest(digest: str) -> str:
    if not DIGEST_PATTERN.fullmatch(digest):
        raise ValueError(f"invalid sha256 digest (expected 64 lowercase hex): {digest!r}")
    return digest


def generate_ipxe(flavor: str, digest: str) -> str:
    """Generate exact 4-line iPXE script with relative URIs and verified digest."""
    valid_flavor = validate_flavor(flavor)
    valid_digest = validate_digest(digest)
    lines = [
        "#!ipxe",
        (
            f"kernel {valid_flavor}-netboot.vmlinuz "
            f"initrd={valid_flavor}-netboot.initrd ip=dhcp rd.neednet=1 "
            f"root=live:${{cwduri}}{valid_flavor}-root.squashfs "
            f"imago.root-sha256={valid_digest} "
            "console=ttyS0 console=tty0"
        ),
        f"initrd {valid_flavor}-netboot.initrd",
        "boot",
    ]
    return "\n".join(lines) + "\n"


def compute_sha256(path: pathlib.Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK_BYTES):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_kernel(boot_dir: pathlib.Path) -> pathlib.Path:
    """Return the kernel /boot/imago-netboot.vmlinuz names, the one the initrd was built for.

    The link is read inside the mounted image: an absolute or nested target would resolve
    on the runner, so only a plain file name in the same directory is accepted.
    """
    link = boot_dir / "imago-netboot.vmlinuz"
    if not link.is_symlink():
        raise NetbootError(f"{link} is not the link 80-netboot-initrd.sh writes")
    target = os.readlink(link)
    if not target or "/" in target or target in (".", ".."):
        raise NetbootError(f"{link} points outside {boot_dir}: {target!r}")
    kernel = boot_dir / target
    if kernel.is_symlink() or not kernel.is_file():
        raise NetbootError(f"{link} names no regular kernel file: {target!r}")
    return kernel


def copy_out(source: pathlib.Path, dest: pathlib.Path, *, use_sudo: bool) -> None:
    """Copy a root-only image file out as a 0644 file the runner user owns."""
    if not use_sudo:
        shutil.copyfile(source, dest)
        return
    owner = [str(os.getuid()), str(os.getgid())]
    run(["sudo", "install", "-m", "0644", "-o", owner[0], "-g", owner[1], str(source), str(dest)])


def find_netboot_initrd(boot_dir: pathlib.Path) -> pathlib.Path:
    initrd = boot_dir / "imago-netboot.initrd"
    if not initrd.is_file():
        raise NetbootError(f"imago-netboot.initrd not found in {boot_dir}")
    return initrd


def extract(
    flavor: str,
    root_dir: pathlib.Path,
    out_dir: pathlib.Path,
    *,
    use_sudo: bool = True,
) -> dict[str, pathlib.Path]:
    valid_flavor = validate_flavor(flavor)
    if not root_dir.is_dir():
        raise NetbootError(f"root directory does not exist: {root_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    boot_dir = root_dir / "boot"
    kernel_src = find_kernel(boot_dir)
    initrd_src = find_netboot_initrd(boot_dir)

    kernel_dst = out_dir / f"{valid_flavor}-netboot.vmlinuz"
    initrd_dst = out_dir / f"{valid_flavor}-netboot.initrd"
    squashfs_dst = out_dir / f"{valid_flavor}-root.squashfs"
    ipxe_dst = out_dir / f"{valid_flavor}.ipxe"

    copy_out(kernel_src, kernel_dst, use_sudo=use_sudo)
    copy_out(initrd_src, initrd_dst, use_sudo=use_sudo)

    # Pack root filesystem into squashfs with Zstandard level 19
    mksquashfs = ["sudo", "mksquashfs"] if use_sudo else ["mksquashfs"]
    cmd = [
        *mksquashfs,
        str(root_dir),
        str(squashfs_dst),
        "-comp",
        "zstd",
        "-Xcompression-level",
        "19",
        "-noappend",
    ]
    run(cmd)

    digest = compute_sha256(squashfs_dst)
    script = generate_ipxe(valid_flavor, digest)
    ipxe_dst.write_text(script, encoding="utf-8")

    return {
        "kernel": kernel_dst,
        "initrd": initrd_dst,
        "squashfs": squashfs_dst,
        "ipxe": ipxe_dst,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = root.add_subparsers(dest="command", required=True)

    cmd_gen = commands.add_parser("generate", help="Generate an iPXE script")
    cmd_gen.add_argument("--flavor", required=True)
    cmd_gen.add_argument("--digest", required=True)
    cmd_gen.add_argument("--out", type=pathlib.Path, required=True)

    cmd_ext = commands.add_parser("extract", help="Extract netboot assets from mounted root")
    cmd_ext.add_argument("--flavor", required=True)
    cmd_ext.add_argument("--root", type=pathlib.Path, required=True)
    cmd_ext.add_argument("--out", type=pathlib.Path, required=True)
    cmd_ext.add_argument("--no-sudo", action="store_true", help="run mksquashfs without sudo")

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            script = generate_ipxe(args.flavor, args.digest)
            args.out.write_text(script, encoding="utf-8")
        elif args.command == "extract":
            extract(args.flavor, args.root, args.out, use_sudo=not args.no_sudo)
    except (NetbootError, ValueError, OSError) as error:
        print(f"::error::netboot asset {args.command} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
