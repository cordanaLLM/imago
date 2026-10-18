#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Check that every upstream source and pin a flavor build needs exists before the build.

A provisioner that fetches a missing key, release asset or apt package fails only after the
image has been installed and booted, about 20 minutes into a Packer build. This check resolves
the same sources from versions.json and the provisioners and asks each upstream, so a pin the
vendor does not publish fails the build job in seconds. It covers:

- URLs: apt keys and Release files, release assets, the cloud image checksum, release tags.
- Images: every preheated container image and device plugin, by registry manifest.
- NVIDIA tiers: each tier's packages exist in the Ubuntu archive, carry the pinned branch and
  are not transitional packages that install another branch.
- CUDA labels: NVIDIA's cuda-compat package for the pinned CUDA release requires the tier's
  driver branch.
- Apt version pins: the pinned docker-ce, kubelet and Container Toolkit releases are published.
- Provisioner packages: every literal package an `apt-get install` names has an installation
  candidate: a real package, or a virtual one with exactly one provider, as apt requires.

The urls command prints the URLs and images; the check command asks for them and exits 1
naming every source that is missing.
"""

from __future__ import annotations

import argparse
import dataclasses
import gzip
import json
import lzma
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROVISIONERS = ROOT / "packer" / "provisioners"
TIMEOUT_SECONDS = 30
MAX_URLS = 64
MAX_IMAGES = 32
MAX_INDEX_BYTES = 128 * 1024 * 1024
MAX_SCRIPTS = 128
# get.k3s.io answers 403 to urllib's default User-Agent; name the check instead.
USER_AGENT = "imago-upstream-sources/1 (+https://github.com/cordanaLLM/imago)"

ARCHIVE = "https://archive.ubuntu.com/ubuntu"
ARCHIVE_COMPONENTS = ("main", "restricted", "universe", "multiverse")
# NVIDIA's CUDA repository for Ubuntu 24.04 lists cuda-compat for every CUDA release from 12.4
# on; the 26.04 repository starts at 13.2. The CUDA-to-driver pairing is the same in both.
CUDA_INDEX = "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/Packages.gz"
NVIDIA_TOOLKIT_INDEX = "https://nvidia.github.io/libnvidia-container/stable/deb/amd64/Packages"
MANIFEST_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)

# Tier -> (driver pin, CUDA pin, packages its provisioner installs). The provisioners name the
# same packages; tests/test_upstream_sources.py keeps the two in step.
NVIDIA_TIERS: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    "legacy": ("legacy_driver", "cuda_legacy", ("nvidia-headless-{b}", "nvidia-utils-{b}")),
    "mainstream": ("mainstream_driver", "cuda_mainstream", ("nvidia-headless-{b}", "nvidia-utils-{b}")),
    "modern": ("modern_driver", "cuda_modern", ("nvidia-headless-{b}-open", "nvidia-utils-{b}")),
    "bleeding": ("bleeding_driver", "cuda_bleeding", ("nvidia-headless-{b}-open", "nvidia-utils-{b}")),
    "datacenter": (
        "datacenter_driver",
        None,
        ("nvidia-headless-{b}-server-open", "nvidia-utils-{b}-server", "nvidia-fabricmanager-{b}"),
    ),
}

Fetch = Callable[[str], int]
Read = Callable[[str], bytes]
Image = Callable[[str], int]


@dataclasses.dataclass
class Index:
    """Packages index: first record per name in priority order, every version, providers."""

    records: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    versions: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    provides: dict[str, set[str]] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Probes:
    fetch: Fetch
    read: Read
    image: Image


def rocm_urls(manifest: dict) -> list[str]:
    """Return the ROCm key and the apt Release file of every pinned ROCm version."""
    amd = manifest["drivers"]["amd"]
    repo = amd["rocm_repo"]
    suite = amd["rocm_apt_suite"]
    urls = [f"{repo}/rocm.gpg.key"]
    for key in ("rocm_bleeding_version", "rocm_legacy_version"):
        urls.append(f"{repo}/apt/{amd[key]}/dists/{suite}/Release")
    return urls


def repository_urls(manifest: dict) -> list[str]:
    """Return the keys and Release files of the Docker, Kubernetes and NVIDIA repositories."""
    release = manifest["distro"]["release"]
    k8s = f"https://pkgs.k8s.io/core:/stable:/v{manifest['kubernetes']['major_minor']}/deb"
    return [
        "https://download.docker.com/linux/ubuntu/gpg",
        f"https://download.docker.com/linux/ubuntu/dists/{release}/Release",
        f"{k8s}/Release.key",
        f"{k8s}/Release",
        "https://nvidia.github.io/libnvidia-container/gpgkey",
        "https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list",
        "https://get.k3s.io",
    ]


def asset_urls(manifest: dict) -> list[str]:
    """Return the release assets the provisioners and CI download, as they name them."""
    tools, runtimes = manifest["tools"], manifest["runtimes"]
    k3s = urllib.parse.quote(manifest["k3s"]["version"], safe="")
    stargz = runtimes["stargz_snapshotter"]
    enroot = tools["enroot"]
    cst = tools["container_structure_test"]
    packer = manifest["build"]["packer"]["version"]
    gh = "https://github.com"
    urls = [
        f"{gh}/k3s-io/k3s/releases/download/{k3s}/k3s",
        f"{gh}/k3s-io/k3s/releases/download/{k3s}/sha256sum-amd64.txt",
        f"{gh}/containerd/stargz-snapshotter/releases/download/v{stargz}/stargz-snapshotter-v{stargz}-linux-amd64.tar.gz",
        f"{gh}/containerd/stargz-snapshotter/releases/download/v{stargz}/stargz-snapshotter-v{stargz}-linux-amd64.tar.gz.sha256sum",
        f"{gh}/NVIDIA/enroot/releases/download/v{enroot}/enroot_{enroot}-1_amd64.deb",
        f"{gh}/NVIDIA/enroot/releases/download/v{enroot}/enroot+caps_{enroot}-1_amd64.deb",
        f"{gh}/GoogleContainerTools/container-structure-test/releases/download/v{cst}/container-structure-test-linux-amd64",
        f"{gh}/GoogleContainerTools/container-structure-test/releases/download/v{cst}/checksums.txt",
        f"{gh}/iximiuz/cdebug/releases/download/v{tools['cdebug']}/cdebug_linux_amd64.tar.gz",
        f"https://releases.hashicorp.com/packer/{packer}/packer_{packer}_linux_amd64.zip",
        f"{gh}/containerd/containerd/releases/tag/v{runtimes['containerd']}",
        f"{gh}/containers/crun/releases/tag/{runtimes['crun']}",
        manifest["distro"]["iso_checksum"].removeprefix("file:"),
    ]
    for plugin in manifest["build"]["packer_plugins"].values():
        name = plugin["source"].rsplit("/", 1)[1]
        urls.append(f"{gh}/hashicorp/packer-plugin-{name}/releases/tag/v{plugin['version']}")
    return urls


def source_urls(manifest: dict) -> list[str]:
    urls = rocm_urls(manifest) + repository_urls(manifest) + asset_urls(manifest)
    if len(urls) > MAX_URLS:
        raise ValueError(f"{len(urls)} URLs exceed the bound of {MAX_URLS}")
    return urls


def image_refs(manifest: dict) -> list[str]:
    """Return every preheated image and every device plugin image the flavors pull."""
    refs = list(manifest["kubernetes"]["images"].values())
    refs += [vendor["k8s_plugin"] for vendor in manifest["drivers"].values() if "k8s_plugin" in vendor]
    if len(refs) > MAX_IMAGES:
        raise ValueError(f"{len(refs)} images exceed the bound of {MAX_IMAGES}")
    return refs


def https_opener() -> urllib.request.OpenerDirector:
    """Return an opener that speaks HTTPS only: no file://, ftp:// or plain http:// handler."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    opener.addheaders = [("User-Agent", USER_AGENT)]
    return opener


