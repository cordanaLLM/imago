"""Automated verification suite for security and privacy invariants.

Enforces zero-leak invariant:
- No private RFC 1918 IP addresses in configs, provisioners, or templates.
- No developer workstation home paths (/home/<user>).
- All GitHub Actions pinned to 40-character commit SHAs.
- No unencrypted private keys.
- Proper .gitignore hygiene for build artifacts and secrets.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

IGNORED_SCAN_PARTS = {".git", ".pytest_cache", "__pycache__", ".workingdir", "tests", "bin", "site"}

RFC1918 = re.compile(
    r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
LINUX_HOME = re.compile(r"/home/(?!(ubuntu|username|runner)\b)[a-zA-Z0-9_-]+")
DARWIN_HOME = re.compile(r"/Users/[a-zA-Z0-9_-]+")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")


def publishable_files() -> list[Path]:
    """Return the files git tracks or would add, outside the ignored scan parts.

    The zero-leak invariant binds what can reach a remote. Files that .gitignore excludes
    (coverage data, build caches, local state) carry workstation paths by design and are
    never committed, so they are not scanned.
    """
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    candidates = [REPO_ROOT / rel for rel in listing.split("\0") if rel]
    return [
        path
        for path in candidates
        if path.is_file() and not any(part in IGNORED_SCAN_PARTS for part in path.relative_to(REPO_ROOT).parts)
    ]


class TestSecurityPrivacyIntegrity:
    def test_no_private_rfc1918_ips(self) -> None:
        """Verify no private RFC 1918 IPs exist in configs, scripts, or templates."""
        for path in publishable_files():
            # Skip documentation files as they discuss RFC 1918 rules or examples
            if path.suffix == ".md" or "docs" in path.parts:
                continue

            content = path.read_text(encoding="utf-8", errors="ignore")
            match = RFC1918.search(content)
            assert not match, (
                f"Prohibited private RFC 1918 IP '{match.group(0)}' found in {path.relative_to(REPO_ROOT)}"
            )

    def test_no_developer_workstation_paths(self) -> None:
        """Verify no developer workstation home paths leak into repository files."""
        for path in publishable_files():
            content = path.read_text(encoding="utf-8", errors="ignore")
            m_linux = LINUX_HOME.search(content)
            assert not m_linux, (
                f"Prohibited workstation path '{m_linux.group(0)}' found in {path.relative_to(REPO_ROOT)}"
            )
            m_darwin = DARWIN_HOME.search(content)
            assert not m_darwin, (
                f"Prohibited workstation path '{m_darwin.group(0)}' found in {path.relative_to(REPO_ROOT)}"
            )

    def test_github_actions_pinned_to_sha(self) -> None:
        """Verify every GitHub Action in .github/workflows/ is pinned to a 40-character commit SHA."""
        assert WORKFLOWS_DIR.exists(), ".github/workflows directory is missing"
        action_pattern = re.compile(r"^\s*-\s+uses:\s+([^\s#]+)")
        sha_pin_pattern = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_./-]+@[a-f0-9]{40}$")

        workflow_files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
        assert len(workflow_files) >= 5, f"Expected >= 5 workflows, found {len(workflow_files)}"

        for wf in workflow_files:
            lines = wf.read_text(encoding="utf-8").splitlines()
            for idx, line in enumerate(lines, 1):
                match = action_pattern.search(line)
                if match:
                    action_target = match.group(1).strip()
                    # Skip local actions (e.g. ./...)
                    if action_target.startswith("./"):
                        continue
                    assert sha_pin_pattern.match(action_target), (
                        f"Unpinned GitHub Action '{action_target}' in {wf.name}:{idx}. "
                        f"Must be pinned to a full 40-character commit SHA."
                    )

    def test_no_unencrypted_private_keys(self) -> None:
        """Verify no unencrypted private keys exist in the repository."""
        for path in publishable_files():
            # Skip gitleaks scanner definitions and test fixtures
            if path.name.startswith(".gitleaks"):
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert not PRIVATE_KEY.search(content), f"Unencrypted private key detected in {path.relative_to(REPO_ROOT)}"

    def test_sensitive_artifacts_gitignored(self) -> None:
        """Verify .gitignore contains patterns for VM images, packer caches, and secrets."""
        assert GITIGNORE_PATH.exists(), ".gitignore is missing"
        gitignore_content = GITIGNORE_PATH.read_text(encoding="utf-8")
        required_patterns = ["output-images", "packer_cache", "*.qcow2", "*.iso", ".env"]
        for pattern in required_patterns:
            assert pattern in gitignore_content, f"Missing '{pattern}' pattern in .gitignore"

    def test_workflows_least_privilege_permissions(self) -> None:
        """Verify no workflow declares write permissions at the top level (OpenSSF Scorecard)."""
        assert WORKFLOWS_DIR.exists(), ".github/workflows directory is missing"
        workflow_files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))

        for wf in workflow_files:
            content = wf.read_text(encoding="utf-8")
            parts = re.split(r"^jobs:\s*$", content, flags=re.MULTILINE)
            top_level = parts[0] if parts else content

            perm_match = re.search(r"^permissions:\s*(.*?)(?=\n[a-zA-Z]|\Z)", top_level, flags=re.MULTILINE | re.DOTALL)
            if perm_match:
                perm_body = perm_match.group(1).strip()
                assert "write-all" not in perm_body, (
                    f"Top-level 'write-all' permission forbidden in {wf.name} (OpenSSF Scorecard rule)."
                )
                for line in perm_body.splitlines():
                    assert ": write" not in line and not line.strip().endswith("write"), (
                        f"Top-level write permission '{line.strip()}' forbidden in {wf.name}. "
                        f"Permissions must be scoped to specific jobs."
                    )


# Planted text for each scan above: the leak a pattern must find, and the documentation
# placeholders and near misses it must let through. A pattern that matches nothing
# passes the tree scans as well, so these cases prove the patterns bite. The leaks are
# joined at run time, so this file holds none of them.
def dotted(*octets: int) -> str:
    return ".".join(str(octet) for octet in octets)


HOME, USERS = "/" + "home/", "/" + "Users/"
PLANTED_LEAKS = [
    (RFC1918, f"host = {dotted(10, 0, 0, 1)}"),
    (RFC1918, f"gateway {dotted(192, 168, 1, 254)}"),
    (RFC1918, dotted(172, 16, 0, 1)),
    (RFC1918, dotted(172, 31, 255, 255)),
    (LINUX_HOME, f"cache={HOME}alice/.cache"),
    (LINUX_HOME, f"{HOME}runnerx/work"),
    (DARWIN_HOME, f"{USERS}bob/src"),
    (PRIVATE_KEY, "-----BEGIN RSA " + "PRIVATE KEY-----"),
    (PRIVATE_KEY, "-----BEGIN " + "PRIVATE KEY-----"),
]
ALLOWED_TEXT = [
    (RFC1918, "host = 192.0.2.10"),
    (RFC1918, "172.15.0.1"),
    (RFC1918, "172.32.0.1"),
    (RFC1918, "110.0.0.1"),
    (RFC1918, "192.169.0.1"),
    (LINUX_HOME, "/home/runner/work"),
    (LINUX_HOME, "/home/ubuntu/.ssh"),
    (LINUX_HOME, "/home/username"),
    (DARWIN_HOME, "/usr/share"),
    (PRIVATE_KEY, "-----BEGIN PUBLIC KEY-----"),
]


@pytest.mark.parametrize(("pattern", "text"), PLANTED_LEAKS, ids=[text for _p, text in PLANTED_LEAKS])
def test_planted_leak_is_found(pattern, text):
    assert pattern.search(text)


@pytest.mark.parametrize(("pattern", "text"), ALLOWED_TEXT, ids=[text for _p, text in ALLOWED_TEXT])
def test_placeholder_or_near_miss_passes(pattern, text):
    assert not pattern.search(text)
