#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Boot a built netboot flavor over iPXE and fail unless integrity verification passes.

In a normal run, serves netboot assets (<flavor>-netboot.vmlinuz, <flavor>-netboot.initrd,
<flavor>-root.squashfs, <flavor>.ipxe) on loopback, boots diskless QEMU with iPXE, fetches
the root squashfs, checks sha256 integrity via imago-netroot, and validates that cloud-init
reaches the multi-user marker on the serial console.

In a negative run (--expect-mismatch), verifies that a wrong imago.root-sha256 digest
triggers an immediate 'imago-netroot: root sha256 mismatch' error and refuses to mount.

RAM allocation: 4096 MiB (4 GiB). Netboot operates completely diskless: the kernel, initrd,
entire fetched root squashfs (~605 MiB to ~1.5 GiB) in tmpfs, page cache for the loop device,
and the writable overlayfs all reside concurrently in RAM. 2048 MiB risks OOM killer during
root transition; 4096 MiB provides safe headroom.

All networking uses 192.0.2.x (RFC 5737 TEST-NET-1 documentation range), never RFC 1918.

Usage:
  python3 -I tools/ci/netboot_smoke.py --dir ASSET_DIR --flavor FLAVOR [--accel tcg] [--timeout 1500] [--expect-mismatch]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import pathlib
import re
import secrets
import signal
import subprocess
import sys
import threading
import time

try:
    from tools.ci.boot_smoke import (
        ACCELERATORS,
        LOG_TAIL_LINES,
        POLL_S,
        TOOL_TIMEOUT_S,
        BootError,
        marker_line,
        read_log,
        signal_group,
        stop,
        user_data,
        watch,
    )
except ImportError:
    from boot_smoke import (  # type: ignore[no-redef]
        ACCELERATORS,
        LOG_TAIL_LINES,
        POLL_S,
        TOOL_TIMEOUT_S,
        BootError,
        marker_line,
        read_log,
        signal_group,
        stop,
        user_data,
        watch,
    )

MISMATCH_MARKER = "imago-netroot: root sha256 mismatch"
NETBOOT_RAM_MB = "4096"
NET_NETWORK = "192.0.2.0/24"
NET_HOST = "192.0.2.2"


class AssetServer:
    """Bounded-lifetime HTTP server serving netboot assets on loopback."""

    def __init__(self, directory: pathlib.Path) -> None:
        self.directory = directory
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def __enter__(self) -> AssetServer:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def mismatch_line(log: str) -> str:
    """Return the root sha256 mismatch error line from the serial log, or an empty string."""
    for line in log.splitlines():
        if MISMATCH_MARKER in line:
            return line.strip()
    return ""


def inject_cmdline(ipxe_script: str, extra: str) -> str:
    """Append extra kernel command line options to the kernel line in an iPXE script."""
    lines = []
    for line in ipxe_script.splitlines():
        if line.startswith("kernel ") and extra not in line:
            lines.append(f"{line} {extra}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def command(
    qemu: str,
    port: int,
    flavor: str,
    serial: pathlib.Path,
    accel: str,
) -> list[str]:
    """Build QEMU command for diskless iPXE network boot."""
    cpu = "host" if accel == "kvm" else "max"
    bootfile_url = f"http://{NET_HOST}:{port}/{flavor}.ipxe"
    netdev_arg = f"user,id=n0,net={NET_NETWORK},host={NET_HOST},bootfile={bootfile_url}"
    return [
        qemu,
        "-machine",
        f"pc,accel={accel}",
        "-cpu",
        cpu,
        "-smp",
        "2",
        "-m",
        NETBOOT_RAM_MB,
        "-display",
        "none",
        "-monitor",
        "none",
        "-no-reboot",
        "-serial",
        f"file:{serial}",
        "-netdev",
        netdev_arg,
        "-device",
        "virtio-net-pci,netdev=n0",
        "-boot",
        "n",
    ]