def require_https(url: str) -> None:
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError(f"upstream source is not an https URL: {url}")


def http_status(url: str, headers: dict[str, str] | None = None) -> int:
    require_https(url)
    request = urllib.request.Request(url, method="HEAD", headers=headers or {})
    try:
        with https_opener().open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def http_read(url: str) -> bytes:
    """Return the body of url; an answer other than 200 raises urllib.error.HTTPError."""
    require_https(url)
    with https_opener().open(urllib.request.Request(url), timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_INDEX_BYTES + 1)
    if len(body) > MAX_INDEX_BYTES:
        raise ValueError(f"{url} exceeds the bound of {MAX_INDEX_BYTES} bytes")
    return body


def registry_parts(ref: str) -> tuple[str, str, str]:
    """Split an image reference into registry host, repository and tag."""
    name, tag = ref.rsplit(":", 1)
    host, repo = name.split("/", 1)
    if host == "docker.io":
        host = "registry-1.docker.io"
        repo = repo if "/" in repo else f"library/{repo}"
    return host, repo, tag


def registry_token(challenge: str, opener: urllib.request.OpenerDirector) -> str:
    """Fetch an anonymous pull token for a Bearer challenge from a registry."""
    fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
    realm = fields.pop("realm")
    require_https(realm)
    url = f"{realm}?{urllib.parse.urlencode(fields)}"
    with opener.open(urllib.request.Request(url), timeout=TIMEOUT_SECONDS) as response:
        body = json.loads(response.read(1024 * 1024))
    return body.get("token") or body["access_token"]


