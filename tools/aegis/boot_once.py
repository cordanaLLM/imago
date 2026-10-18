#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Boot an Aegis OS image once in QEMU to verify bootability and emit evidence.

Runs QEMU with KVM, q35 machine, OVMF UEFI firmware (non-Secure-Boot code with
temporary vars copy), a swtpm socket TPM 2.0 device, a throwaway qcow2 overlay
over the raw image, and serial output redirected to a log file. Passes the
SMBIOS Type 11 string io.systemd.stub.kernel-cmdline-extra=console=ttyS0 so
systemd-stub appends console=ttyS0 to the kernel command line. Polls until a
systemd target success marker appears or the deadline expires. Kills the
process group on all exit paths and writes boot-evidence.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

SCHEMA_ID = "imago.aegis.boot-evidence.v1"
CMDLINE_EXTRA = "console=ttyS0"
SMBIOS_ARG = "io.systemd.stub.kernel-cmdline-extra=console=ttyS0"
DEFAULT_DEADLINE_S = 600.0
DEFAULT_POLL_INTERVAL_S = 2.0
MAX_LOG_READ_BYTES = 10 * 1024 * 1024  # 10 MiB limit
MAX_LOG_SCAN_LINES = 10000
MAX_IMAGE_CHUNKS = 1048576  # 64 GiB max (chunk size 64 KiB)
CHUNK_SIZE = 65536
SWTPM_SOCKET_WAIT_STEPS = 100  # 100 x 0.1 s = 10 s for the control socket
DEFAULT_MARKER_REGEX = r"(Reached target (multi-user\.target|Multi-User System)|Startup finished in)"

OVMF_CODE_CANDIDATES = (
    pathlib.Path("/usr/share/OVMF/OVMF_CODE_4M.fd"),
    pathlib.Path("/usr/share/OVMF/OVMF_CODE.fd"),
    pathlib.Path("/usr/share/edk2/x64/OVMF_CODE.4m.fd"),
    pathlib.Path("/usr/share/edk2/x64/OVMF_CODE.fd"),
    pathlib.Path("/usr/share/edk2-ovmf/x64/OVMF_CODE.fd"),
)

OVMF_VARS_CANDIDATES = (
    pathlib.Path("/usr/share/OVMF/OVMF_VARS_4M.fd"),
    pathlib.Path("/usr/share/OVMF/OVMF_VARS.fd"),
    pathlib.Path("/usr/share/edk2/x64/OVMF_VARS.4m.fd"),
    pathlib.Path("/usr/share/edk2/x64/OVMF_VARS.fd"),
    pathlib.Path("/usr/share/edk2-ovmf/x64/OVMF_VARS.fd"),
)


class BootError(Exception):
    """Raised when single-boot verification fails."""


def resolve_ovmf(
    code_path: pathlib.Path | None = None, vars_path: pathlib.Path | None = None
) -> tuple[pathlib.Path, pathlib.Path]:
    """Locate non-Secure-Boot OVMF code and vars files."""
    if code_path and vars_path:
        if not code_path.is_file():
            raise BootError(f"OVMF code file not found: {code_path}")
        if not vars_path.is_file():
            raise BootError(f"OVMF vars file not found: {vars_path}")
        return code_path, vars_path

    resolved_code = next((p for p in OVMF_CODE_CANDIDATES if p.is_file()), None)
    resolved_vars = next((p for p in OVMF_VARS_CANDIDATES if p.is_file()), None)
    if not resolved_code or not resolved_vars:
        raise BootError("Could not locate standard non-Secure-Boot OVMF code and vars files")
    return resolved_code, resolved_vars


def get_tool_version(cmd: list[str], default: str = "unknown") -> str:
    """Run a version command and return the first non-empty line."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0, check=False)
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if line_str:
                return line_str
    except (OSError, subprocess.TimeoutExpired):
        # A missing or hanging tool leaves its version unknown; the evidence records the default.
        return default
    return default


def compute_file_sha256(path: pathlib.Path) -> str:
    """Compute SHA-256 digest of a file with a bounded loop."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for _ in range(MAX_IMAGE_CHUNKS):
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                return hasher.hexdigest()
            hasher.update(chunk)
        if handle.read(1):
            raise BootError(f"File {path} exceeds maximum supported size for hashing")
    return hasher.hexdigest()


