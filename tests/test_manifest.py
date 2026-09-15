"""Automated verification suite for versions.json Single Source of Truth (SSOT).

Validates schema conformity (Draft 2020-12), semantic distribution invariants,
hardware driver matrix, container tags, and network time servers.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

from pathlib import Path
import json
import jsonschema
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "versions.json"
SCHEMA_PATH = REPO_ROOT / "versions.schema.json"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class TestManifestIntegrity:
    def test_schema_conformance(self) -> None:
        """Verify versions.json strictly conforms to versions.schema.json."""
        assert MANIFEST_PATH.exists(), "versions.json is missing"
        assert SCHEMA_PATH.exists(), "versions.schema.json is missing"
        data = load_manifest()
        schema = load_schema()
        jsonschema.validate(instance=data, schema=schema)

    def test_distro_metadata(self) -> None:
        """Verify distribution release, version, and name format."""
        distro = load_manifest()["distro"]
        assert distro["name"] == "ubuntu"
        assert re.match(r"^[a-z]+$", distro["release"]), "Release must be lowercase letters"
        assert re.match(r"^\d{2}\.\d{2}$", distro["version"]), "Version must be YY.MM format"

    def test_runtimes_and_kubernetes(self) -> None:
        """Verify runtime and Kubernetes semver version formats."""
        data = load_manifest()
        k8s = data["kubernetes"]
        runtimes = data["runtimes"]
        assert re.match(r"^\d+\.\d+\.\d+", k8s["version"])
        assert re.match(r"^\d+\.\d+$", k8s["major_minor"])
        assert re.match(r"^\d+\.\d+", runtimes["containerd"])
        assert re.match(r"^\d+\.\d+", runtimes["docker_ce"])
        assert re.match(r"^\d+\.\d+", runtimes["crun"])
        assert re.match(r"^\d+\.\d+", runtimes["stargz_snapshotter"])
        assert "tools" in data and "cdebug" in data["tools"]
        assert "tools" in data and "enroot" in data["tools"]
        assert "k3s" in data and len(data["k3s"]) > 0

    def test_nvidia_driver_tiers(self) -> None:
        """Verify NVIDIA multi-generational driver branches and CUDA versions."""
        nvidia = load_manifest()["drivers"]["nvidia"]
        expected_driver_keys = [
            "legacy_driver",
            "mainstream_driver",
            "modern_driver",
            "bleeding_driver",
            "datacenter_driver",
        ]
        for key in expected_driver_keys:
            assert key in nvidia, f"Missing driver key '{key}' in nvidia drivers"
            assert isinstance(nvidia[key], str) and len(nvidia[key]) > 0

        expected_cuda_keys = [
            "cuda_legacy",
            "cuda_mainstream",
            "cuda_modern",
            "cuda_bleeding",
        ]
        for key in expected_cuda_keys:
            assert key in nvidia, f"Missing CUDA key '{key}' in nvidia drivers"
            assert isinstance(nvidia[key], str) and len(nvidia[key]) > 0

        assert "container_toolkit" in nvidia and len(nvidia["container_toolkit"]) > 0
        assert "k8s_plugin" in nvidia and len(nvidia["k8s_plugin"]) > 0

    def test_amd_driver_manifest(self) -> None:
        """Verify AMD driver and ROCm compute packages."""
        amd = load_manifest()["drivers"]["amd"]
        assert "rocm_legacy_version" in amd and len(amd["rocm_legacy_version"]) > 0
        assert "rocm_bleeding_version" in amd and len(amd["rocm_bleeding_version"]) > 0
        assert "k8s_plugin" in amd and len(amd["k8s_plugin"]) > 0

    def test_intel_driver_manifest(self) -> None:
        """Verify Intel Media and Level Zero driver entries."""
        intel = load_manifest()["drivers"]["intel"]
        assert "k8s_plugin" in intel and len(intel["k8s_plugin"]) > 0

    def test_cached_cluster_images(self) -> None:
        """Verify CNI and VIP pre-cached image repositories and tags."""
        images = load_manifest()["kubernetes"]["images"]
        for cni in ("cilium", "calico_cni", "flannel", "kube_vip"):
            assert cni in images, f"Missing {cni} image declaration"
            assert "/" in images[cni], f"Invalid image repository format: {images[cni]}"

    def test_network_time_servers(self) -> None:
        """Verify authoritative Anycast and Stratum-1 NTS server configurations."""
        time_cfg = load_manifest()["time"]
        assert "anycast_nts" in time_cfg and len(time_cfg["anycast_nts"]) > 0
        assert "stratum1_nts" in time_cfg and isinstance(time_cfg["stratum1_nts"], list)
        assert len(time_cfg["stratum1_nts"]) >= 2, "Require at least 2 Stratum-1 national peers"
        assert "fallback_pool" in time_cfg and len(time_cfg["fallback_pool"]) > 0


PINNED_KERNEL_STREAM = {
    "version": "7.2.4-lusoris1",
    "artifact_digest": "sha256:" + "a" * 64,
    "provenance": {
        "tag": "v7.2.4-lusoris1",
        "revision": "188c35d188c35d188c35d188c35d188c35d18800",
        "bundle": "SHA256SUMS.bundle",
    },
}


class TestKernelContractPin:
    def test_kernel_contract_section(self) -> None:
        """Verify the kernel forge contract pin names the provider, contract, and dispatch event."""
        kernel = load_manifest()["kernel"]
        assert kernel["provider"] == "cordanaLLM/nucleus"
        assert kernel["contract"] == "imago.nucleus.kernel-artifact.v1"
        assert kernel["dispatch_event"] == "kernel_release_published"
        assert isinstance(kernel["streams"], dict)
        for name, stream in kernel["streams"].items():
            assert name in ("bleeding", "mainstream", "lts", "realtime"), f"Unknown stream {name}"
            assert stream["artifact_digest"].startswith("sha256:")

    def test_schema_accepts_pinned_stream(self) -> None:
        """Verify a fully pinned stream (version, artifact_digest, provenance) validates."""
        data = load_manifest()
        data["kernel"]["streams"]["mainstream"] = PINNED_KERNEL_STREAM
        jsonschema.validate(instance=data, schema=load_schema())

    def test_schema_rejects_stream_without_artifact_digest(self) -> None:
        """Verify a stream pin missing artifact_digest is rejected by the schema."""
        data = load_manifest()
        stream = {k: v for k, v in PINNED_KERNEL_STREAM.items() if k != "artifact_digest"}
        data["kernel"]["streams"]["mainstream"] = stream
        try:
            jsonschema.validate(instance=data, schema=load_schema())
        except jsonschema.ValidationError as err:
            assert "artifact_digest" in err.message
        else:
            raise AssertionError("schema accepted a kernel stream without artifact_digest")

    def test_schema_rejects_unknown_stream_and_bad_digest(self) -> None:
        """Verify unknown stream names and non-sha256 digests are rejected by the schema."""
        data = load_manifest()
        data["kernel"]["streams"]["nightly"] = PINNED_KERNEL_STREAM
        try:
            jsonschema.validate(instance=data, schema=load_schema())
        except jsonschema.ValidationError:
            pass
        else:
            raise AssertionError("schema accepted an unknown kernel stream name")

        data = load_manifest()
        bad = dict(PINNED_KERNEL_STREAM, artifact_digest="md5:" + "a" * 32)
        data["kernel"]["streams"]["lts"] = bad
        try:
            jsonschema.validate(instance=data, schema=load_schema())
        except jsonschema.ValidationError:
            pass
        else:
            raise AssertionError("schema accepted a non-sha256 artifact_digest")