def image_status(ref: str) -> int:
    """Return the registry status of an image manifest, with an anonymous token when asked."""
    host, repo, tag = registry_parts(ref)
    url = f"https://{host}/v2/{repo}/manifests/{tag}"
    require_https(url)
    opener = https_opener()
    headers = {"Accept": MANIFEST_ACCEPT}
    try:
        with opener.open(urllib.request.Request(url, method="HEAD", headers=headers), timeout=TIMEOUT_SECONDS) as r:
            return r.status
    except urllib.error.HTTPError as error:
        challenge = error.headers.get("WWW-Authenticate", "")
        if error.code != 401 or not challenge.startswith("Bearer "):
            return error.code
    headers["Authorization"] = f"Bearer {registry_token(challenge, opener)}"
    return http_status(url, headers)


def missing(urls: list[str], fetch: Fetch) -> list[str]:
    """Return each URL with its status, for every URL that did not answer 200."""
    failures = []
    for url in urls:
        status = fetch(url)
        if status != 200:
            failures.append(f"{status} {url}")
    return failures


def missing_images(refs: list[str], image: Image) -> list[str]:
    return [f"{status} image {ref}" for ref in refs if (status := image(ref)) != 200]


def decode(url: str, body: bytes) -> str:
    if url.endswith(".xz"):
        body = lzma.decompress(body)
    elif url.endswith(".gz"):
        body = gzip.decompress(body)
    return body.decode("utf-8", errors="replace")


def parse_packages(text: str, index: Index) -> None:
    """Add the stanzas of a Packages file to index; an earlier record of a name wins."""
    for stanza in text.split("\n\n"):
        fields = dict(re.findall(r"^(Package|Version|Section|Depends|Provides): ?(.*)$", stanza, re.M))
        name = fields.get("Package")
        if not name:
            continue
        index.records.setdefault(name, fields)
        index.versions.setdefault(name, []).append(fields.get("Version", ""))
        for entry in fields.get("Provides", "").split(","):
            virtual = entry.split("(")[0].strip()
            if virtual:
                index.provides.setdefault(virtual, set()).add(name)


def load_index(urls: list[str], read: Read) -> tuple[Index, list[str]]:
    """Read and merge Packages files in priority order; report every file that is missing."""
    index, failures = Index(), []
    for url in urls:
        try:
            parse_packages(decode(url, read(url)), index)
        except urllib.error.HTTPError as error:
            failures.append(f"{error.code} index {url}")
    return index, failures


def archive_urls(release: str, arch: str) -> list[str]:
    """Return the archive Packages files apt reads, -updates first as its higher versions win."""
    return [
        f"{ARCHIVE}/dists/{pocket}/{component}/binary-{arch}/Packages.xz"
        for pocket in (f"{release}-updates", release)
        for component in ARCHIVE_COMPONENTS
    ]


