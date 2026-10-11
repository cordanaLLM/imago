#!/usr/bin/env python3
# Copyright 2026 Lusoris Authors
# SPDX-License-Identifier: EUPL-1.2
"""Cluster tunnel daemon for Hindsight semantic-memory backend.

Maintains a localhost port-forward to service/hindsight in the ai namespace:
  kubectl --namespace=ai port-forward service/hindsight 8888:8888 --address=127.0.0.1

Usage:
  python scripts/tunnel_hindsight.py [--check] [--port 8888]
"""

from __future__ import annotations

import argparse
import http.client
import subprocess
import sys
import time

DEFAULT_PORT = 8888
NAMESPACE = "ai"
SERVICE = "service/hindsight"
# Upper bound on port-forward starts. The 5 s pause after each ended
# port-forward alone keeps the supervisor running for ten hours before the
# bound is reached.
MAX_STARTS = 7200


def check_health(port: int = DEFAULT_PORT) -> bool:
    """Probe Hindsight health endpoint on loopback using http.client (avoids dynamic urllib SSRF)."""
    if not (1 <= port <= 65535):
        return False
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/v1/default/banks")
        resp = conn.getresponse()
        status = resp.status
        conn.close()
        return 200 <= status < 300
    except Exception:
        return False


def run_tunnel(port: int = DEFAULT_PORT, max_starts: int = MAX_STARTS) -> int:
    """Launch and supervise kubectl port-forward; give up after `max_starts` starts."""
    print(f"[*] Starting Hindsight tunnel on 127.0.0.1:{port} -> {SERVICE} (ns: {NAMESPACE})...")
    cmd = [
        "kubectl",
        f"--namespace={NAMESPACE}",
        "port-forward",
        SERVICE,
        f"{port}:8888",
        "--address=127.0.0.1",
    ]

    for _ in range(max_starts):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(2)
            if check_health(port):
                print(f"[+] Hindsight tunnel active on http://127.0.0.1:{port}.")
            proc.wait()
            print("[!] Port-forward process terminated. Reconnecting in 5s...", file=sys.stderr)
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[*] Stopping Hindsight tunnel.")
            if "proc" in locals() and proc.poll() is None:
                proc.terminate()
            return 0
        except Exception as exc:
            print(f"[!] Tunnel error: {exc}. Retrying in 10s...", file=sys.stderr)
            time.sleep(10)
    print(f"[!] Port-forward was started {max_starts} times; giving up.", file=sys.stderr)
    return 1


def main() -> int:
    """CLI entrypoint for Hindsight tunnel supervisor."""
    parser = argparse.ArgumentParser(description="Hindsight cluster port-forward supervisor")
    parser.add_argument("--check", action="store_true", help="Check if Hindsight is currently reachable")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Local port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    if args.check:
        healthy = check_health(args.port)
        if healthy:
            print(f"[OK] Hindsight service is reachable on http://127.0.0.1:{args.port}.")
            return 0
        print(f"[FAIL] Hindsight is unreachable on http://127.0.0.1:{args.port}.", file=sys.stderr)
        return 1

    return run_tunnel(args.port)


if __name__ == "__main__":
    sys.exit(main())
