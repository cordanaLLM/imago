#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Expose a built image to Syft, check its SBOMs and merge the release checksums.

Syft cannot read a qcow2 disk: pointed at the file it catalogues nothing and still writes a
valid, empty SBOM. The attach command connects the image read-only through qemu-nbd and
mounts the partition labelled cloudimg-rootfs read-only, so Syft can catalogue that tree.
The Ubuntu cloud image keeps /boot on its own partition labelled BOOT; attach mounts it
read-only at <root>/boot, so the kernel and the netboot initrd are where the image boots
them from. detach undoes all three. The check command fails unless the CycloneDX and the SPDX document each
list at least MIN_DEB_PACKAGES Debian packages, so an empty catalogue never ships as an SBOM.

The merge command joins the checksum files of all flavors into the one SHA256SUMS the release
signs. It refuses an empty set, a malformed line, a path in a name and a name listed twice.

The sizes command lists the size of each compressed image, appends the list to the step
summary when one is given, and fails when an asset reaches ASSET_LIMIT_BYTES: the forge
refuses a release asset of 2 GiB or more, and a raw disk image grows with the disk size.

Usage:
  python3 -I tools/ci/release_assets.py attach --image IMG.qcow2 --at DIR [--device /dev/nbd0]
  python3 -I tools/ci/release_assets.py detach --at DIR [--device /dev/nbd0]
  python3 -I tools/ci/release_assets.py check --cdx sbom.cdx.json --spdx sbom.spdx.json
  python3 -I tools/ci/release_assets.py merge --out SHA256SUMS checksums/*.sha256
  python3 -I tools/ci/release_assets.py sizes [--summary FILE] IMG.qcow2.zst IMG.raw.zst
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time

ROOT_LABEL = "cloudimg-rootfs"
BOOT_LABEL = "BOOT"
MIN_DEB_PACKAGES = 100
MAX_PACKAGES = 100_000
MAX_CHECKSUM_LINES = 4096
PARTITION_POLLS = 30
COMMAND_TIMEOUT_S = 120
# "Each file included in a release must be under 2 GiB" (docs.github.com, About releases,
# checked 2026-10-14).
ASSET_LIMIT_BYTES = 2 * 1024**3
MAX_ASSETS = 1000
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64}) [ *]([A-Za-z0-9._+-]{1,255})$")


class AssetError(Exception):
    """A release asset that cannot be produced or trusted."""


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S, check=False)
    if result.returncode != 0:
        raise AssetError(f"{' '.join(command[:3])} exited {result.returncode}: {result.stderr.strip()[:400]}")
    return result.stdout


def partition_label(partition: str) -> str:
    try:
        return run(["sudo", "blkid", "-o", "value", "-s", "LABEL", partition]).strip()
    except AssetError:
        return ""


def labelled(device: str, label: str) -> list[str]:
    names = [n for n in run(["lsblk", "-nrpo", "NAME", device]).split() if n != device]
    return [n for n in names if partition_label(n) == label]


def boot_partition(device: str) -> str | None:
    """Return the partition of device labelled BOOT_LABEL, or None when /boot lives on the root."""
    found = labelled(device, BOOT_LABEL)
    if len(found) > 1:
        raise AssetError(f"{len(found)} partitions of {device} carry the label {BOOT_LABEL}")
    return found[0] if found else None


def root_partition(device: str) -> str:
    """Return the one partition of device labelled ROOT_LABEL, waiting for the kernel scan.

    The label is read per partition of this device only: the runner's own root file system
    carries the same label, so a lookup by label across all devices could mount the host.
    """
    for _ in range(PARTITION_POLLS):
        found = labelled(device, ROOT_LABEL)
        if len(found) > 1:
            raise AssetError(f"{len(found)} partitions of {device} carry the label {ROOT_LABEL}")
        if found:
            return found[0]
        time.sleep(1)
    raise AssetError(f"no partition of {device} carries the label {ROOT_LABEL}")


def attach(image: pathlib.Path, mount: pathlib.Path, device: str) -> None:
    if not image.is_file() or image.suffix != ".qcow2":
        raise AssetError(f"{image} is not a qcow2 image")
    mount.mkdir(parents=True, exist_ok=True)
    run(["sudo", "modprobe", "nbd", "max_part=16"])
    run(["sudo", "qemu-nbd", "--read-only", "--format=qcow2", f"--connect={device}", str(image)])
    try:
        run(["sudo", "mount", "-o", "ro,noload", root_partition(device), str(mount)])
    except AssetError:
        run(["sudo", "qemu-nbd", "--disconnect", device])
        raise
    if not (mount / "var/lib/dpkg/status").is_file():
        detach(mount, device)
        raise AssetError(f"the {ROOT_LABEL} partition holds no var/lib/dpkg/status")
    print(f"{image.name}: {ROOT_LABEL} mounted read-only at {mount}")
    attach_boot(mount, device)


def attach_boot(mount: pathlib.Path, device: str) -> None:
    try:
        boot = boot_partition(device)
        if boot is not None:
            run(["sudo", "mount", "-o", "ro,noload", boot, str(mount / "boot")])
    except AssetError:
        detach(mount, device)
        raise
    where = f"{BOOT_LABEL} mounted read-only at {mount / 'boot'}" if boot else f"no {BOOT_LABEL} partition"
    print(f"{device}: {where}")


def detach(mount: pathlib.Path, device: str) -> None:
    """Unmount /boot and the root, then disconnect; each step is tried, and any failure fails the command."""
    errors = []
    commands = [["sudo", "umount", str(mount)], ["sudo", "qemu-nbd", "--disconnect", device]]
    if os.path.ismount(mount / "boot"):
        commands.insert(0, ["sudo", "umount", str(mount / "boot")])
    for command in commands:
        try:
            run(command)
        except AssetError as error:
            errors.append(str(error))
    if errors:
        raise AssetError("; ".join(errors))


def deb_purls(packages: list, purls) -> int:
    return sum(
        1 for item in packages[:MAX_PACKAGES]
        if isinstance(item, dict) and any(p.startswith("pkg:deb/") for p in purls(item))
    )  # fmt: skip


def cyclonedx_purls(item: dict) -> list[str]:
    return [str(item.get("purl", ""))]


def spdx_purls(item: dict) -> list[str]:
    refs = item.get("externalRefs")
    if not isinstance(refs, list):
        return []
    return [str(ref.get("referenceLocator", "")) for ref in refs[:64] if isinstance(ref, dict)]


def load_list(path: pathlib.Path, key: str) -> list:
    document = json.loads(path.read_text(encoding="utf-8"))
    items = document.get(key) if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise AssetError(f"{path.name} has no {key} list")
    return items


def check(cdx: pathlib.Path, spdx: pathlib.Path) -> None:
    counts = {
        cdx.name: deb_purls(load_list(cdx, "components"), cyclonedx_purls),
        spdx.name: deb_purls(load_list(spdx, "packages"), spdx_purls),
    }
    for name, found in counts.items():
        if found < MIN_DEB_PACKAGES:
            raise AssetError(f"{name} lists {found} Debian packages, fewer than {MIN_DEB_PACKAGES}")
    print(", ".join(f"{name}: {found} Debian packages" for name, found in counts.items()))


def merge(parts: list[pathlib.Path], out: pathlib.Path) -> None:
    if not parts:
        raise AssetError("no checksum files to merge")
    lines: dict[str, str] = {}
    for part in parts[:MAX_CHECKSUM_LINES]:
        for line in part.read_text(encoding="utf-8").splitlines()[:MAX_CHECKSUM_LINES]:
            match = CHECKSUM_LINE.match(line)
            if not match:
                raise AssetError(f"{part.name}: not a sha256sum line: {line[:80]!r}")
            if match[2] in lines:
                raise AssetError(f"{match[2]} is listed twice")
            lines[match[2]] = f"{match[1]}  {match[2]}"
    if not lines:
        raise AssetError("the checksum files list no asset")
    out.write_text("".join(lines[name] + "\n" for name in sorted(lines)), encoding="utf-8")
    print(f"{out.name}: {len(lines)} assets from {len(parts)} checksum files")


def sizes(paths: list[pathlib.Path], summary: pathlib.Path | None) -> None:
    if not paths:
        raise AssetError("no release assets to measure")
    if len(paths) > MAX_ASSETS:
        raise AssetError(f"{len(paths)} assets, more than the {MAX_ASSETS} a release holds")
    measured = [(path.name, path.stat().st_size) for path in paths]
    rows = [f"| `{name}` | {size} | {size / 1024**3:.2f} GiB |" for name, size in measured]
    table = ["| Asset | Bytes | Size |", "| :--- | ---: | ---: |", *rows]
    if summary is not None:
        with summary.open("a", encoding="utf-8") as out:
            out.write("\n".join(table) + "\n")
    print("\n".join(table))
    too_large = [name for name, size in measured if size >= ASSET_LIMIT_BYTES]
    if too_large:
        raise AssetError(f"{', '.join(too_large)} reach the forge limit of {ASSET_LIMIT_BYTES} bytes per asset")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("attach", "detach"):
        sub = commands.add_parser(name)
        sub.add_argument("--at", type=pathlib.Path, required=True)
        sub.add_argument("--device", default="/dev/nbd0")
        if name == "attach":
            sub.add_argument("--image", type=pathlib.Path, required=True)
    sub = commands.add_parser("check")
    sub.add_argument("--cdx", type=pathlib.Path, required=True)
    sub.add_argument("--spdx", type=pathlib.Path, required=True)
    sub = commands.add_parser("merge")
    sub.add_argument("--out", type=pathlib.Path, required=True)
    sub.add_argument("parts", type=pathlib.Path, nargs="*")
    sub = commands.add_parser("sizes")
    sub.add_argument("--summary", type=pathlib.Path)
    sub.add_argument("assets", type=pathlib.Path, nargs="*")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    actions = {
        "attach": lambda: attach(args.image, args.at, args.device),
        "detach": lambda: detach(args.at, args.device),
        "check": lambda: check(args.cdx, args.spdx),
        "merge": lambda: merge(args.parts, args.out),
        "sizes": lambda: sizes(args.assets, args.summary),
    }
    try:
        actions[args.command]()
    except (AssetError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"::error::release asset {args.command} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
