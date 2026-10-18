"""Automated verification suite for the 4-Dimensional Flavor Matrix.

Verifies completeness, pipeline chaining, naming conventions, Makefile targets,
and documentation synchronization across all 44 production flavors.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKER_DIR = REPO_ROOT / "packer"
BUILDS_PKR = PACKER_DIR / "builds.pkr.hcl"
MAKEFILE_PATH = REPO_ROOT / "Makefile"
FLAVORS_MD = REPO_ROOT / "FLAVORS.md"
MATRIX_MD = REPO_ROOT / "docs" / "flavors" / "matrix.md"

EXPECTED_FLAVORS = [
    # Tier 1: Base Cloud OS (8)
    "base-generic",
    "base-intel",
    "base-amd",
    "base-nvidia-legacy",
    "base-nvidia-mainstream",
    "base-nvidia-modern",
    "base-nvidia-bleeding",
    "base-nvidia-datacenter",
    # Tier 2: Container Hosts (7)
    "docker-generic",
    "docker-intel",
    "docker-amd",
    "docker-nvidia",
    "docker-nvidia-modern",
    "docker-nvidia-bleeding",
    "podman-generic",
    # Tier 3: Enterprise Kubernetes Nodes (9)
    "k8s-node-generic",
    "k8s-node-cilium",
    "k8s-node-calico",
    "k8s-node-flannel",
    "k8s-node-intel",
    "k8s-node-amd",
    "k8s-node-nvidia",
    "k8s-node-nvidia-modern",
    "k8s-node-nvidia-bleeding",
    # Tier 4: K3s Edge Fleet (5)
    "k3s-agent-generic",
    "k3s-agent-intel",
    "k3s-agent-amd",
    "k3s-agent-nvidia",
    "k3s-server-generic",
    # Tier 5: Cloud-Native Immutable & Storage (4)
    "cloudnative-generic",
    "cloudnative-k8s",
    "cloudnative-storage",
    "cloudnative-pg",
    # Tier 6: AI Inference Appliances (6)
    "ai-infer-generic",
    "ai-infer-intel",
    "ai-infer-amd",
    "ai-infer-nvidia",
    "ai-infer-nvidia-modern",
    "ai-infer-nvidia-bleeding",
    # Tier 7: Specialized Homelab Appliances (5)
    "appliance-vision-nvr",
    "appliance-gateway-dns",
    "appliance-media-server",
    "appliance-ci-runner",
    "appliance-game-server",
]


def build_scripts(content: str) -> list[tuple[str, str]]:
    """(name, scripts list text) per top-level build block; blocks start at a `build {` line."""
    found = []
    for block in re.split(r"(?m)^build\s*\{", content)[1:]:
        name = re.search(r'^\s*name\s*=\s*"([^"]+)"', block, re.MULTILINE)
        scripts = re.search(r"scripts\s*=\s*\[(.*?)\]", block, re.DOTALL)
        if name and scripts:
            found.append((name.group(1), scripts.group(1)))
    return found


class TestFlavorsIntegrity:
    def test_expected_flavors_count(self) -> None:
        """Verify the exact count of active production flavors."""
        assert len(EXPECTED_FLAVORS) == 44, f"Expected 44 flavors, got {len(EXPECTED_FLAVORS)}"

    def test_naming_convention(self) -> None:
        """Verify all flavor targets conform to the canonical naming regex."""
        pattern = re.compile(
            r"^(base|docker|podman|k8s-node|k3s-agent|k3s-server|cloudnative|ai-infer|appliance)-[a-z0-9-]+$"
        )
        for flavor in EXPECTED_FLAVORS:
            assert pattern.match(flavor), f"Flavor '{flavor}' violates naming convention"

    def test_all_flavors_defined_in_builds(self) -> None:
        """Verify every flavor has a build block in builds.pkr.hcl."""
        content = BUILDS_PKR.read_text(encoding="utf-8")
        for flavor in EXPECTED_FLAVORS:
            assert f'name    = "{flavor}"' in content, f"Missing build definition for {flavor}"

    def test_all_flavors_have_make_targets(self) -> None:
        """Verify every flavor has a corresponding build-<flavor> target in Makefile."""
        makefile_content = MAKEFILE_PATH.read_text(encoding="utf-8")
        for flavor in EXPECTED_FLAVORS:
            # Check for direct or alias targets (e.g., build-base-generic or build-k8s-generic)
            target = f"build-{flavor}:"
            # Allow common k8s-node short aliases (build-k8s-*)
            short_k8s = target.replace("build-k8s-node-", "build-k8s-")
            assert target in makefile_content or short_k8s in makefile_content, (
                f"Missing Makefile target for flavor: {flavor}"
            )

    def test_all_flavors_in_catalog_and_matrix(self) -> None:
        """Verify every flavor is documented in both FLAVORS.md and docs/flavors/matrix.md."""
        flavors_content = FLAVORS_MD.read_text(encoding="utf-8")
        matrix_content = MATRIX_MD.read_text(encoding="utf-8")
        for flavor in EXPECTED_FLAVORS:
            assert f"`{flavor}`" in flavors_content, f"Flavor {flavor} missing from FLAVORS.md"
            assert f"`{flavor}`" in matrix_content, f"Flavor {flavor} missing from matrix.md"

    def test_pipeline_chain_invariants(self) -> None:
        """Verify all build blocks start with 00-base-strip and terminate with 99-cleanup."""
        content = BUILDS_PKR.read_text(encoding="utf-8")
        build_blocks = build_scripts(content)
        assert len(build_blocks) >= 44, "Failed to parse build blocks from builds.pkr.hcl"

        for name, scripts_raw in build_blocks:
            scripts = [s.strip().strip('"').strip("'") for s in scripts_raw.split(",") if s.strip()]
            assert len(scripts) >= 4, f"Build {name} has fewer than 4 provisioner steps"
            assert "00-base-strip.sh" in scripts[0], f"Build {name} must start with 00-base-strip.sh"
            assert "99-cleanup.sh" in scripts[-1], f"Build {name} must end with 99-cleanup.sh"
            assert "98-structure-test.sh" in scripts[-2], (
                f"Build {name} must run 98-structure-test.sh immediately before 99-cleanup.sh"
            )
            assert "80-netboot-initrd.sh" in scripts[-3], (
                f"Build {name} must run 80-netboot-initrd.sh immediately before 98-structure-test.sh"
            )

    def test_every_build_lists_netboot_initrd_provisioner(self) -> None:
        """Verify all 44 build definitions list 80-netboot-initrd.sh."""
        content = BUILDS_PKR.read_text(encoding="utf-8")
        build_blocks = build_scripts(content)
        assert len(build_blocks) >= 44, "Failed to parse build blocks from builds.pkr.hcl"
        for name, scripts_raw in build_blocks:
            assert "80-netboot-initrd.sh" in scripts_raw, (
                f"Build {name} is missing 80-netboot-initrd.sh in its provisioners list"
            )

    def test_no_orphan_provisioner_scripts(self) -> None:
        """Verify every provisioner script in packer/provisioners/ is utilized in builds."""
        content = BUILDS_PKR.read_text(encoding="utf-8")
        provisioner_files = (PACKER_DIR / "provisioners").glob("*.sh")
        for p_file in provisioner_files:
            assert p_file.name in content, f"Provisioner script {p_file.name} is not referenced in builds.pkr.hcl"

    def test_go_catalog_provisioners_synchrony(self) -> None:
        """Verify every provisioner in pkg/flavors/flavors.go exists in packer/provisioners/."""
        go_file = REPO_ROOT / "pkg" / "flavors" / "flavors.go"
        assert go_file.is_file(), "pkg/flavors/flavors.go must exist"
        go_content = go_file.read_text(encoding="utf-8")

        matches = re.findall(r"Provisioners:\s*\[\]string\{([^}]+)\}", go_content)
        all_go_provisioners = set()
        for m in matches:
            scripts = [s.strip().strip('"') for s in m.split(",") if s.strip()]
            all_go_provisioners.update(scripts)

        actual_provisioners = {p.name for p in (PACKER_DIR / "provisioners").glob("*.sh")}
        diff = all_go_provisioners - actual_provisioners
        assert not diff, f"Provisioner scripts in Go catalog not found in packer/provisioners/: {diff}"
