# Copyright 2026 Lusoris
"""Verification that the boot smoke test passes only on a boot it observed.

`tools/ci/boot_smoke.py` boots a built image in QEMU with a NoCloud seed and passes only
when the serial console shows the marker with this run's nonce. The tests below run it
against a stub QEMU: it passes on a guest that runs the seed's command, and fails on a
console that only echoes the seed, a marker from another run, a silent guest, an early
QEMU exit and an image that is not qcow2. They also hold the throw-away overlay that keeps
the released image unwritten, and the workflow step that runs the check after the build.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "boot_smoke.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-build.yml"

_spec = importlib.util.spec_from_file_location("boot_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

# A QEMU stand-in. It reads the seed's user-data (the seed path is the cdrom drive), and by
# STUB_MODE writes to the serial file what a guest would: "ok" runs the seed's command,
# "echo" prints the seed verbatim, "other" prints a marker with another nonce, "early"
# exits at once, "silent" never prints. STUB_LINGER keeps it running after it printed.
STUB = """
import os, re, subprocess, sys, time
args = sys.argv[1:]
serial = next(a for a in args if a.startswith("file:"))[len("file:"):]
seed = next(a for a in args if "media=cdrom" in a).split(",")[0][len("file="):]
text = open(seed, encoding="utf-8").read()
mode = os.environ["STUB_MODE"]
with open(serial, "w", encoding="utf-8") as out:
    out.write("[    0.000000] Linux version 7.0.0\\n")
    if mode == "ok":
        reversed_nonce = re.search(r"echo ([0-9a-f]+) \\| rev", text).group(1)
        out.write(f"IMAGO-BOOT-OK {reversed_nonce[::-1]} 7.0.0-stub\\n")
    elif mode == "echo":
        out.write(text)
    elif mode == "other":
        out.write("IMAGO-BOOT-OK 0123456789abcdef 7.0.0-stub\\n")
    elif mode == "early":
        sys.exit(3)
if mode in ("echo", "other", "silent") or os.environ.get("STUB_LINGER"):
    time.sleep(60)
"""


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """Run the stub instead of QEMU and write the seed as plain text instead of an ISO."""
    script = tmp_path / "stub_qemu.py"
    script.write_text(STUB, encoding="utf-8")
    real = smoke.command
    monkeypatch.setattr(smoke, "command", lambda *args: [sys.executable, "-I", str(script), *real(*args)[1:]])

    def seed(workdir, nonce, _xorriso):
        path = workdir / "user-data"
        path.write_text(smoke.user_data(nonce), encoding="utf-8")
        return path

    monkeypatch.setattr(smoke, "seed_iso", seed)
    monkeypatch.setattr(smoke, "POLL_S", 0.05)
    monkeypatch.setattr(smoke, "STOP_GRACE_S", 1)
    image = tmp_path / "image.qcow2"
    image.write_bytes(b"QFI\xfb")

    def run(mode: str, timeout: float = 3, linger: bool = False) -> int:
        monkeypatch.setenv("STUB_MODE", mode)
        if linger:
            monkeypatch.setenv("STUB_LINGER", "1")
        return smoke.main(["--image", str(image), "--timeout", str(timeout)])

    return run


def test_guest_that_runs_the_seed_passes(stub, capsys):
    assert stub("ok") == 0
    assert re.search(r"passed: IMAGO-BOOT-OK [0-9a-f]{16} 7\.0\.0-stub", capsys.readouterr().out)


def test_guest_that_keeps_running_after_the_marker_is_stopped(stub):
    assert stub("ok", linger=True) == 0


def test_console_that_only_echoes_the_seed_fails(stub, capsys):
    assert stub("echo", timeout=1) == 1
    assert "no marker on the serial console within 1 s" in capsys.readouterr().err


def test_marker_of_another_run_fails(stub):
    assert stub("other", timeout=1) == 1


def test_silent_guest_fails_on_the_deadline(stub, capsys):
    assert stub("silent", timeout=1) == 1
    err = capsys.readouterr().err
    assert "within 1 s" in err and "Linux version 7.0.0" in err


def test_early_qemu_exit_fails(stub, capsys):
    assert stub("early") == 1
    assert "QEMU exited 3 before the image printed the marker" in capsys.readouterr().err


def test_image_that_is_not_qcow2_fails(tmp_path, capsys):
    raw = tmp_path / "image.raw"
    raw.write_bytes(b"")
    assert smoke.main(["--image", str(raw)]) == 1
    assert "is not a qcow2 image" in capsys.readouterr().err


def test_missing_image_fails(tmp_path):
    assert smoke.main(["--image", str(tmp_path / "absent.qcow2")]) == 1


def test_unknown_accelerator_fails(stub, tmp_path, capsys):
    image = tmp_path / "image.qcow2"
    assert smoke.main(["--image", str(image), "--accel", "hvf"]) == 1
    assert "unknown accelerator hvf" in capsys.readouterr().err


def test_seed_holds_the_nonce_only_reversed():
    nonce = "0123456789abcdef"
    data = smoke.user_data(nonce)
    assert nonce not in data and nonce[::-1] in data
    assert yaml.safe_load(data)["power_state"]["mode"] == "poweroff"


def test_marker_line_needs_this_nonce():
    log = "boot\nIMAGO-BOOT-OK aaaa 7.0\nIMAGO-BOOT-OK bbbb 7.0\n"
    assert smoke.marker_line(log, "bbbb") == "IMAGO-BOOT-OK bbbb 7.0"
    assert smoke.marker_line(log, "cccc") == ""
    assert smoke.marker_line("", "aaaa") == ""


def test_released_image_is_never_written():
    args = smoke.command("qemu", Path("i.qcow2"), Path("s.iso"), Path("c.log"), "tcg")
    image = next(a for a in args if a.startswith("file=i.qcow2"))
    assert "snapshot=on" in image.split(",")
    seed = next(a for a in args if a.startswith("file=s.iso"))
    assert {"media=cdrom", "readonly=on"} <= set(seed.split(","))
    assert "-no-reboot" in args and "accel=tcg" in args[args.index("-machine") + 1]


def load_build_steps() -> list[dict]:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["jobs"]["build-matrix"]["steps"]


def test_workflow_boots_every_built_image_before_it_is_released():
    steps = load_build_steps()
    names = [step.get("name", "") for step in steps]
    boot = next(i for i, step in enumerate(steps) if "tools/ci/boot_smoke.py" in step.get("run", ""))
    assert names.index("Build Image with Packer") < boot < names.index("Compress Image with Zstandard")
    step = steps[boot]
    assert "--accel tcg" in step["run"] and "--image" in step["run"]
    assert "continue-on-error" not in step and "if" not in step
