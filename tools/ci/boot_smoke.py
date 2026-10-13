#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Boot a built image once and fail unless it reaches cloud-init's final stage.

The image boots in QEMU from a throw-away overlay (`snapshot=on`), so the file that is
compressed, catalogued and released afterwards is never written. A NoCloud seed with a
fresh instance id makes cloud-init run again (`99-cleanup.sh` cleared its state), and its
`runcmd` writes a marker with a random nonce to the serial console and powers the machine
off. The check passes only when the serial log holds that marker with this run's nonce:
the kernel booted, the root file system mounted, systemd reached `cloud-final.service`
and cloud-init read the seed. The seed holds the nonce reversed and the guest's `rev`
turns it round, so a console that only echoes the seed shows no marker. A stale log, a marker from another run, an early QEMU exit
or a boot that does not finish before the deadline fails.

Usage:
  python3 -I tools/ci/boot_smoke.py --image IMG.qcow2 [--accel tcg] [--timeout 1500]
"""

import argparse
import pathlib
import secrets
import subprocess
import sys
import tempfile
import time

MARKER = "IMAGO-BOOT-OK"
POLL_S = 2.0
STOP_GRACE_S = 120
TOOL_TIMEOUT_S = 60
LOG_TAIL_LINES = 40
ACCELERATORS = ("kvm", "tcg")


class BootError(Exception):
    """The image did not prove that it boots."""


def user_data(nonce: str) -> str:
    return (
        "#cloud-config\n"
        "runcmd:\n"
        f"  - [sh, -c, 'echo \"{MARKER} $(echo {nonce[::-1]} | rev) $(uname -r)\" > /dev/ttyS0']\n"
        "power_state:\n"
        "  mode: poweroff\n"
        "  timeout: 30\n"
    )


def seed_iso(workdir: pathlib.Path, nonce: str, xorriso: str) -> pathlib.Path:
    """Write a NoCloud seed with a fresh instance id and return its ISO."""
    seed = workdir / "seed"
    seed.mkdir()
    (seed / "meta-data").write_text(
        f"instance-id: imago-smoke-{nonce}\nlocal-hostname: imago-smoke\n", encoding="utf-8"
    )
    (seed / "user-data").write_text(user_data(nonce), encoding="utf-8")
    iso = workdir / "seed.iso"
    result = subprocess.run(
        [xorriso, "-as", "mkisofs", "-output", str(iso), "-volid", "cidata", "-joliet", "-rock", str(seed)],
        capture_output=True, text=True, timeout=TOOL_TIMEOUT_S, check=False,
    )  # fmt: skip
    if result.returncode != 0:
        raise BootError(f"xorriso exited {result.returncode}: {result.stderr.strip()[:400]}")
    return iso


def command(qemu: str, image: pathlib.Path, seed: pathlib.Path, serial: pathlib.Path, accel: str) -> list[str]:
    cpu = "host" if accel == "kvm" else "max"
    return [
        qemu, "-machine", f"pc,accel={accel}", "-cpu", cpu, "-smp", "2", "-m", "2048",
        "-display", "none", "-monitor", "none", "-no-reboot",
        "-serial", f"file:{serial}",
        "-drive", f"file={image},if=virtio,format=qcow2,snapshot=on",
        "-drive", f"file={seed},media=cdrom,readonly=on",
        "-nic", "user,model=virtio-net-pci",
    ]  # fmt: skip


def read_log(serial: pathlib.Path) -> str:
    try:
        return serial.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def marker_line(log: str, nonce: str) -> str:
    """Return the marker line of this run, or an empty string."""
    for line in log.splitlines():
        if f"{MARKER} {nonce}" in line:
            return line.strip()
    return ""


def stop(process: subprocess.Popen) -> None:
    """Let a machine that printed the marker power off, then make sure QEMU is gone."""
    try:
        process.wait(timeout=STOP_GRACE_S)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=TOOL_TIMEOUT_S)


def watch(process: subprocess.Popen, serial: pathlib.Path, nonce: str, timeout_s: float) -> str:
    """Poll the serial log until the marker appears, QEMU exits or the deadline passes."""
    for _ in range(int(timeout_s / POLL_S) + 1):
        found = marker_line(read_log(serial), nonce)
        if found:
            stop(process)
            return found
        if process.poll() is not None:
            found = marker_line(read_log(serial), nonce)
            if found:
                return found
            raise BootError(f"QEMU exited {process.returncode} before the image printed the marker")
        time.sleep(POLL_S)
    process.kill()
    process.wait(timeout=TOOL_TIMEOUT_S)
    raise BootError(f"no marker on the serial console within {timeout_s:.0f} s")


def boot(image: pathlib.Path, qemu: str, xorriso: str, accel: str, timeout_s: float) -> str:
    if not image.is_file() or image.suffix != ".qcow2":
        raise BootError(f"{image} is not a qcow2 image")
    if accel not in ACCELERATORS:
        raise BootError(f"unknown accelerator {accel}; known: {', '.join(ACCELERATORS)}")
    nonce = secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix="boot-smoke-") as scratch:
        workdir = pathlib.Path(scratch)
        seed = seed_iso(workdir, nonce, xorriso)
        serial = workdir / "serial.log"
        errors = workdir / "qemu.err"
        with errors.open("w", encoding="utf-8") as sink:
            process = subprocess.Popen(
                command(qemu, image.resolve(), seed, serial, accel),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=sink,
            )  # fmt: skip
            try:
                return watch(process, serial, nonce, timeout_s)
            except BootError:
                tail = (read_log(errors) + read_log(serial)).splitlines()[-LOG_TAIL_LINES:]
                print("\n".join(["--- QEMU and serial console tail ---", *tail, "---"]), file=sys.stderr)
                raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", required=True, type=pathlib.Path, help="qcow2 image to boot")
    parser.add_argument("--accel", default="tcg", help="QEMU accelerator: kvm or tcg")
    parser.add_argument("--timeout", type=float, default=1500, help="seconds until the marker must appear")
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--xorriso", default="xorriso")
    args = parser.parse_args(argv)
    try:
        line = boot(args.image, args.qemu, args.xorriso, args.accel, args.timeout)
    except (BootError, OSError, subprocess.TimeoutExpired) as error:
        print(f"::error::boot smoke test failed for {args.image}: {error}", file=sys.stderr)
        return 1
    print(f"boot smoke test passed: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
