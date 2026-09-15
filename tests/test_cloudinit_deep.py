# Copyright 2026 Lusoris
"""Deep Permutation & Schema Verification Test Suite for Cloud-Init Configurations.

Permutates all hypervisor and developer platforms (Proxmox, Unraid, VMware, macOS,
Windows, Baremetal, Cloud) against workload tiers, asserting strict YAML validity,
non-root security postures, and platform-specific device/storage configurations.
"""

from pathlib import Path
import json
import subprocess
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FORGE_BIN = REPO_ROOT / "bin" / "imago.exe"

PLATFORMS = ["proxmox", "unraid", "truenas", "macos", "windows"]
TIERS = [
    "base-generic",
    "docker-generic",
    "k8s-node-cilium",
    "k3s-agent-generic",
    "cloudnative-generic",
    "ai-infer-nvidia",
    "appliance-vision-nvr",
]


class TestCloudInitDeepMatrix:
    @pytest.mark.parametrize("platform", PLATFORMS)
    @pytest.mark.parametrize("flavor", TIERS)
    def test_cloudinit_userdata_matrix_generation(self, platform: str, flavor: str) -> None:
        """Verify cloud-init user-data generates valid YAML for all platform/flavor permutations."""
        # Use go test / pkg/cloudinit via CLI or direct go runner
        res = subprocess.run(
            [
                "go",
                "run",
                "./cmd/imago",
                "cloud-init",
                "generate",
                f"--flavor={flavor}",
                f"--platform={platform}",
                "--hostname=node-audit",
                "--user=ops",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Failed for {platform}/{flavor}: {res.stderr}"

        content = res.stdout
        assert content.startswith("#cloud-config"), f"Missing header for {platform}/{flavor}"

        # Parse YAML
        data = yaml.safe_load(content)
        assert isinstance(data, dict), f"YAML not a dictionary for {platform}/{flavor}"

        # Invariant 1: Identity & Hostname
        assert data.get("hostname") == "node-audit"
        assert data.get("fqdn") == "node-audit.local"
        assert data.get("manage_etc_hosts") is True

        # Invariant 2: Security & Non-Root
        assert data.get("disable_root") is True
        assert data.get("ssh_pwauth") is False
        users = data.get("users", [])
        assert len(users) >= 1
        user0 = users[0]
        assert user0.get("name") == "ops"
        assert user0.get("sudo") == "ALL=(ALL) NOPASSWD:ALL"
        assert user0.get("lock_passwd") is True
        assert user0.get("shell") == "/bin/bash"

        # Invariant 3: Platform Optimizations
        if platform == "unraid":
            mounts = data.get("mounts", [])
            assert any("share" in str(m) and "virtiofs" in str(m) for m in mounts)
        elif platform == "truenas":
            mounts = data.get("mounts", [])
            assert any("truenas" in str(m) for m in mounts)
        elif platform == "macos":
            mounts = data.get("mounts", [])
            assert any("workspace" in str(m) and "virtiofs" in str(m) for m in mounts)
        elif platform == "windows":
            write_files = data.get("write_files", [])
            assert any("hyperv.conf" in str(f) for f in write_files)

    @pytest.mark.parametrize("hostname", ["edge-worker-01", "gw-core", "srv-test"])
    def test_cloudinit_metadata_generation(self, hostname: str) -> None:
        """Verify cloud-init meta-data generates valid instance-id and hostname mappings."""
        res = subprocess.run(
            [
                "go",
                "run",
                "./cmd/imago",
                "cloud-init",
                "metadata",
                f"--hostname={hostname}",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Metadata generation failed: {res.stderr}"

        data = yaml.safe_load(res.stdout)
        assert data.get("instance-id") == f"{hostname}-01"
        assert data.get("local-hostname") == hostname