def kill_process_group(process: subprocess.Popen) -> None:
    """Kill the QEMU process group, then reap QEMU itself.

    QEMU starts with `start_new_session=True`, so its pid is its group id; the pid is passed
    to the guard directly. `os.getpgid()` is never asked: a pid that was already reused would
    name another process's group, and a mock pid would name group 1.
    """
    try:
        signal_group(process.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    try:
        process.kill()
        process.wait(timeout=TOOL_TIMEOUT_S)
    except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
        pass


def watch_mismatch(process: subprocess.Popen, serial: pathlib.Path, nonce: str, timeout_s: float) -> str:
    """Poll serial log until the mismatch error appears, failing if multi-user marker is reached."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        log = read_log(serial)
        if marker_line(log, nonce):
            stop(process)
            raise BootError("image booted to multi-user marker despite wrong digest")
        found = mismatch_line(log)
        if found:
            stop(process)
            return found
        if process.poll() is not None:
            log = read_log(serial)
            if marker_line(log, nonce):
                raise BootError("image booted to multi-user marker despite wrong digest")
            found = mismatch_line(log)
            if found:
                return found
            raise BootError(f"QEMU exited {process.returncode} before mismatch line was printed")
        time.sleep(POLL_S)
    kill_process_group(process)
    raise BootError(f"no mismatch error line on serial console within {timeout_s:.0f} s")


def prepare_seed(serve_dir: pathlib.Path, nonce: str) -> None:
    """Write NoCloud metadata and userdata to be served over HTTP."""
    seed_dir = serve_dir / "seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "meta-data").write_text(
        f"instance-id: imago-smoke-{nonce}\nlocal-hostname: imago-smoke\n",
        encoding="utf-8",
    )
    (seed_dir / "user-data").write_text(user_data(nonce), encoding="utf-8")


def run_boot(
    asset_dir: pathlib.Path,
    flavor: str,
    accel: str,
    timeout_s: float,
    *,
    expect_mismatch: bool = False,
    qemu: str = "qemu-system-x86_64",
) -> str:
    if accel not in ACCELERATORS:
        raise BootError(f"unknown accelerator {accel}; known: {', '.join(ACCELERATORS)}")

    script_path = asset_dir / f"{flavor}.ipxe"
    if not script_path.is_file():
        raise BootError(f"iPXE script {script_path} does not exist")

    original_script = script_path.read_text(encoding="utf-8")
    nonce = secrets.token_hex(8)

    with AssetServer(asset_dir) as server:
        prepare_seed(asset_dir, nonce)
        seed_arg = f"ds=nocloud;s=http://{NET_HOST}:{server.port}/seed/"
        test_script = inject_cmdline(original_script, seed_arg)
        if expect_mismatch and "imago.root-sha256=0000" not in test_script:
            test_script = re.sub(
                r"imago\.root-sha256=[0-9a-f]{64}",
                "imago.root-sha256=" + "0" * 64,
                test_script,
            )
        script_path.write_text(test_script, encoding="utf-8")

        serial = asset_dir / "serial.log"
        errors = asset_dir / "qemu.err"
        if serial.exists():
            serial.unlink()

        try:
            with errors.open("w", encoding="utf-8") as sink:
                cmd = command(qemu, server.port, flavor, serial, accel)
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=sink,
                    start_new_session=True,
                )
                try:
                    if expect_mismatch:
                        return watch_mismatch(process, serial, nonce, timeout_s)
                    return watch(process, serial, nonce, timeout_s)
                except BootError:
                    tail = (read_log(errors) + read_log(serial)).splitlines()[-LOG_TAIL_LINES:]
                    print("\n".join(["--- QEMU and serial console tail ---", *tail, "---"]), file=sys.stderr)
                    raise
                finally:
                    kill_process_group(process)
        finally:
            script_path.write_text(original_script, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dir", "--assets", dest="dir", required=True, type=pathlib.Path, help="directory holding netboot assets"
    )
    parser.add_argument("--flavor", required=True, help="flavor name to netboot")
    parser.add_argument("--accel", default="tcg", help="QEMU accelerator: kvm or tcg")
    parser.add_argument("--timeout", type=float, default=1500, help="seconds until marker must appear")
    parser.add_argument("--expect-mismatch", action="store_true", help="verify rejection of wrong root digest")
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    args = parser.parse_args(argv)

    try:
        line = run_boot(
            args.dir,
            args.flavor,
            args.accel,
            args.timeout,
            expect_mismatch=args.expect_mismatch,
            qemu=args.qemu,
        )
    except (BootError, OSError, subprocess.TimeoutExpired) as error:
        print(f"::error::netboot smoke test failed for {args.flavor}: {error}", file=sys.stderr)
        return 1
    print(f"netboot smoke test passed: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
