# Copyright 2026 Lusoris
"""Flash test of `lusoris-install-to-disk` against a loop device.

The helper is taken byte for byte from the heredoc in
`packer/provisioners/25-baremetal-tuning.sh` that installs it, so the test runs the program
the image ships. Each case attaches a sparse file as a loop device with passwordless sudo,
flashes a zstd-compressed disk image from a file or over HTTP and compares the device with
the image. The negative cases cover a target that is no block device, a missing argument, a
truncated stream, an HTTP 404, an image larger than the device and an image without a
partition table; the boundary cases cover an image of exactly the device size and an image
with an MBR only.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.harness.live import skip_or_fail

ROOT = Path(__file__).resolve().parent.parent
PROVISIONER = ROOT / "packer" / "provisioners" / "25-baremetal-tuning.sh"
MIB = 1024 * 1024
TIMEOUT = 120

HELPER_RE = re.compile(r"cat <<'EOF' \| sudo tee /usr/local/bin/lusoris-install-to-disk\n(.*?)\nEOF\n", re.DOTALL)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, check=False, **kwargs)


@pytest.fixture(scope="module")
def helper(tmp_path_factory: pytest.TempPathFactory) -> Path:
    match = HELPER_RE.search(PROVISIONER.read_text(encoding="utf-8"))
    assert match, f"no lusoris-install-to-disk heredoc in {PROVISIONER}"
    path = tmp_path_factory.mktemp("helper") / "lusoris-install-to-disk"
    path.write_text(match.group(1) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture(scope="module")
def host_tools() -> None:
    for tool in ("bash", "losetup", "sfdisk", "zstd", "zstdcat", "curl", "dd", "od"):
        if shutil.which(tool) is None:
            skip_or_fail(f"{tool} is required for the flash test and was not found", os.environ)
    if run(["sudo", "-n", "true"]).returncode != 0:
        skip_or_fail("the flash test attaches a loop device and needs passwordless sudo", os.environ)


class LoopDevice:
    def __init__(self, backing: Path, device: str) -> None:
        self.backing = backing
        self.device = device

    def read(self, size: int) -> bytes:
        out = subprocess.run(
            ["sudo", "-n", "dd", f"if={self.device}", "bs=1M", f"count={size // MIB}", "status=none"],
            capture_output=True,
            timeout=TIMEOUT,
            check=True,
        )
        return out.stdout


@pytest.fixture
def loop(tmp_path: Path, host_tools: None) -> Iterator[functools.partial]:
    attached: list[str] = []

    def attach(size: int) -> LoopDevice:
        backing = tmp_path / f"disk-{len(attached)}.img"
        with backing.open("wb") as f:
            f.truncate(size)
        out = run(["sudo", "-n", "losetup", "--find", "--show", str(backing)])
        if out.returncode != 0:
            skip_or_fail(f"losetup could not attach a loop device: {out.stderr.strip()}", os.environ)
        attached.append(out.stdout.strip())
        return LoopDevice(backing, attached[-1])

    yield attach
    for device in attached:
        run(["sudo", "-n", "losetup", "--detach", device])


def disk_image(path: Path, size: int, label: str = "gpt") -> bytes:
    """A raw disk image with one partition and a payload behind the partition table."""
    with path.open("wb") as f:
        f.truncate(size)
    table = run(["sfdisk", "--quiet", str(path)], input=f"label: {label}\nstart=2048, type=L\n")
    assert table.returncode == 0, table.stderr
    with path.open("r+b") as f:
        f.seek(MIB)
        f.write(hashlib.sha256(path.name.encode()).digest() * 4096)
    return path.read_bytes()


def compress(raw: Path) -> Path:
    out = raw.with_suffix(".raw.zst")
    done = run(["zstd", "-q", "-f", str(raw), "-o", str(out)])
    assert done.returncode == 0, done.stderr
    return out


def flash(helper: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["bash", str(helper), *args])


@pytest.fixture
def http_root(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    root = tmp_path / "www"
    root.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=10)


def test_flashes_a_file_onto_the_device(helper: Path, loop, tmp_path: Path) -> None:
    device = loop(64 * MIB)
    raw = disk_image(tmp_path / "image", 32 * MIB)
    done = flash(helper, str(compress(tmp_path / "image")), device.device)
    assert done.returncode == 0, done.stderr
    assert "Ready to boot." in done.stdout
    assert device.read(32 * MIB) == raw


def test_flashes_over_http(helper: Path, loop, tmp_path: Path, http_root: tuple[Path, str]) -> None:
    root, base = http_root
    device = loop(64 * MIB)
    raw = disk_image(root / "image", 32 * MIB)
    compress(root / "image")
    done = flash(helper, f"{base}/image.raw.zst", device.device)
    assert done.returncode == 0, done.stderr
    assert device.read(32 * MIB) == raw


def test_image_of_exactly_the_device_size(helper: Path, loop, tmp_path: Path) -> None:
    device = loop(32 * MIB)
    raw = disk_image(tmp_path / "image", 32 * MIB)
    done = flash(helper, str(compress(tmp_path / "image")), device.device)
    assert done.returncode == 0, done.stderr
    assert device.read(32 * MIB) == raw


def test_mbr_only_image_is_accepted(helper: Path, loop, tmp_path: Path) -> None:
    device = loop(32 * MIB)
    raw = disk_image(tmp_path / "image", 16 * MIB, label="dos")
    done = flash(helper, str(compress(tmp_path / "image")), device.device)
    assert done.returncode == 0, done.stderr
    assert device.read(16 * MIB) == raw


def test_image_larger_than_the_device_fails(helper: Path, loop, tmp_path: Path) -> None:
    device = loop(16 * MIB)
    disk_image(tmp_path / "image", 32 * MIB)
    done = flash(helper, str(compress(tmp_path / "image")), device.device)
    assert done.returncode != 0
    assert "Ready to boot." not in done.stdout


def test_image_without_a_partition_table_fails(helper: Path, loop, tmp_path: Path) -> None:
    # The first bytes of a qcow2 container: what the helper writes when it is handed the
    # .qcow2.zst a release ships instead of a raw image.
    device = loop(16 * MIB)
    image = tmp_path / "image"
    image.write_bytes(b"QFI\xfb\x00\x00\x00\x03" + bytes(8 * MIB - 8))
    done = flash(helper, str(compress(image)), device.device)
    assert done.returncode == 1
    assert "holds no partition table" in done.stderr
    assert "Ready to boot." not in done.stdout


def test_truncated_stream_fails(helper: Path, loop, tmp_path: Path) -> None:
    device = loop(64 * MIB)
    disk_image(tmp_path / "image", 32 * MIB)
    packed = compress(tmp_path / "image")
    packed.write_bytes(packed.read_bytes()[: packed.stat().st_size // 2])
    done = flash(helper, str(packed), device.device)
    assert done.returncode != 0
    assert "Ready to boot." not in done.stdout


def test_http_404_fails(helper: Path, loop, http_root: tuple[Path, str]) -> None:
    _, base = http_root
    device = loop(16 * MIB)
    done = flash(helper, f"{base}/missing.raw.zst", device.device)
    assert done.returncode != 0
    assert "Ready to boot." not in done.stdout
    assert device.read(16 * MIB) == bytes(16 * MIB)


def test_target_that_is_no_block_device_is_refused(helper: Path, host_tools: None, tmp_path: Path) -> None:
    target = tmp_path / "not-a-disk"
    target.write_bytes(b"keep")
    raw = tmp_path / "image"
    disk_image(raw, 4 * MIB)
    done = flash(helper, str(compress(raw)), str(target))
    assert done.returncode == 1
    assert "is not a valid block device" in done.stderr
    assert target.read_bytes() == b"keep"


@pytest.mark.parametrize("args", [(), ("image.raw.zst",), ("a", "b", "c")])
def test_wrong_argument_count_prints_usage(helper: Path, args: tuple[str, ...]) -> None:
    done = flash(helper, *args)
    assert done.returncode == 1
    assert done.stdout.startswith("Usage: ")
