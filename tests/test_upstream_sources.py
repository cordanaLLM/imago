# Copyright 2026 Lusoris
"""Tests for the upstream source pre-flight (tools/ci/upstream_sources.py).

The ROCm provisioner fetched a key name, release and apt suite that repo.radeon.com does not
publish, and the build failed with a 404 about 20 minutes in. NVIDIA tiers pinned branches the
Ubuntu archive does not carry (565) or carries only as transitional packages that install
another branch (535, 610), and qemu-user-static has no installation candidate. These tests run
the check against a simulated upstream that publishes exactly the current pins, then plant one
unpublished pin per kind and require the check to name it.
"""

from __future__ import annotations

import copy
import gzip
import importlib.util
import json
import lzma
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "ci" / "upstream_sources.py"
PROVISIONERS = REPO_ROOT / "packer" / "provisioners"
ROCM_SCRIPT = PROVISIONERS / "32-gpu-amd-rocm.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-matrix.yml"
MANIFEST = json.loads((REPO_ROOT / "versions.json").read_text(encoding="utf-8"))

_SPEC = importlib.util.spec_from_file_location("upstream_sources", TOOL)
assert _SPEC is not None and _SPEC.loader is not None
upstream_sources = importlib.util.module_from_spec(_SPEC)
sys.modules["upstream_sources"] = upstream_sources
_SPEC.loader.exec_module(upstream_sources)

SCRIPTS = upstream_sources.provisioner_scripts()


def stanza(name: str, version: str, depends: str = "", provides: str = "", section: str = "misc") -> str:
    lines = [f"Package: {name}", f"Version: {version}", f"Section: {section}"]
    lines += [f"Depends: {depends}"] if depends else []
    lines += [f"Provides: {provides}"] if provides else []
    return "\n".join(lines)


def nvidia_stanzas(manifest: dict) -> list[str]:
    nvidia = manifest["drivers"]["nvidia"]
    stanzas = []
    for driver_key, _, templates in upstream_sources.NVIDIA_TIERS.values():
        branch = nvidia[driver_key]
        stanzas += [stanza(t.format(b=branch), f"{branch}.10.01-0ubuntu1") for t in templates]
    return stanzas


def cuda_stanzas(manifest: dict) -> list[str]:
    nvidia = manifest["drivers"]["nvidia"]
    return [
        stanza("cuda-compat-" + nvidia[cuda_key].replace(".", "-"), f"{nvidia[driver_key]}.10.01-1")
        for driver_key, cuda_key, _ in upstream_sources.NVIDIA_TIERS.values()
        if cuda_key is not None
    ]


def script_stanzas(scripts: dict[str, str]) -> list[str]:
    names = set()
    for text in scripts.values():
        names |= {name.split(":")[0] for name in upstream_sources.literal_packages(text)[0]}
    return [stanza(name, "1.0-1") for name in sorted(names)]


def encode(url: str, text: str) -> bytes:
    body = text.encode("utf-8")
    if url.endswith(".xz"):
        return lzma.compress(body)
    return gzip.compress(body) if url.endswith(".gz") else body


class Upstream:
    """Simulated upstream that publishes exactly what the current manifest pins."""

    def __init__(self, manifest: dict = MANIFEST, scripts: dict[str, str] = SCRIPTS) -> None:
        self.urls = set(upstream_sources.source_urls(manifest))
        self.images = set(upstream_sources.image_refs(manifest))
        release = manifest["distro"]["release"]
        self.files = {
            f"{upstream_sources.ARCHIVE}/dists/{release}/main/binary-amd64/Packages.xz": nvidia_stanzas(manifest)
            + script_stanzas(scripts),
            f"{upstream_sources.ARCHIVE}/dists/{release}/main/binary-i386/Packages.xz": script_stanzas(scripts),
            upstream_sources.CUDA_INDEX: cuda_stanzas(manifest),
            upstream_sources.vendor_urls(manifest)[0]: [
                stanza("docker-ce", f"5:{manifest['runtimes']['docker_ce']}.0-1")
            ],
            upstream_sources.vendor_urls(manifest)[1]: [stanza("kubelet", f"{manifest['kubernetes']['version']}-1.1")],
            upstream_sources.NVIDIA_TOOLKIT_INDEX: [
                stanza("nvidia-container-toolkit", f"{manifest['drivers']['nvidia']['container_toolkit']}-1")
            ],
        }

    def read(self, url: str) -> bytes:
        return encode(url, "\n\n".join(self.files.get(url, [])) + "\n")

    def probes(self):
        return upstream_sources.Probes(
            fetch=lambda url: 200 if url in self.urls else 404,
            read=self.read,
            image=lambda ref: 200 if ref in self.images else 404,
        )