def clean_ansi(text: str) -> str:
    """Strip ANSI escape sequences from terminal log text."""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def find_marker_line(log_path: pathlib.Path, pattern: re.Pattern[str]) -> str | None:
    """Search serial log for a line matching the success marker pattern."""
    if not log_path.is_file():
        return None
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            raw = handle.read(MAX_LOG_READ_BYTES)
    except OSError:
        return None

    cleaned = clean_ansi(raw)
    lines = cleaned.splitlines()
    bound = min(len(lines), MAX_LOG_SCAN_LINES)
    for idx in range(bound):
        line = lines[idx].strip()
        if pattern.search(line):
            return line
    return None


def kill_process_group(pgid: int | None) -> None:
    """Terminate and kill a process group if still active.

    `os.killpg(1, sig)` is `kill(-1, sig)` and reaches every process the user owns; a
    `MagicMock` pid indexes to 1. Only a real `int` above 1 that is not this process's own
    group is signalled. `tools/ci/boot_smoke.py` `signal_group` holds the same check; this
    script runs under `python3 -I` from `tools/aegis/` and cannot import it.
    """
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 1 or pgid == os.getpgrp():
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
        time.sleep(0.5)
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        # The group already exited after SIGTERM, or was reaped; nothing is left to kill.
        return


def setup_swtpm(state_dir: pathlib.Path, swtpm_setup_bin: str) -> None:
    """Initialize TPM 2.0 state directory."""
    cmd = [
        swtpm_setup_bin,
        "--tpm-state",
        str(state_dir),
        "--tpm2",
        "--pcr-banks",
        "sha256",
        "--config",
        "/dev/null",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise BootError(f"swtpm_setup failed (exit {proc.returncode}): {detail}")


def create_overlay(raw_image: pathlib.Path, overlay_path: pathlib.Path, qemu_img_bin: str) -> None:
    """Create throwaway qcow2 overlay referencing the raw image."""
    cmd = [
        qemu_img_bin,
        "create",
        "-f",
        "qcow2",
        "-b",
        str(raw_image.resolve()),
        "-F",
        "raw",
        str(overlay_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise BootError(f"qemu-img create overlay failed (exit {proc.returncode}): {detail}")


def build_qemu_cmd(
    qemu_bin: str,
    ovmf_code: pathlib.Path,
    *,
    vars_copy: pathlib.Path,
    swtpm_sock: pathlib.Path,
    overlay_path: pathlib.Path,
    serial_log: pathlib.Path,
) -> list[str]:
    """Construct QEMU command arguments for UEFI KVM boot."""
    return [
        qemu_bin,
        "-machine",
        "q35,accel=kvm",
        "-cpu",
        "host",
        "-smp",
        "2",
        "-m",
        "2048",
        "-no-reboot",
        "-display",
        "none",
        "-drive",
        f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        "-drive",
        f"if=pflash,format=raw,file={vars_copy}",
        "-chardev",
        f"socket,id=chrtpm,path={swtpm_sock}",
        "-tpmdev",
        "emulator,id=tpm0,chardev=chrtpm",
        "-device",
        "tpm-tis,tpmdev=tpm0",
        "-drive",
        f"file={overlay_path},if=virtio,format=qcow2",
        "-serial",
        f"file:{serial_log}",
        "-smbios",
        f"type=11,value={SMBIOS_ARG}",
        "-nic",
        "none",
    ]


def poll_boot(
    proc: subprocess.Popen[bytes],
    serial_log: pathlib.Path,
    pattern: re.Pattern[str],
    deadline_s: float,
    poll_s: float,
) -> str:
    """Poll the serial console log until the success marker appears or timeout occurs."""
    max_iterations = int(deadline_s / max(poll_s, 0.1)) + 5
    for _ in range(max_iterations):
        marker = find_marker_line(serial_log, pattern)
        if marker:
            return marker
        if proc.poll() is not None:
            marker = find_marker_line(serial_log, pattern)
            if marker:
                return marker
            raise BootError(f"QEMU exited prematurely with code {proc.returncode} before marker")
        time.sleep(poll_s)
    raise BootError(f"Boot timed out after {deadline_s} seconds without reaching marker")


def detect_runner_image() -> str:
    """Detect the runner environment image identifier."""
    image_os = os.environ.get("ImageOS")
    if image_os:
        version = os.environ.get("ImageVersion", "")
        return f"{image_os}:{version}".rstrip(":")
    runner_os = os.environ.get("RUNNER_OS")
    if runner_os:
        return f"{runner_os}-hosted"
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("PRETTY_NAME="):
                    return line.partition("=")[2].strip().strip('"')
    except OSError:
        # Without os-release the runner is recorded under the generic name below.
        return "linux-host"
    return "linux-host"


def assemble_evidence(
    correlation_id: str,
    image_sha: str,
    *,
    qemu_ver: str,
    ovmf_ver: str,
    swtpm_ver: str,
    marker_line: str,
    serial_log: pathlib.Path,
    serial_sha: str,
    elapsed: float,
) -> dict[str, object]:
    """Assemble the boot evidence dictionary matching schema."""
    return {
        "schema": SCHEMA_ID,
        "correlation-id": correlation_id,
        "image-sha256": image_sha,
        "qemu-version": qemu_ver,
        "ovmf-version": ovmf_ver,
        "swtpm-version": swtpm_ver,
        "kernel-cmdline-extra": CMDLINE_EXTRA,
        "marker-line": marker_line,
        "serial-log": {
            "name": serial_log.name,
            "sha256": serial_sha,
        },
        "wall-seconds": round(elapsed, 3),
        "runner-image": detect_runner_image(),
    }


def launch_swtpm(
    swtpm_bin: str,
    swtpm_state: pathlib.Path,
    swtpm_sock: pathlib.Path,
) -> subprocess.Popen[bytes]:
    """Launch swtpm daemon in socket mode."""
    cmd = [
        swtpm_bin,
        "socket",
        "--tpm2",
        "--tpmstate",
        f"dir={swtpm_state}",
        "--ctrl",
        f"type=unixio,path={swtpm_sock}",
    ]
    proc = subprocess.Popen(cmd, start_new_session=True)
    for _ in range(SWTPM_SOCKET_WAIT_STEPS):
        if swtpm_sock.exists():
            return proc
        if proc.poll() is not None:
            raise BootError(f"swtpm exited with code {proc.returncode} before creating its socket")
        time.sleep(0.1)
    kill_process_group(proc.pid)
    raise BootError(f"swtpm socket {swtpm_sock} did not appear within the wait bound")


def run_qemu_session(
    qemu_cmd: list[str],
    serial_log: pathlib.Path,
    pattern: re.Pattern[str],
    deadline_s: float,
) -> str:
    """Spawn QEMU process and poll until marker line appears."""
    proc = subprocess.Popen(qemu_cmd, start_new_session=True)
    try:
        return poll_boot(proc, serial_log, pattern, deadline_s, DEFAULT_POLL_INTERVAL_S)
    finally:
        kill_process_group(proc.pid)


def save_boot_evidence(
    correlation_id: str,
    image_path: pathlib.Path,
    serial_log: pathlib.Path,
    evidence_path: pathlib.Path,
    *,
    marker: str,
    qemu_bin: str,
    ovmf_code: pathlib.Path,
    swtpm_bin: str,
    elapsed: float,
) -> dict[str, object]:
    """Collect digests and versions, then write evidence JSON."""
    image_sha = compute_file_sha256(image_path)
    serial_sha = compute_file_sha256(serial_log)
    qemu_ver = get_tool_version([qemu_bin, "--version"])
    swtpm_ver = get_tool_version([swtpm_bin, "--version"])
    evidence = assemble_evidence(
        correlation_id,
        image_sha,
        qemu_ver=qemu_ver,
        ovmf_ver=str(ovmf_code),
        swtpm_ver=swtpm_ver,
        marker_line=marker,
        serial_log=serial_log,
        serial_sha=serial_sha,
        elapsed=elapsed,
    )
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def execute_boot(
    image_path: pathlib.Path,
    correlation_id: str,
    *,
    serial_log: pathlib.Path,
    evidence_path: pathlib.Path,
    deadline_s: float = DEFAULT_DEADLINE_S,
    marker_regex: str = DEFAULT_MARKER_REGEX,
    ovmf_code_opt: pathlib.Path | None = None,
    ovmf_vars_opt: pathlib.Path | None = None,
    qemu_bin: str = "qemu-system-x86_64",
    swtpm_bin: str = "swtpm",
    swtpm_setup_bin: str = "swtpm_setup",
    qemu_img_bin: str = "qemu-img",
) -> dict[str, object]:
    """Run single boot cycle in throwaway environment and write evidence."""
    ovmf_code, ovmf_vars = resolve_ovmf(ovmf_code_opt, ovmf_vars_opt)
    pattern = re.compile(marker_regex)
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="imago-boot-"))
    overlay_path = temp_dir / "overlay.qcow2"
    vars_copy = temp_dir / "vars.fd"
    swtpm_state = temp_dir / "swtpm-state"
    swtpm_state.mkdir()
    swtpm_sock = temp_dir / "swtpm.sock"

    swtpm_proc: subprocess.Popen[bytes] | None = None
    start_time = time.monotonic()
    try:
        shutil.copyfile(ovmf_vars, vars_copy)
        create_overlay(image_path, overlay_path, qemu_img_bin)
        setup_swtpm(swtpm_state, swtpm_setup_bin)
        swtpm_proc = launch_swtpm(swtpm_bin, swtpm_state, swtpm_sock)
        qemu_cmd = build_qemu_cmd(
            qemu_bin,
            ovmf_code,
            vars_copy=vars_copy,
            swtpm_sock=swtpm_sock,
            overlay_path=overlay_path,
            serial_log=serial_log,
        )
        marker = run_qemu_session(qemu_cmd, serial_log, pattern, deadline_s)
        elapsed = time.monotonic() - start_time
    finally:
        if swtpm_proc:
            kill_process_group(swtpm_proc.pid)
        shutil.rmtree(temp_dir, ignore_errors=True)

    return save_boot_evidence(
        correlation_id,
        image_path,
        serial_log,
        evidence_path,
        marker=marker,
        qemu_bin=qemu_bin,
        ovmf_code=ovmf_code,
        swtpm_bin=swtpm_bin,
        elapsed=elapsed,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for boot_once."""
    parser = argparse.ArgumentParser(description="Boot an Aegis OS image once in QEMU and record evidence.")
    parser.add_argument("--image", required=True, type=pathlib.Path, help="Path to raw disk image")
    parser.add_argument("--correlation-id", required=True, help="Correlation ID of the build request")
    parser.add_argument("--serial-log", default=pathlib.Path("serial.log"), type=pathlib.Path, help="Serial log path")
    parser.add_argument(
        "--evidence", default=pathlib.Path("boot-evidence.json"), type=pathlib.Path, help="Output evidence JSON path"
    )
    parser.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE_S, help="Hard deadline in seconds")
    parser.add_argument("--marker", default=DEFAULT_MARKER_REGEX, help="Success marker regex")
    parser.add_argument("--ovmf-code", type=pathlib.Path, default=None, help="Custom OVMF code file path")
    parser.add_argument("--ovmf-vars", type=pathlib.Path, default=None, help="Custom OVMF vars template file path")

    args = parser.parse_args(argv)
    try:
        execute_boot(
            args.image,
            args.correlation_id,
            serial_log=args.serial_log,
            evidence_path=args.evidence,
            deadline_s=args.deadline,
            marker_regex=args.marker,
            ovmf_code_opt=args.ovmf_code,
            ovmf_vars_opt=args.ovmf_vars,
        )
    except BootError as err:
        sys.stderr.write(f"boot_once: error: {err}\n")
        return 1

    sys.stdout.write(f"boot_once: Success marker found. Evidence written to {args.evidence}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