def vendor_urls(manifest: dict) -> list[str]:
    """Return the Packages files of the vendor repositories the provisioners add."""
    release = manifest["distro"]["release"]
    amd = manifest["drivers"]["amd"]
    rocm = [
        f"{amd['rocm_repo']}/apt/{amd[key]}/dists/{amd['rocm_apt_suite']}/main/binary-amd64/Packages"
        for key in ("rocm_bleeding_version", "rocm_legacy_version")
    ]
    return [
        f"https://download.docker.com/linux/ubuntu/dists/{release}/stable/binary-amd64/Packages",
        f"https://pkgs.k8s.io/core:/stable:/v{manifest['kubernetes']['major_minor']}/deb/Packages",
        NVIDIA_TOOLKIT_INDEX,
        *rocm,
    ]


def transitional_target(record: dict[str, str], name: str) -> str | None:
    """Return the package a transitional package pulls in, or None for a real package.

    A transitional package is in an oldlibs section, or depends on nothing but the same package
    of another branch: nvidia-utils-610 that pulls in nvidia-utils-615.
    """
    depends = [dep.split("(")[0].strip() for dep in record.get("Depends", "").split(",") if dep.strip()]
    family = re.sub(r"\d{3}", "N", name)
    if len(depends) == 1 and depends[0] != name and re.sub(r"\d{3}", "N", depends[0]) == family:
        return depends[0]
    if record.get("Section", "").endswith("/oldlibs"):
        return depends[0] if depends else "another package"
    return None


def nvidia_failures(manifest: dict, archive: Index) -> list[str]:
    """Each tier's packages must exist, carry the pinned branch and not be transitional."""
    nvidia, failures = manifest["drivers"]["nvidia"], []
    for tier, (driver_key, _, templates) in NVIDIA_TIERS.items():
        branch = nvidia[driver_key]
        if not re.fullmatch(r"\d{3}", branch):
            failures.append(f"nvidia {tier}: driver pin {branch!r} is not a three-digit branch")
            continue
        for template in templates:
            name = template.format(b=branch)
            record = archive.records.get(name)
            if record is None:
                failures.append(f"nvidia {tier}: {name} is not in the Ubuntu archive")
            elif target := transitional_target(record, name):
                failures.append(f"nvidia {tier}: {name} is a transitional package that installs {target}")
            elif not record.get("Version", "").startswith(f"{branch}."):
                failures.append(f"nvidia {tier}: {name} carries version {record.get('Version')}, not {branch}")
    return failures


def cuda_failures(manifest: dict, cuda: Index) -> list[str]:
    """The pinned CUDA release's cuda-compat package must require the tier's driver branch."""
    nvidia, failures = manifest["drivers"]["nvidia"], []
    for tier, (driver_key, cuda_key, _) in NVIDIA_TIERS.items():
        if cuda_key is None:
            continue
        release, branch = nvidia[cuda_key], nvidia[driver_key]
        name = "cuda-compat-" + release.replace(".", "-")
        versions = cuda.versions.get(name)
        if not versions:
            failures.append(f"nvidia {tier}: CUDA {release} is not published ({name} is not in {CUDA_INDEX})")
        elif not any(version.startswith(f"{branch}.") for version in versions):
            needs = sorted({version.split(".")[0] for version in versions})
            failures.append(
                f"nvidia {tier}: CUDA {release} pairs with driver {'/'.join(needs)}, the tier pins {branch}"
            )
    return failures


def version_failures(manifest: dict, vendor: Index) -> list[str]:
    """The pinned docker-ce, kubelet and Container Toolkit releases must be published."""
    pins = (
        ("docker-ce", manifest["runtimes"]["docker_ce"]),
        ("kubelet", manifest["kubernetes"]["version"]),
        ("nvidia-container-toolkit", manifest["drivers"]["nvidia"]["container_toolkit"]),
    )
    failures = []
    for name, pin in pins:
        published = [version.split(":", 1)[-1] for version in vendor.versions.get(name, [])]
        if not any(re.match(rf"{re.escape(pin)}[.~-]", version) for version in published):
            failures.append(f"apt pin {name} {pin} is not published (newest: {max(published, default='none')})")
    return failures