def run_check(manifest: dict, tmp_path: Path, upstream: Upstream | None = None, scripts=None) -> int:
    path = tmp_path / "versions.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    probes = (upstream or Upstream()).probes()
    return upstream_sources.main(["check", "--manifest", str(path)], probes=probes, scripts=scripts)


def planted(section: str, field: str, value: str, parent: str | None = None) -> dict:
    manifest = copy.deepcopy(MANIFEST)
    target = manifest[parent][section] if parent else manifest[section]
    target[field] = value
    return manifest


def test_check_passes_when_upstream_publishes_every_pin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_check(MANIFEST, tmp_path) == 0
    assert "0 upstream sources missing" in capsys.readouterr().out


@pytest.mark.parametrize(
    "pin",
    [
        ("amd", "rocm_bleeding_version", "10.0", "drivers"),
        ("amd", "rocm_legacy_version", "7.14", "drivers"),
        ("amd", "rocm_apt_suite", "resolute", "drivers"),
        ("tools", "cdebug", "0.5.1", None),
        ("tools", "enroot", "9.9.9", None),
        ("tools", "container_structure_test", "9.9.9", None),
        ("runtimes", "stargz_snapshotter", "9.9.9", None),
        ("k3s", "version", "v9.9.9+k3s1", None),
        ("runtimes", "containerd", "9.9.9", None),
    ],
)
def test_check_refuses_an_unpublished_url_pin(
    pin: tuple[str, str, str, str | None], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    value = pin[2]
    assert run_check(planted(*pin), tmp_path) == 1
    err = capsys.readouterr().err
    assert "404" in err
    assert value.replace("+", "%2B") in err


def test_check_refuses_an_unpublished_image_tag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = copy.deepcopy(MANIFEST)
    name = next(iter(manifest["kubernetes"]["images"]))
    manifest["kubernetes"]["images"][name] = "quay.io/example/fictional:v0.0.0-planted"
    assert run_check(manifest, tmp_path) == 1
    assert "404 image quay.io/example/fictional:v0.0.0-planted" in capsys.readouterr().err


def test_check_refuses_an_unpublished_device_plugin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        run_check(planted("nvidia", "k8s_plugin", "nvcr.io/nvidia/k8s-device-plugin:v0.0.0", "drivers"), tmp_path) == 1
    )
    assert "image nvcr.io/nvidia/k8s-device-plugin:v0.0.0" in capsys.readouterr().err


