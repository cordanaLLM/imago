#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Check that the upstream package sources pinned in versions.json exist before a build.

A provisioner that fetches a missing key or apt suite fails only after the image has been
installed and booted, about 20 minutes into a Packer build. This check resolves the same
URLs from versions.json and requests each one, so a pin that names a release, key or suite
the vendor does not publish fails the build job in seconds.

The urls command prints the URLs; the check command requests them and exits 1 naming every
URL that did not answer 200.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request
from collections.abc import Callable

ROOT = pathlib.Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 30
MAX_URLS = 32

Fetch = Callable[[str], int]


def rocm_urls(manifest: dict) -> list[str]:
    """Return the ROCm key and the apt Release file of every pinned ROCm version."""
    amd = manifest["drivers"]["amd"]
    repo = amd["rocm_repo"]
    suite = amd["rocm_apt_suite"]
    urls = [f"{repo}/rocm.gpg.key"]
    for key in ("rocm_bleeding_version", "rocm_legacy_version"):
        urls.append(f"{repo}/apt/{amd[key]}/dists/{suite}/Release")
    return urls


def source_urls(manifest: dict) -> list[str]:
    urls = rocm_urls(manifest)
    if len(urls) > MAX_URLS:
        raise ValueError(f"{len(urls)} URLs exceed the bound of {MAX_URLS}")
    return urls


def http_status(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def missing(urls: list[str], fetch: Fetch) -> list[str]:
    """Return each URL with its status, for every URL that did not answer 200."""
    failures = []
    for url in urls:
        status = fetch(url)
        if status != 200:
            failures.append(f"{status} {url}")
    return failures


def main(argv: list[str] | None = None, fetch: Fetch = http_status) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["urls", "check"])
    parser.add_argument("--manifest", type=pathlib.Path, default=ROOT / "versions.json")
    args = parser.parse_args(argv)
    urls = source_urls(json.loads(args.manifest.read_text(encoding="utf-8")))
    if args.command == "urls":
        print("\n".join(urls))
        return 0
    failures = missing(urls, fetch)
    for failure in failures:
        print(f"::error::upstream source missing: {failure}", file=sys.stderr)
    print(f"{len(urls) - len(failures)} of {len(urls)} upstream sources answered 200")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
