#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""
Pre-tool lifecycle hook for Gemini Antigravity Agent sandbox.
Asserts zero private RFC 1918 IP addresses or developer workstation paths
before any file write operation executes.
"""

import json
import re
import sys
from typing import Optional

# RFC 1918 private IPv4 patterns
RFC1918_PATTERNS = [
    re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}\b"),
]

# Workstation private home paths
WORKSTATION_PATH_PATTERNS = [
    re.compile(r"/home/[a-zA-Z0-9_-]+/"),
    re.compile(r"C:\\Users\\[a-zA-Z0-9_-]+\\dev\\"),
]


def inspect_payload(text: str) -> Optional[str]:
    """Return the violation found in text, or None when the payload is clean."""
    for pattern in RFC1918_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"SECURITY VIOLATION: Private RFC 1918 IP detected: {match.group(0)}"

    for pattern in WORKSTATION_PATH_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"SECURITY VIOLATION: Local workstation path detected: {match.group(0)}"

    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # If payload is empty or not JSON, allow through
        sys.exit(0)

    args = data.get("arguments", {})
    content = args.get("content", "") or args.get("text", "") or ""

    if isinstance(content, str) and content:
        violation = inspect_payload(content)
        if violation:
            sys.stderr.write(violation + "\n")
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