@pytest.mark.parametrize("branch", ["565", "999"])
def test_check_refuses_a_driver_branch_the_archive_lacks(
    branch: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    upstream = Upstream()
    assert run_check(planted("nvidia", "mainstream_driver", branch, "drivers"), tmp_path, upstream) == 1
    assert f"nvidia-headless-{branch} is not in the Ubuntu archive" in capsys.readouterr().err


def test_check_refuses_a_transitional_driver_branch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ubuntu replaced 610 with packages that only pull in 615: a silent branch swap."""
    upstream = Upstream()
    archive = next(url for url in upstream.files if url.endswith("binary-amd64/Packages.xz"))
    upstream.files[archive] += [
        stanza("nvidia-headless-610-open", "610.57-0ubuntu1", depends="nvidia-headless-615-open"),
        stanza("nvidia-utils-610", "610.57-0ubuntu1", depends="nvidia-utils-615"),
    ]
    manifest = planted("nvidia", "modern_driver", "610", "drivers")
    manifest["drivers"]["nvidia"]["cuda_modern"] = manifest["drivers"]["nvidia"]["cuda_bleeding"]
    assert run_check(manifest, tmp_path, upstream) == 1
    assert "nvidia-utils-610 is a transitional package that installs nvidia-utils-615" in capsys.readouterr().err


def test_an_oldlibs_package_is_transitional() -> None:
    record = {"Section": "restricted/oldlibs", "Depends": "nvidia-headless-580"}
    assert upstream_sources.transitional_target(record, "nvidia-headless-535") == "nvidia-headless-580"


def test_a_package_that_depends_on_one_other_package_is_not_transitional() -> None:
    """nvidia-fabricmanager-615 depends on nvidia-kernel-common only and is a real package."""
    record = {"Section": "multiverse/libs", "Depends": "nvidia-kernel-common-615-server-615.71.09"}
    assert upstream_sources.transitional_target(record, "nvidia-fabricmanager-615") is None


def test_check_refuses_a_branch_pin_with_a_suffix(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_check(planted("nvidia", "datacenter_driver", "615-open", "drivers"), tmp_path) == 1
    assert "driver pin '615-open' is not a three-digit branch" in capsys.readouterr().err


def test_check_refuses_a_cuda_label_of_another_branch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    upstream = Upstream()
    upstream.files[upstream_sources.CUDA_INDEX].append(stanza("cuda-compat-12-8", "570.211.01-1"))
    assert run_check(planted("nvidia", "cuda_mainstream", "12.8", "drivers"), tmp_path, upstream) == 1
    pinned = MANIFEST["drivers"]["nvidia"]["mainstream_driver"]
    assert f"CUDA 12.8 pairs with driver 570, the tier pins {pinned}" in capsys.readouterr().err


def test_check_refuses_an_unpublished_cuda_release(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_check(planted("nvidia", "cuda_legacy", "12.2", "drivers"), tmp_path) == 1
    assert "CUDA 12.2 is not published" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("section", "field", "parent"),
    [("runtimes", "docker_ce", None), ("kubernetes", "version", None), ("nvidia", "container_toolkit", "drivers")],
)
def test_check_refuses_an_unpublished_apt_version(
    section: str, field: str, parent: str | None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_check(planted(section, field, "0.0.1", parent), tmp_path) == 1
    assert re.search(r"apt pin \S+ 0\.0\.1 is not published", capsys.readouterr().err)


def test_check_refuses_a_virtual_package_with_two_providers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """apt answers 'has no installation candidate' for qemu-user-static on Ubuntu 26.04."""
    scripts = {"78-appliance-runner.sh": "sudo apt-get install -y \\\n  qemu-user-static \\\n  binfmt-support\n"}
    upstream = Upstream(scripts=scripts)
    archive = next(url for url in upstream.files if url.endswith("binary-amd64/Packages.xz"))
    upstream.files[archive] = [s for s in upstream.files[archive] if "qemu-user-static" not in s] + [
        stanza("qemu-user-binfmt", "1:10.2.1", provides="qemu-user-static"),
        stanza("qemu-user-binfmt-hwe", "1:10.2.1", provides="qemu-user-static"),
    ]
    assert run_check(MANIFEST, tmp_path, upstream, scripts) == 1
    err = capsys.readouterr().err
    assert "78-appliance-runner.sh: apt package qemu-user-static is a virtual package with 2 providers" in err


def test_a_virtual_package_with_one_provider_has_a_candidate() -> None:
    index = upstream_sources.Index(provides={"mesa-va-drivers": {"mesa-libgallium"}})
    assert upstream_sources.candidate_problem("mesa-va-drivers", [index]) is None


def test_a_package_no_repository_carries_has_no_candidate() -> None:
    problem = upstream_sources.candidate_problem("fictional-planted-package", [upstream_sources.Index()])
    assert problem == "is not in any configured repository"


def test_a_package_guarded_by_apt_cache_show_is_optional() -> None:
    script = "if apt-cache show hyperv-daemons >/dev/null; then\n  sudo apt-get install -y hyperv-daemons\nfi\n"
    assert upstream_sources.package_failures({"05.sh": script}, [upstream_sources.Index()], []) == []


def test_a_script_that_adds_i386_resolves_against_the_i386_archive() -> None:
    script = "sudo dpkg --add-architecture i386\nsudo apt-get install -y steamcmd lib32gcc-s1\n"
    i386 = upstream_sources.Index(records={"steamcmd": {}, "lib32gcc-s1": {}})
    assert upstream_sources.package_failures({"79.sh": script}, [upstream_sources.Index()], [i386]) == []
    assert upstream_sources.package_failures({"79.sh": script.splitlines()[1]}, [upstream_sources.Index()], [i386])


def test_literal_packages_skip_flags_variables_and_comments() -> None:
    script = '# apt-get install commented-out\nsudo apt-get install -y --no-install-recommends \\\n  jq \\\n  nvidia-utils-"${B}" \\\n  libc6:i386\n'
    assert upstream_sources.literal_packages(script)[0] == ["jq", "libc6:i386"]
    local_debs = 'if ! (cd "${t}" && sudo apt-get install -y "./${deb_main}" "./${deb_caps}"); then\n'
    assert upstream_sources.literal_packages(local_debs)[0] == []


def test_every_provisioner_package_is_extracted() -> None:
    """Guards the extractor: a regex that matches nothing would pass every script."""
    names = upstream_sources.literal_packages(SCRIPTS["78-appliance-runner.sh"])[0]
    assert {"qemu-user-binfmt", "binfmt-support", "git-lfs"} <= set(names)
    total = sum(len(upstream_sources.literal_packages(text)[0]) for text in SCRIPTS.values())
    assert total > 50


@pytest.mark.parametrize("tier", list(upstream_sources.NVIDIA_TIERS))
def test_nvidia_provisioners_install_the_checked_packages(tier: str) -> None:
    """The check and the provisioner must name the same packages, with the branch from versions.json."""
    script = next(text for name, text in SCRIPTS.items() if re.match(rf"3\d-gpu-nvidia-{tier}\.sh", name))
    for template in upstream_sources.NVIDIA_TIERS[tier][2]:
        assert template.replace("{b}", '"${DRIVER_BRANCH}"') in script, template
    assert re.search(r'DRIVER_BRANCH="\$\{NVIDIA_\w+:\?', script), "the branch must come from versions.json"
    assert "falling back" not in script and "|| {" not in script


def test_registry_parts_maps_docker_hub_to_its_registry() -> None:
    assert upstream_sources.registry_parts("docker.io/flannel/flannel:v0.28.9") == (
        "registry-1.docker.io",
        "flannel/flannel",
        "v0.28.9",
    )
    assert upstream_sources.registry_parts("docker.io/busybox:1.37")[1] == "library/busybox"
    assert upstream_sources.registry_parts("ghcr.io/kube-vip/kube-vip:v1.2.3")[0] == "ghcr.io"


def test_rocm_urls_follow_versions_json() -> None:
    amd = MANIFEST["drivers"]["amd"]
    urls = upstream_sources.rocm_urls(MANIFEST)
    assert urls[0] == f"{amd['rocm_repo']}/rocm.gpg.key"
    for key in ("rocm_bleeding_version", "rocm_legacy_version"):
        assert f"{amd['rocm_repo']}/apt/{amd[key]}/dists/{amd['rocm_apt_suite']}/Release" in urls


def test_check_reports_every_missing_url() -> None:
    urls = upstream_sources.source_urls(MANIFEST)
    assert upstream_sources.missing(urls, lambda url: 404) == [f"404 {url}" for url in urls]


def test_provisioner_fetches_the_checked_urls() -> None:
    """The provisioner must build the same key and apt URL the pre-flight checks."""
    script = ROCM_SCRIPT.read_text(encoding="utf-8")
    assert '"${ROCM_REPO}/rocm.gpg.key"' in script
    assert "${ROCM_REPO}/apt/${ROCM_VERSION} ${ROCM_APT_SUITE} main" in script
    assert "repo.radeon.com/rocm/" not in script.replace("o=repo.radeon.com", "")


def test_provisioner_fails_on_a_failed_index_update() -> None:
    script = ROCM_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"apt-get update\s*\|\|", script) is None


def test_preflight_runs_before_the_packer_build() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build-matrix"]["steps"]
    names = [step.get("name", "") for step in steps]
    check = names.index("Check Upstream Package Sources")
    assert "tools/ci/upstream_sources.py check" in steps[check]["run"]
    assert check < names.index("Build Image with Packer")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://repo.radeon.com/rocm/rocm.gpg.key"])
def test_http_probes_refuse_a_url_that_is_not_https(url: str) -> None:
    with pytest.raises(ValueError, match="not an https URL"):
        upstream_sources.http_status(url)
    with pytest.raises(ValueError, match="not an https URL"):
        upstream_sources.http_read(url)


def test_opener_has_no_handler_for_other_schemes() -> None:
    opener = upstream_sources.https_opener()
    schemes = {name[: -len("_open")] for handler in opener.handlers for name in dir(handler) if name.endswith("_open")}
    assert "https" in schemes
    assert not schemes & {"file", "ftp", "http", "data"}
