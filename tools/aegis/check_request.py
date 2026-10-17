#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Verify Aegis build request inputs and commit lineage.

Validates the input parameters, verifies the SHA-256 digest of
aegis/build/product-input.json against the expected hash, runs
`imago aegis validate` on the manifest, and confirms that the
reviewed-definitions commit (request.revision) is an ancestor of
the target aegis-revision using git merge-base --is-ancestor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

HEX_LOWER_RE = re.compile(r"^[0-9a-f]+$")
MAX_REQUEST_CHUNKS = 1024  # 1024 * 64 KiB = 64 MiB (manifest is < 1 MiB)
CHUNK_SIZE = 65536
SUBPROCESS_TIMEOUT_S = 30.0


class RequestCheckError(Exception):
    """Raised when an Aegis build request check fails."""


def validate_hex(value: str, expected_len: int, name: str) -> None:
    """Ensure value consists of exactly expected_len lowercase hex characters."""
    if len(value) != expected_len or not HEX_LOWER_RE.fullmatch(value):
        raise RequestCheckError(f"Invalid {name}: must be {expected_len} lowercase hex characters, got {value!r}")


def compute_sha256(path: pathlib.Path) -> str:
    """Compute SHA-256 hex digest of path with bounded chunk reading."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for _ in range(MAX_REQUEST_CHUNKS):
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                return hasher.hexdigest()
            hasher.update(chunk)
        remaining = handle.read(1)
        if remaining:
            raise RequestCheckError(f"File {path} exceeds maximum size limit")
    return hasher.hexdigest()


def verify_request_sha(path: pathlib.Path, expected_sha: str) -> str:
    """Verify that file digest matches expected SHA-256."""
    actual_sha = compute_sha256(path)
    if actual_sha != expected_sha:
        raise RequestCheckError(f"SHA-256 mismatch for {path}: expected {expected_sha}, computed {actual_sha}")
    return actual_sha


def read_request_revision(path: pathlib.Path) -> str:
    """Read and validate the revision field from the request JSON."""
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except (OSError, json.JSONDecodeError) as err:
        raise RequestCheckError(f"Failed to read JSON from {path}: {err}") from err

    revision = data.get("revision")
    if not isinstance(revision, str):
        raise RequestCheckError(f"Request {path} missing string 'revision' field")
    validate_hex(revision, 40, "request.revision")
    return revision


def verify_imago_validate(imago_bin: str, request_path: pathlib.Path, timeout_s: float = SUBPROCESS_TIMEOUT_S) -> None:
    """Run imago aegis validate on the request file."""
    cmd = [imago_bin, "aegis", "validate", str(request_path)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as err:
        raise RequestCheckError(f"imago binary not found at {imago_bin!r}") from err
    except subprocess.TimeoutExpired as err:
        raise RequestCheckError(f"imago aegis validate timed out after {timeout_s}s") from err

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RequestCheckError(f"imago aegis validate rejected request (exit {proc.returncode}): {detail}")


def verify_git_ancestor(
    aegis_dir: pathlib.Path,
    request_rev: str,
    aegis_rev: str,
    timeout_s: float = SUBPROCESS_TIMEOUT_S,
) -> None:
    """Verify that request_rev is an ancestor of aegis_rev."""
    cmd = [
        "git",
        "-C",
        str(aegis_dir),
        "merge-base",
        "--is-ancestor",
        request_rev,
        aegis_rev,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as err:
        raise RequestCheckError("git executable not found") from err
    except subprocess.TimeoutExpired as err:
        raise RequestCheckError(f"git merge-base timed out after {timeout_s}s") from err

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RequestCheckError(
            f"Lineage refusal: request revision {request_rev} is not an ancestor of {aegis_rev}: {detail}"
        )


def check_request(
    request_path: pathlib.Path,
    expected_sha: str,
    aegis_dir: pathlib.Path,
    aegis_rev: str,
    imago_bin: str = "./imago",
) -> None:
    """Execute all request preflight checks."""
    validate_hex(expected_sha, 64, "request-sha256")
    validate_hex(aegis_rev, 40, "aegis-revision")

    if not request_path.is_file():
        raise RequestCheckError(f"Request file not found: {request_path}")

    verify_request_sha(request_path, expected_sha)
    request_rev = read_request_revision(request_path)
    verify_imago_validate(imago_bin, request_path)
    verify_git_ancestor(aegis_dir, request_rev, aegis_rev)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for request verification."""
    parser = argparse.ArgumentParser(description="Verify Aegis build request inputs and commit lineage.")
    parser.add_argument("--request", required=True, type=pathlib.Path, help="Path to product-input.json")
    parser.add_argument("--request-sha256", required=True, help="Expected SHA-256 of product-input.json")
    parser.add_argument("--aegis-dir", required=True, type=pathlib.Path, help="Path to Aegis-OS git checkout")
    parser.add_argument("--aegis-revision", required=True, help="Target Aegis commit revision")
    parser.add_argument("--imago-binary", default="./imago", help="Path to imago binary (default: ./imago)")

    args = parser.parse_args(argv)
    try:
        check_request(
            request_path=args.request,
            expected_sha=args.request_sha256,
            aegis_dir=args.aegis_dir,
            aegis_rev=args.aegis_revision,
            imago_bin=args.imago_binary,
        )
    except RequestCheckError as err:
        sys.stderr.write(f"check_request: error: {err}\n")
        return 1

    sys.stdout.write("check_request: Aegis build request and commit lineage verified successfully.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
