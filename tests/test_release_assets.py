# Copyright 2026 Lusoris
"""Verification of the release SBOM and signing path.

`tools/ci/release_assets.py` attaches a built qcow2 image read-only so Syft can catalogue its
root file system, refuses an SBOM with too few Debian packages and merges the per-flavor
checksum files into the SHA256SUMS a release signs, and refuses an asset the forge would
refuse for its size. The tests replace the system tools (sudo, qemu-nbd, lsblk, blkid, mount)
with a recorder, cover the failure and boundary cases, and check that release-matrix.yml
generates the SBOMs, ships each image as qcow2 and as raw disk under the signed checksums,
signs SHA256SUMS and verifies the signature before it uploads anything.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "release_assets.py"
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE = WORKFLOWS / "release-matrix.yml"
BAREMETAL = ROOT / "docs" / "platforms" / "baremetal.md"
DEVICE = "/dev/nbd7"

_spec = importlib.util.spec_from_file_location("release_assets", SCRIPT)
assets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(assets)


class Tools:
    """Stand-in for the system tools: records each command and answers as configured."""

    def __init__(self, mount_dir: Path) -> None:
        self.mount_dir = mount_dir
        self.calls: list[list[str]] = []
        self.labels = {f"{DEVICE}p1": assets.ROOT_LABEL, f"{DEVICE}p13": "BOOT", f"{DEVICE}p15": "UEFI"}
        self.fail: set[str] = set()
        self.dpkg_status = True

    def run(self, command: list[str]) -> str:
        self.calls.append(command)
        verb = command[1] if command[0] == "sudo" else command[0]
        if verb in self.fail or (verb == "mount" and "mount-boot" in self.fail and command[-1].endswith("/boot")):
            raise assets.AssetError(f"{verb} failed")
        if verb == "lsblk":
            return "\n".join([DEVICE, *self.labels]) + "\n"
        if verb == "blkid":
            return self.labels.get(command[-1], "") + "\n"
        if verb == "mount" and self.dpkg_status:
            (self.mount_dir / "var/lib/dpkg").mkdir(parents=True, exist_ok=True)
            (self.mount_dir / "var/lib/dpkg/status").write_text("Package: base-files\n", encoding="utf-8")
        return ""

    def verbs(self) -> list[str]:
        return [c[1] if c[0] == "sudo" else c[0] for c in self.calls if c[0] != "lsblk" and "blkid" not in c]


@pytest.fixture
def tools(tmp_path, monkeypatch):
    stub = Tools(tmp_path / "root")
    monkeypatch.setattr(assets, "run", stub.run)
    monkeypatch.setattr(assets.time, "sleep", lambda _s: None)
    return stub


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "imago-base-generic.qcow2"
    path.write_bytes(b"QFI\xfb")
    return path


def attach(image: Path, tools: Tools) -> int:
    return assets.main(["attach", "--image", str(image), "--at", str(tools.mount_dir), "--device", DEVICE])


def test_attach_mounts_the_labelled_partition_read_only(image, tools):
    assert attach(image, tools) == 0
    assert tools.verbs() == ["modprobe", "qemu-nbd", "mount", "mount"]
    connect = tools.calls[1]
    root, boot = [c for c in tools.calls if c[:2] == ["sudo", "mount"]]
    assert "--read-only" in connect and f"--connect={DEVICE}" in connect
    assert root[2:] == ["-o", "ro,noload", f"{DEVICE}p1", str(tools.mount_dir)]
    assert boot[2:] == ["-o", "ro,noload", f"{DEVICE}p13", str(tools.mount_dir / "boot")]


def test_attach_without_a_boot_partition_mounts_the_root_only(image, tools, capsys):
    del tools.labels[f"{DEVICE}p13"]
    assert attach(image, tools) == 0
    assert tools.verbs() == ["modprobe", "qemu-nbd", "mount"]
    assert "no BOOT partition" in capsys.readouterr().out


@pytest.mark.parametrize(
    "case",
    [
        (lambda t: t.labels.update({f"{DEVICE}p2": "BOOT"}), "2 partitions of /dev/nbd7 carry the label BOOT"),
        (lambda t: t.fail.add("mount-boot"), "mount failed"),
    ],
    ids=["two-boot-labels", "boot-mount-fails"],
)
def test_attach_fails_on_the_boot_partition_and_releases_the_device(image, tools, capsys, case):
    setup, message = case
    setup(tools)
    assert attach(image, tools) == 1
    assert message in capsys.readouterr().err
    assert tools.verbs()[-2:] == ["umount", "qemu-nbd"]
    assert tools.calls[-1][1:] == ["qemu-nbd", "--disconnect", DEVICE]


def test_detach_unmounts_then_disconnects(tools):
    assert assets.main(["detach", "--at", str(tools.mount_dir), "--device", DEVICE]) == 0
    assert tools.verbs() == ["umount", "qemu-nbd"]
    assert tools.calls[-1][2:] == ["--disconnect", DEVICE]


def test_detach_unmounts_boot_before_the_root(tools, monkeypatch):
    boot = tools.mount_dir / "boot"
    monkeypatch.setattr(assets.os.path, "ismount", lambda path: Path(path) == boot)
    assert assets.main(["detach", "--at", str(tools.mount_dir), "--device", DEVICE]) == 0
    assert tools.calls[0][1:] == ["umount", str(boot)]
    assert tools.calls[1][1:] == ["umount", str(tools.mount_dir)]
    assert tools.verbs() == ["umount", "umount", "qemu-nbd"]


def test_detach_tries_both_and_fails_when_umount_fails(tools, capsys):
    tools.fail.add("umount")
    assert assets.main(["detach", "--at", str(tools.mount_dir), "--device", DEVICE]) == 1
    assert tools.verbs() == ["umount", "qemu-nbd"]
    assert "umount failed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "case",
    [
        (lambda t: t.fail.add("qemu-nbd"), "qemu-nbd failed", ["modprobe", "qemu-nbd"]),
        (lambda t: t.labels.update({f"{DEVICE}p1": "data"}), "no partition", ["modprobe", "qemu-nbd", "qemu-nbd"]),
        (
            lambda t: t.labels.update({f"{DEVICE}p2": assets.ROOT_LABEL}),
            "2 partitions",
            ["modprobe", "qemu-nbd", "qemu-nbd"],
        ),
        (lambda t: t.fail.add("mount"), "mount failed", ["modprobe", "qemu-nbd", "mount", "qemu-nbd"]),
        (
            lambda t: setattr(t, "dpkg_status", False),
            "dpkg/status",
            ["modprobe", "qemu-nbd", "mount", "umount", "qemu-nbd"],
        ),
    ],
    ids=["connect-fails", "no-root-label", "two-root-labels", "mount-fails", "no-dpkg-status"],
)
def test_attach_fails_and_releases_the_device(image, tools, capsys, case):
    setup, message, verbs = case
    setup(tools)
    assert attach(image, tools) == 1
    assert message in capsys.readouterr().err
    assert tools.verbs() == verbs
    if "qemu-nbd" in verbs[2:]:
        assert tools.calls[-1][1:] == ["qemu-nbd", "--disconnect", DEVICE]


def test_attach_waits_a_bounded_time_for_the_partition(image, tools):
    tools.labels = {}
    assert attach(image, tools) == 1
    assert sum(c[0] == "lsblk" for c in tools.calls) == assets.PARTITION_POLLS


@pytest.mark.parametrize("name", ["missing.qcow2", "imago-base-generic.raw"])
def test_attach_refuses_a_missing_or_foreign_image(tmp_path, tools, name):
    path = tmp_path / name
    if name.endswith(".raw"):
        path.write_bytes(b"\0")
    assert attach(path, tools) == 1
    assert tools.calls == []


def sboms(tmp_path: Path, debs: int, others: int = 5) -> tuple[Path, Path]:
    deb = [f"pkg:deb/ubuntu/pkg{i}@1.0?arch=amd64" for i in range(debs)]
    other = [f"pkg:pypi/mod{i}@1.0" for i in range(others)]
    cdx = tmp_path / "sbom-base-generic.cdx.json"
    spdx = tmp_path / "sbom-base-generic.spdx.json"
    cdx.write_text(json.dumps({"components": [{"purl": p} for p in deb + other]}), encoding="utf-8")
    packages = [{"externalRefs": [{"referenceType": "purl", "referenceLocator": p}]} for p in deb + other]
    spdx.write_text(json.dumps({"packages": packages}), encoding="utf-8")
    return cdx, spdx


def check(cdx: Path, spdx: Path) -> int:
    return assets.main(["check", "--cdx", str(cdx), "--spdx", str(spdx)])


def test_check_accepts_the_floor(tmp_path):
    assert check(*sboms(tmp_path, assets.MIN_DEB_PACKAGES)) == 0


def test_check_refuses_one_below_the_floor(tmp_path, capsys):
    assert check(*sboms(tmp_path, assets.MIN_DEB_PACKAGES - 1, others=500)) == 1
    assert "fewer than" in capsys.readouterr().err


def test_check_refuses_an_empty_catalogue(tmp_path):
    """The SBOM Syft writes for a qcow2 file it cannot read: valid, and empty."""
    assert check(*sboms(tmp_path, 0, others=0)) == 1


@pytest.mark.parametrize("broken", ["cdx", "spdx"])
def test_check_refuses_a_document_without_its_list(tmp_path, broken):
    cdx, spdx = sboms(tmp_path, assets.MIN_DEB_PACKAGES)
    (cdx if broken == "cdx" else spdx).write_text('{"bomFormat": "CycloneDX"}', encoding="utf-8")
    assert check(cdx, spdx) == 1


def test_check_refuses_an_spdx_short_of_debs(tmp_path):
    cdx, spdx = sboms(tmp_path, assets.MIN_DEB_PACKAGES)
    spdx.write_text(json.dumps({"packages": [{"name": "x"}] * 500}), encoding="utf-8")
    assert check(cdx, spdx) == 1


def test_check_refuses_invalid_json(tmp_path):
    cdx, spdx = sboms(tmp_path, assets.MIN_DEB_PACKAGES)
    cdx.write_text("{", encoding="utf-8")
    assert check(cdx, spdx) == 1


def checksum_file(path: Path, names: list[str]) -> Path:
    path.write_text("".join(f"{hashlib.sha256(n.encode()).hexdigest()}  {n}\n" for n in names), encoding="utf-8")
    return path


def test_merge_joins_and_sorts_every_flavor(tmp_path):
    a = checksum_file(tmp_path / "checksums-k8s.sha256", ["imago-k8s.qcow2.zst", "sbom-k8s.cdx.json"])
    b = checksum_file(tmp_path / "checksums-base.sha256", ["imago-base.qcow2.zst", "sbom-base.cdx.json"])
    out = tmp_path / "SHA256SUMS"
    assert assets.main(["merge", "--out", str(out), str(a), str(b)]) == 0
    names = [line.split("  ")[1] for line in out.read_text().splitlines()]
    assert names == sorted(names) and len(names) == 4
    assert all(re.fullmatch(r"[0-9a-f]{64}  \S+", line) for line in out.read_text().splitlines())


def test_merge_accepts_binary_mode_lines(tmp_path):
    part = tmp_path / "checksums-x.sha256"
    part.write_text(f"{'a' * 64} *imago-x.qcow2.zst\n", encoding="utf-8")
    out = tmp_path / "SHA256SUMS"
    assert assets.main(["merge", "--out", str(out), str(part)]) == 0
    assert out.read_text() == f"{'a' * 64}  imago-x.qcow2.zst\n"


@pytest.mark.parametrize(
    "line",
    [
        f"{'a' * 64}  ./imago-x.qcow2.zst",
        f"{'a' * 64}  sub/imago-x.qcow2.zst",
        f"{'a' * 63}  imago-x.qcow2.zst",
        f"{'A' * 64}  imago-x.qcow2.zst",
        f"{'a' * 64}  ",
        "",
    ],
    ids=["dot-slash", "path", "short-digest", "upper-hex", "no-name", "blank"],
)
def test_merge_refuses_a_malformed_line(tmp_path, line):
    part = tmp_path / "checksums-x.sha256"
    part.write_text(line + "\n", encoding="utf-8")
    out = tmp_path / "SHA256SUMS"
    assert assets.main(["merge", "--out", str(out), str(part)]) == 1
    assert not out.exists()


def test_merge_refuses_a_name_listed_twice(tmp_path):
    a = checksum_file(tmp_path / "checksums-a.sha256", ["sbom.cdx.json"])
    b = checksum_file(tmp_path / "checksums-b.sha256", ["sbom.cdx.json"])
    assert assets.main(["merge", "--out", str(tmp_path / "SHA256SUMS"), str(a), str(b)]) == 1


@pytest.mark.parametrize("parts", [[], ["empty"]], ids=["no-files", "empty-file"])
def test_merge_refuses_an_empty_set(tmp_path, parts):
    paths = []
    for name in parts:
        (tmp_path / name).write_text("", encoding="utf-8")
        paths.append(str(tmp_path / name))
    assert assets.main(["merge", "--out", str(tmp_path / "SHA256SUMS"), *paths]) == 1


def sparse(path: Path, size: int) -> Path:
    with path.open("wb") as f:
        f.truncate(size)
    return path


def test_sizes_accepts_one_byte_under_the_limit_and_writes_the_summary(tmp_path, capsys):
    raw = sparse(tmp_path / "lusoris-cloud-base-generic.raw.zst", assets.ASSET_LIMIT_BYTES - 1)
    qcow2 = sparse(tmp_path / "lusoris-cloud-base-generic.qcow2.zst", 1024)
    summary = tmp_path / "summary.md"
    summary.write_text("earlier step\n", encoding="utf-8")
    assert assets.main(["sizes", "--summary", str(summary), str(qcow2), str(raw)]) == 0
    lines = summary.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "earlier step"
    assert f"| `{raw.name}` | {assets.ASSET_LIMIT_BYTES - 1} | 2.00 GiB |" in lines
    assert f"| `{qcow2.name}` | 1024 | 0.00 GiB |" in lines
    assert raw.name in capsys.readouterr().out


def test_sizes_refuses_an_asset_of_exactly_the_limit_and_still_lists_it(tmp_path, capsys):
    raw = sparse(tmp_path / "big.raw.zst", assets.ASSET_LIMIT_BYTES)
    small = sparse(tmp_path / "small.qcow2.zst", 1)
    summary = tmp_path / "summary.md"
    assert assets.main(["sizes", "--summary", str(summary), str(small), str(raw)]) == 1
    assert "big.raw.zst" in summary.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert "big.raw.zst reach the forge limit" in err and "small" not in err


def test_sizes_limit_is_the_forge_limit():
    assert assets.ASSET_LIMIT_BYTES == 2_147_483_648


def test_sizes_refuses_planted_2gib_squashfs_and_accepts_limit_minus_one(tmp_path, capsys):
    squashfs_boundary = sparse(tmp_path / "base-generic-root.squashfs", assets.ASSET_LIMIT_BYTES - 1)
    assert assets.main(["sizes", str(squashfs_boundary)]) == 0
    squashfs_over = sparse(tmp_path / "base-generic-root.squashfs", assets.ASSET_LIMIT_BYTES)
    assert assets.main(["sizes", str(squashfs_over)]) == 1
    err = capsys.readouterr().err
    assert "base-generic-root.squashfs reach the forge limit" in err


def test_sizes_refuses_no_asset_a_missing_asset_and_too_many(tmp_path):
    assert assets.main(["sizes"]) == 1
    assert assets.main(["sizes", str(tmp_path / "absent.raw.zst")]) == 1
    one = sparse(tmp_path / "a.raw.zst", 1)
    assert assets.main(["sizes", *[str(one)] * (assets.MAX_ASSETS + 1)]) == 1
    assert assets.main(["sizes", *[str(one)] * assets.MAX_ASSETS]) == 0


# --- workflow wiring -------------------------------------------------------------------


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def steps(job: dict) -> list[dict]:
    return job["steps"]


def index(job: dict, predicate) -> int:
    found = [i for i, step in enumerate(steps(job)) if predicate(step)]
    assert len(found) == 1, found
    return found[0]


def runs(step: dict, pattern: str) -> bool:
    return re.search(pattern, step.get("run", "")) is not None


@pytest.fixture
def small_parts(monkeypatch):
    """Scale the limit and part size down so a split runs on a few kilobytes."""
    monkeypatch.setattr(assets, "ASSET_LIMIT_BYTES", 4096)
    monkeypatch.setattr(assets, "PART_BYTES", 1500)
    monkeypatch.setattr(assets, "COPY_CHUNK", 512)


def random_file(path: Path, size: int) -> Path:
    path.write_bytes(bytes((i * 131 + 7) % 251 for i in range(size)))
    return path


def split_one(tmp_path: Path, size: int) -> tuple[Path, Path, Path]:
    image = random_file(tmp_path / "imago-k8s.qcow2.zst", size)
    sums, listing = tmp_path / "checksums-k8s.sha256", tmp_path / "upload-k8s.txt"
    assert assets.main(["split", "--sums", str(sums), "--list", str(listing), str(image)]) == 0
    return image, sums, listing


def test_split_keeps_an_asset_one_byte_under_the_limit_whole(tmp_path, small_parts):
    image, sums, listing = split_one(tmp_path, 4095)
    assert listing.read_text(encoding="utf-8") == "imago-k8s.qcow2.zst\n"
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    assert sums.read_text(encoding="utf-8") == f"{digest}  imago-k8s.qcow2.zst\n"
    assert not list(tmp_path.glob("*.part*"))


def test_split_cuts_an_asset_of_the_limit_and_join_rebuilds_it(tmp_path, small_parts, capsys):
    image, sums, listing = split_one(tmp_path, 4096)
    names = [f"imago-k8s.qcow2.zst.part{i:02d}" for i in range(3)]
    assert listing.read_text(encoding="utf-8").splitlines() == names
    assert [(tmp_path / n).stat().st_size for n in names] == [1500, 1500, 1096]
    lines = sums.read_text(encoding="utf-8").splitlines()
    assert [line.split("  ")[1] for line in lines] == ["imago-k8s.qcow2.zst", *names]
    assert assets.main(["sizes", *(str(tmp_path / n) for n in names)]) == 0
    original = image.read_bytes()
    image.unlink()
    parts = [str(tmp_path / n) for n in reversed(names)]
    assert assets.main(["join", "--sums", str(sums), "--out", str(image), *parts]) == 0
    assert image.read_bytes() == original
    assert "joined 3 parts" in capsys.readouterr().out


def test_split_lists_whole_assets_and_parts_in_one_merged_file(tmp_path, small_parts):
    sbom = random_file(tmp_path / "sbom-k8s.cdx.json", 10)
    image = random_file(tmp_path / "imago-k8s.qcow2.zst", 5000)
    sums, listing = tmp_path / "checksums-k8s.sha256", tmp_path / "upload-k8s.txt"
    assert assets.main(["split", "--sums", str(sums), "--list", str(listing), str(image), str(sbom)]) == 0
    assert assets.main(["merge", "--out", str(tmp_path / "SHA256SUMS"), str(sums)]) == 0
    assert listing.read_text(encoding="utf-8").splitlines()[-1] == "sbom-k8s.cdx.json"


def test_join_refuses_a_planted_corrupt_part_and_writes_nothing(tmp_path, small_parts, capsys):
    image, sums, _ = split_one(tmp_path, 4096)
    image.unlink()
    bad = tmp_path / "imago-k8s.qcow2.zst.part01"
    data = bytearray(bad.read_bytes())
    data[7] ^= 0xFF
    bad.write_bytes(bytes(data))
    parts = [str(tmp_path / f"imago-k8s.qcow2.zst.part{i:02d}") for i in range(3)]
    assert assets.main(["join", "--sums", str(sums), "--out", str(image), *parts]) == 1
    assert "part01 does not match" in capsys.readouterr().err
    assert not image.exists()


def test_join_refuses_a_missing_or_foreign_part(tmp_path, small_parts, capsys):
    image, sums, _ = split_one(tmp_path, 4096)
    image.unlink()
    part = [str(tmp_path / f"imago-k8s.qcow2.zst.part{i:02d}") for i in range(3)]
    assert assets.main(["join", "--sums", str(sums), "--out", str(image), part[0], part[2]]) == 1
    foreign = random_file(tmp_path / "other.part02", 10)
    assert assets.main(["join", "--sums", str(sums), "--out", str(image), part[0], part[1], str(foreign)]) == 1
    assert assets.main(["join", "--sums", str(sums), "--out", str(image)]) == 1
    assert capsys.readouterr().err.count("each once, none left out") == 3
    assert not image.exists()


def test_join_removes_a_joined_file_whose_whole_digest_differs(tmp_path, small_parts, capsys):
    image, sums, _ = split_one(tmp_path, 4096)
    image.unlink()
    lines = sums.read_text(encoding="utf-8").splitlines()
    lines[0] = "0" * 64 + lines[0][64:]
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    parts = [str(tmp_path / f"imago-k8s.qcow2.zst.part{i:02d}") for i in range(3)]
    assert assets.main(["join", "--sums", str(sums), "--out", str(image), *parts]) == 1
    assert "does not match" in capsys.readouterr().err
    assert not image.exists()


def test_split_refuses_an_asset_that_needs_more_parts_than_allowed(tmp_path, small_parts, monkeypatch, capsys):
    monkeypatch.setattr(assets, "MAX_PARTS", 2)
    image = random_file(tmp_path / "imago-k8s.qcow2.zst", 4096)
    args = ["split", "--sums", str(tmp_path / "s"), "--list", str(tmp_path / "l"), str(image)]
    assert assets.main(args) == 1
    assert "3 parts, more than 2" in capsys.readouterr().err
    assert assets.main(["split", "--sums", str(tmp_path / "s"), "--list", str(tmp_path / "l")]) == 1


def test_part_size_stays_under_the_forge_limit():
    assert assets.ASSET_LIMIT_BYTES - assets.PART_BYTES == 256 * 1024**2
    assert assets.MAX_PARTS * assets.PART_BYTES > 16 * 1024**3


def test_build_job_generates_and_checks_sboms_before_compressing():
    job = load(RELEASE)["jobs"]["build-matrix"]
    sbom = index(job, lambda s: runs(s, r"(?m)^\s*syft scan .*-o \"?cyclonedx-json=.*-o \"?spdx-json="))
    compress = index(job, lambda s: runs(s, r"zstd "))
    assert sbom < compress
    lines = steps(job)[sbom]["run"].splitlines()
    wanted = [
        r"python3 -I tools/ci/release_assets\.py attach ",
        r"syft scan .* \|\| status=\$\?$",
        r"python3 -I tools/ci/netboot_assets\.py extract .* \|\| status=\$\?$",
        r"python3 -I tools/ci/release_assets\.py detach ",
        r'test "\$\{status\}" -eq 0$',
        r"python3 -I tools/ci/release_assets\.py check ",
    ]
    order = [[i for i, line in enumerate(lines) if re.match(w, line)] for w in wanted]
    assert all(len(found) == 1 for found in order), order
    assert [found[0] for found in order] == sorted(found[0] for found in order)
    assert runs(
        steps(job)[compress],
        r'(?m)release_assets\.py" split --sums "checksums-\$\{FLAVOR\}\.sha256" \\\n'
        + r'\s+--list "upload-\$\{FLAVOR\}\.txt" \./\*\.qcow2\.zst \./\*\.raw\.zst \./sbom-\*\.json "\$\{netboot\[@\]\}"$',
    )


def test_compress_step_converts_to_raw_splits_then_checks_the_upload_sizes():
    job = load(RELEASE)["jobs"]["build-matrix"]
    lines = steps(job)[index(job, lambda s: runs(s, r"zstd "))]["run"].splitlines()
    wanted = [
        r"qcow2=\(\./\*\.qcow2\)$",
        r'test "\$\{#qcow2\[@\]\}" -eq 1$',
        r'qemu-img convert -O raw "\$\{qcow2\[0\]\}" "\$\{qcow2\[0\]%\.qcow2\}\.raw"$',
        r"zstd -T0 -19 --rm \./\*\.qcow2 \./\*\.raw$",
        r"netboot=\(\./\*-netboot\.vmlinuz \./\*-netboot\.initrd \./\*-root\.squashfs \./\*\.ipxe\)$",
        r'python3 -I "\$\{GITHUB_WORKSPACE\}/tools/ci/release_assets\.py" split --sums ',
        r'mapfile -t upload < "upload-\$\{FLAVOR\}\.txt"$',
        r'python3 -I "\$\{GITHUB_WORKSPACE\}/tools/ci/release_assets\.py" sizes --summary "\$\{GITHUB_STEP_SUMMARY\}"'
        + r' "\$\{upload\[@\]\}"$',
    ]
    order = [[i for i, line in enumerate(lines) if re.match(w, line)] for w in wanted]
    assert all(len(found) == 1 for found in order), order
    assert [found[0] for found in order] == sorted(found[0] for found in order)


def upload_artifact(job: dict, name: str) -> dict:
    return steps(job)[
        index(job, lambda s: s.get("uses", "").startswith("actions/upload-artifact@") and s["with"]["name"] == name)
    ]


def test_manual_run_keeps_the_raw_image_for_a_day():
    job = load(RELEASE)["jobs"]["build-matrix"]
    keep = upload_artifact(job, "raw-${{ matrix.flavor }}")
    assert keep["if"] == "github.event_name == 'workflow_dispatch'"
    assert keep["with"]["path"] == "packer/output-images/${{ matrix.flavor }}/*.raw.zst"
    assert keep["with"]["retention-days"] == 1
    assert keep["with"]["if-no-files-found"] == "error"


def test_build_job_keeps_the_checksums_and_uploads_no_unsigned_sha256sums():
    job = load(RELEASE)["jobs"]["build-matrix"]
    keep = upload_artifact(job, "checksums-${{ matrix.flavor }}")
    assert keep["with"]["if-no-files-found"] == "error"
    paths = keep["with"]["path"].strip().splitlines()
    assert paths == [
        "packer/output-images/${{ matrix.flavor }}/checksums-${{ matrix.flavor }}.sha256",
        "packer/output-images/${{ matrix.flavor }}/sbom-*.json",
        "packer/output-images/${{ matrix.flavor }}/*-netboot.vmlinuz",
        "packer/output-images/${{ matrix.flavor }}/*-netboot.initrd",
        "packer/output-images/${{ matrix.flavor }}/*-root.squashfs",
        "packer/output-images/${{ matrix.flavor }}/*.ipxe",
    ]
    upload = steps(job)[index(job, lambda s: runs(s, r"gh release upload "))]
    assert upload["if"] == "github.event_name == 'release'"
    assert upload["env"]["TAG"] == "${{ github.event.release.tag_name }}"
    assert upload["env"]["FLAVOR"] == "${{ matrix.flavor }}"
    assert "SHA256SUMS" not in upload["run"]
    assert upload["run"].strip().splitlines() == [
        'cd "packer/output-images/${FLAVOR}"',
        'mapfile -t upload < "upload-${FLAVOR}.txt"',
        'gh release upload "${TAG}" --repo "${GITHUB_REPOSITORY}" --clobber "${upload[@]}"',
    ]


def test_netboot_smoke_step_runs_on_manual_dispatch_with_negative_check():
    job = load(RELEASE)["jobs"]["build-matrix"]
    step = steps(job)[index(job, lambda s: s.get("name") == "Netboot Smoke Test")]
    assert step["if"] == "github.event_name == 'workflow_dispatch'"
    assert step.get("continue-on-error") is None or step["continue-on-error"] is False
    run_lines = step["run"].strip().splitlines()
    positive = [line for line in run_lines if "tools/ci/netboot_smoke.py" in line and "--expect-mismatch" not in line]
    negative = [line for line in run_lines if "tools/ci/netboot_smoke.py" in line and "--expect-mismatch" in line]
    assert len(positive) == 1 and len(negative) == 1
    assert "continue-on-error" not in step["run"]


def test_sign_job_signs_verifies_then_uploads_on_release_only():
    job = load(RELEASE)["jobs"]["sign"]
    assert job["needs"] == "build-matrix"
    assert job["if"] == "github.event_name == 'release'"
    assert job["permissions"] == {"contents": "write", "id-token": "write"}
    merge = index(job, lambda s: runs(s, r"release_assets\.py merge --out SHA256SUMS "))
    sign = index(job, lambda s: runs(s, r"^cosign sign-blob --yes --bundle SHA256SUMS\.bundle SHA256SUMS$"))
    verify = index(job, lambda s: runs(s, r"cosign verify-blob --bundle SHA256SUMS\.bundle"))
    upload = index(job, lambda s: runs(s, r"gh release upload "))
    assert merge < sign < verify < upload
    verify_run = steps(job)[verify]["run"]
    assert '--certificate-identity "https://github.com/${GITHUB_WORKFLOW_REF}"' in verify_run
    assert "--certificate-oidc-issuer https://token.actions.githubusercontent.com" in verify_run
    upload_run = steps(job)[upload]["run"].split()
    assert upload_run[upload_run.index("--clobber") + 1 :] == ["SHA256SUMS", "SHA256SUMS.bundle"]


def test_every_action_is_pinned_to_a_commit():
    for name, job in load(RELEASE)["jobs"].items():
        for step in steps(job):
            if "uses" in step:
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), (name, step["uses"])


def test_no_workflow_stands_in_for_signing_with_echo():
    assert not (WORKFLOWS / "supply-chain.yml").exists()
    for path in WORKFLOWS.glob("*.yml"):
        for job in (load(path).get("jobs") or {}).values():
            for step in job.get("steps", []):
                if re.search(r"sign|sbom|attest", step.get("name", ""), re.I) and "run" in step:
                    assert not re.fullmatch(r"\s*echo .*", step["run"].strip(), re.S), (path.name, step["name"])


def test_readme_scorecard_badge_points_at_scorecard():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "supply-chain.yml" not in readme
    assert re.search(r"\[!\[Scorecard\]\([^)]*scorecard\.yml[^)]*\)\]\([^)]*actions/workflows/scorecard\.yml\)", readme)


# --- bare-metal guide ------------------------------------------------------------------

RELEASE_URL = "https://github.com/${OWNER}/imago/releases/download/${TAG}/"


def test_baremetal_guide_downloads_a_raw_image_the_release_ships():
    guide = BAREMETAL.read_text(encoding="utf-8")
    hcl = (ROOT / "packer" / "variables.pkr.hcl").read_text(encoding="utf-8")
    image_name = re.search(r'variable "image_name" \{[^}]*default\s*=\s*"([^"]+)"', hcl)
    expression = load(RELEASE)["jobs"]["build-matrix"]["strategy"]["matrix"]["flavor"]
    released = re.search(r"\|\|\s*'(\[[^']+\])'", expression)
    assert released, "the matrix expression lists no release flavors"
    flavors = json.loads(released[1])
    shipped = {f"{image_name[1]}-{flavor}.raw.zst" for flavor in flavors}
    loop = re.search(r"for asset in ([^;]+); do\n\s*curl -fsSLO \"" + re.escape(RELEASE_URL + "${asset}") + '"', guide)
    assert loop, "no download loop over release assets"
    fetched = loop[1].split()
    assert fetched[1:] == ["SHA256SUMS", "SHA256SUMS.bundle"]
    streamed = re.findall(re.escape(RELEASE_URL) + r"([\w.-]+\.raw\.zst)", guide)
    assert streamed and {fetched[0], *streamed} <= shipped, (fetched, streamed, shipped)
    assert (
        '--certificate-identity "https://github.com/${OWNER}/imago/.github/workflows/release-matrix.yml@refs/tags/${TAG}"'
        in guide
    )


def test_baremetal_guide_names_no_host_that_does_not_serve_the_images():
    guide = BAREMETAL.read_text(encoding="utf-8")
    hosts = set(re.findall(r"https?://([\w.-]+)", guide))
    assert hosts <= {"github.com", "token.actions.githubusercontent.com", "boot.example.com"}, hosts