def literal_packages(script: str) -> tuple[list[str], set[str], bool]:
    """Return the literal packages a script installs, those it guards, and whether it adds i386."""
    lines = [line for line in script.replace("\\\n", " ").splitlines() if not line.lstrip().startswith("#")]
    # Drop words that expand a variable first: their braces would end the command match early.
    text = re.sub(r"[^\s;|&()]*\$(?:\{[^}\n]*\}|\w+)[^\s;|&()]*", " ", "\n".join(lines))
    names = []
    for command in re.findall(r"apt-get install([^\n|&;{}()]*)", text):
        names += [token for token in command.split() if re.fullmatch(r"[a-z0-9][a-z0-9+.-]+(:i386)?", token)]
    guarded = set(re.findall(r"apt-cache show ([a-z0-9][a-z0-9+.-]+)", text))
    return names, guarded, "--add-architecture i386" in text


def candidate_problem(name: str, indexes: list[Index]) -> str | None:
    """Return why apt finds no candidate for name: no package, or a virtual one with many providers."""
    if any(name in index.records for index in indexes):
        return None
    providers = set().union(*(index.provides.get(name, set()) for index in indexes))
    if len(providers) == 1:
        return None
    if providers:
        return f"is a virtual package with {len(providers)} providers ({', '.join(sorted(providers))})"
    return "is not in any configured repository"


def package_failures(scripts: dict[str, str], amd64: list[Index], i386: list[Index]) -> list[str]:
    """Every literal package a provisioner installs must have an installation candidate."""
    failures = []
    for script_name, text in scripts.items():
        names, guarded, adds_i386 = literal_packages(text)
        for name in names:
            base, _, arch = name.partition(":")
            if base in guarded:
                continue
            pool = i386 if arch == "i386" else amd64 + (i386 if adds_i386 else [])
            if problem := candidate_problem(base, pool):
                failures.append(f"{script_name}: apt package {name} {problem}")
    return failures


def provisioner_scripts(directory: pathlib.Path = PROVISIONERS) -> dict[str, str]:
    paths = sorted(directory.glob("*.sh"))
    if len(paths) > MAX_SCRIPTS:
        raise ValueError(f"{len(paths)} provisioners exceed the bound of {MAX_SCRIPTS}")
    return {path.name: path.read_text(encoding="utf-8") for path in paths}


def package_checks(manifest: dict, read: Read, scripts: dict[str, str]) -> list[str]:
    """Run the NVIDIA, CUDA, apt version and provisioner package checks against live indexes."""
    release = manifest["distro"]["release"]
    archive, failures = load_index(archive_urls(release, "amd64"), read)
    i386, more = load_index(archive_urls(release, "i386"), read)
    vendor, vendor_missing = load_index(vendor_urls(manifest), read)
    cuda, cuda_missing = load_index([CUDA_INDEX], read)
    failures += more + vendor_missing + cuda_missing
    failures += nvidia_failures(manifest, archive)
    failures += cuda_failures(manifest, cuda)
    failures += version_failures(manifest, vendor)
    failures += package_failures(scripts, [archive, vendor], [i386])
    return failures


LIVE = Probes(fetch=http_status, read=http_read, image=image_status)


def main(argv: list[str] | None = None, probes: Probes = LIVE, scripts: dict[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["urls", "check"])
    parser.add_argument("--manifest", type=pathlib.Path, default=ROOT / "versions.json")
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    urls, refs = source_urls(manifest), image_refs(manifest)
    if args.command == "urls":
        print("\n".join(urls + refs))
        return 0
    failures = missing(urls, probes.fetch) + missing_images(refs, probes.image)
    failures += package_checks(manifest, probes.read, provisioner_scripts() if scripts is None else scripts)
    for failure in failures:
        print(f"::error::upstream source missing: {failure}", file=sys.stderr)
    print(f"{len(urls)} URLs, {len(refs)} images, NVIDIA tiers, CUDA labels and provisioner packages checked")
    print(f"{len(failures)} upstream sources missing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
