# Copyright 2026 Lusoris
"""Regression tests for build defects fixed in September 2026, each failing on the old code.

- #41, #42: the build account is sealed by the shutdown command and nowhere earlier; the
  seal runs before the power-off and a failed seal stops it.
- #44: a preheated image that cannot be pulled fails the build; precache requires every
  image to be injected by the build with no fallback pins.
- #40: the QEMU accelerator is a validated variable, and the release build emulates.
- #43: the compress step reads the directory Packer writes the flavor's image to.
- #39: the release build installs an ISO authoring tool before Packer writes the seed.

Whether a pinned image tag exists in its registry needs the registry and is not tested here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.harness.live import skip_or_fail
from tests.harness.mock_runner import GIT_BASH, MockSandbox
from tests.test_provisioners_execution import check_bash

ROOT = Path(__file__).resolve().parent.parent
PACKER = ROOT / "packer"
PROVISIONERS = PACKER / "provisioners"
PRECACHE = PROVISIONERS / "55-k8s-precache.sh"
RELEASE = ROOT / ".github" / "workflows" / "release-build.yml"
BUILD_PASSWORD = "build-pass"
COMMAND_TIMEOUT_S = 60
SEALED = ["sudo", "rm -f /etc/sudoers.d/90-cloud-init-users", "passwd -l ubuntu", "shutdown -P now"]
EARLY_SEAL = re.compile(r"passwd\s+(-l|--lock)|usermod\s+(-L|--lock)|90-cloud-init-users")
ISO_AUTHORS = {"xorriso", "genisoimage", "mkisofs"}


@pytest.fixture
def require_bash() -> None:
    check_bash(GIT_BASH)


def qemu_source() -> str:
    text = (PACKER / "sources.pkr.hcl").read_text(encoding="utf-8")
    match = re.search(r'^source "qemu" "image" \{\n(.*?)^\}', text, re.S | re.M)
    assert match, 'packer/sources.pkr.hcl has no source "qemu" "image" block'
    return match[1]


def hcl_attribute(block: str, name: str) -> str:
    match = re.search(rf"^\s*{name}\s*=\s*(.+?)\s*$", block, re.M)
    assert match, f"no {name} attribute"
    return match[1]


def variable_default(name: str) -> str:
    text = (PACKER / "variables.pkr.hcl").read_text(encoding="utf-8")
    match = re.search(rf'^variable "{name}" \{{\n(.*?)^\}}', text, re.S | re.M)
    assert match, f"variable {name} is not declared"
    return json.loads(hcl_attribute(match[1], "default"))


def build_steps() -> list[dict]:
    with RELEASE.open(encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)
    return workflow["jobs"]["build-matrix"]["steps"]


def step_running(steps: list[dict], needle: str) -> tuple[int, dict]:
    found = [(i, s) for i, s in enumerate(steps) if needle in s.get("run", "")]
    assert len(found) == 1, f"{len(found)} build-matrix steps run {needle!r}"
    return found[0]


# --- #41, #42: the build account is sealed last ---------------------------------------


def write_stub(directory: Path, name: str, body: str) -> None:
    stub = directory / name
    stub.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    stub.chmod(0o700)


def run_shutdown_command(tmp_path: Path, fail: str = "") -> tuple[int, list[str]]:
    """Run the builder's shutdown command through bash with sudo and the seal steps stubbed."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    write_stub(
        bin_dir,
        "sudo",
        '[ "$1" = "-S" ] || exit 2\nshift\nread -r password\n'
        '[ "$password" = "$BUILD_PASSWORD" ] || exit 1\necho sudo >> "$LOG"\nexec "$@"\n',
    )
    for name in ("rm", "passwd", "shutdown"):
        write_stub(bin_dir, name, f'echo "{name} $*" >> "$LOG"\ncase " $FAIL " in *" {name} "*) exit 1 ;; esac\n')
    command = json.loads(hcl_attribute(qemu_source(), "shutdown_command"))
    command = command.replace("${var.ssh_password}", BUILD_PASSWORD)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}/usr/bin:/bin",
        "LOG": str(log),
        "FAIL": fail,
        "BUILD_PASSWORD": BUILD_PASSWORD,
    }
    result = subprocess.run(
        [str(GIT_BASH), "-c", command], env=env, timeout=COMMAND_TIMEOUT_S, check=False, capture_output=True
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result.returncode, calls


def test_shutdown_command_seals_the_account_then_powers_off(tmp_path: Path, require_bash) -> None:
    status, calls = run_shutdown_command(tmp_path)
    assert status == 0
    assert calls == SEALED


@pytest.mark.parametrize("failing", ["rm", "passwd"])
def test_a_failed_seal_never_powers_off(tmp_path: Path, require_bash, failing: str) -> None:
    status, calls = run_shutdown_command(tmp_path, fail=failing)
    assert status != 0
    assert not any(call.startswith("shutdown") for call in calls), calls


def test_no_provisioner_seals_the_build_account_early() -> None:
    """Every provisioner runs before the shutdown command, and every one of them uses sudo."""
    offending = [
        f"{script.name}:{number}: {line.strip()}"
        for script in sorted(PROVISIONERS.glob("*.sh"))
        for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1)
        if not line.lstrip().startswith("#") and EARLY_SEAL.search(line)
    ]
    assert offending == []


# --- #44: a preheated image that cannot be pulled fails the build ------------------------


def precache_image_pins() -> dict[str, str]:
    builds = (PACKER / "builds.pkr.hcl").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
    paths = dict(re.findall(r"^\s*(img_\w+)\s*=\s*local\.manifest\.([\w.]+)\s*$", builds, re.M))
    passed = dict(re.findall(r'"(IMG_\w+)=\$\{local\.(img_\w+)\}"', builds))
    pins: dict[str, str] = {}
    for variable, local_var in passed.items():
        value = manifest
        for key in paths[local_var].split("."):
            value = value[key]
        pins[variable] = value
    return pins


def run_precache(
    tmp_path: Path,
    profile: str,
    flavor: str,
    failing_image: str = "",
    extra_env: dict[str, str] | None = None,
):
    env = {
        **precache_image_pins(),
        "PREHEAT_PROFILE": profile,
        "FLAVOR": flavor,
        "MOCK_FAIL_IMAGE": failing_image,
    }
    if extra_env:
        env.update(extra_env)
    return MockSandbox(tmp_path).run_script(PRECACHE, env_vars=env)


def pulled(result) -> list[str]:
    return [c.split()[-1] for c in result.find_commands("ctr") if " images pull " in c]


def test_precache_pulls_every_image_of_the_profile(tmp_path: Path, require_bash) -> None:
    pins = precache_image_pins()
    result = run_precache(tmp_path, "flannel", "k8s-node-amd")
    assert result.returncode == 0, result.stderr
    assert pulled(result) == [
        pins["IMG_PAUSE"],
        pins["IMG_COREDNS"],
        pins["IMG_FLANNEL"],
        pins["IMG_FLANNEL_CNI"],
        pins["IMG_KUBE_VIP"],
        pins["IMG_NODE_EXPORTER"],
        pins["IMG_AMD_PLUGIN"],
    ]


def test_lean_profile_pulls_only_the_pause_image(tmp_path: Path, require_bash) -> None:
    result = run_precache(tmp_path, "lean", "k8s-node-generic")
    assert result.returncode == 0, result.stderr
    assert pulled(result) == [precache_image_pins()["IMG_PAUSE"]]


@pytest.mark.parametrize(
    ("profile", "flavor", "image"),
    [
        ("lean", "k8s-node-generic", precache_image_pins()["IMG_PAUSE"]),
        ("flannel", "k8s-node-flannel", precache_image_pins()["IMG_FLANNEL"]),
        ("cilium", "k8s-node-cilium", precache_image_pins()["IMG_CILIUM_OPERATOR"]),
        ("lean", "k8s-node-amd", precache_image_pins()["IMG_AMD_PLUGIN"]),
        ("lean", "k8s-node-nvidia", precache_image_pins()["IMG_NVIDIA_PLUGIN"]),
    ],
)
def test_precache_fails_when_an_image_cannot_be_pulled(
    tmp_path: Path, require_bash, profile: str, flavor: str, image: str
) -> None:
    result = run_precache(tmp_path, profile, flavor, failing_image=image)
    assert result.returncode != 0, f"{flavor} built without {image}"
    assert pulled(result)[-1] == image
    assert "Complete" not in result.stdout


def test_precache_holds_no_fallback_defaults() -> None:
    fallbacks = re.findall(r"\$\{(IMG_\w+):-", PRECACHE.read_text(encoding="utf-8"))
    assert fallbacks == [], f"precache script still holds hardcoded fallbacks: {fallbacks}"


def test_every_image_read_by_precache_is_passed_by_build() -> None:
    script_vars = set(re.findall(r"\$\{?(IMG_[A-Z0-9_]+)", PRECACHE.read_text(encoding="utf-8")))
    passed_vars = set(precache_image_pins().keys())
    assert script_vars, "precache script reads no IMG_* variables"
    assert script_vars <= passed_vars, f"precache reads variables not passed by builds: {script_vars - passed_vars}"


def test_precache_with_unset_image_exits_nonzero_and_pulls_nothing(
    tmp_path: Path, require_bash, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IMG_PAUSE", raising=False)
    env = {k: v for k, v in precache_image_pins().items() if k != "IMG_PAUSE"}
    env.update({"PREHEAT_PROFILE": "lean", "FLAVOR": "k8s-node-generic"})
    result = MockSandbox(tmp_path).run_script(PRECACHE, env_vars=env)
    assert result.returncode != 0
    assert "IMG_PAUSE" in result.stderr
    assert pulled(result) == []


# --- #40: the accelerator is a validated variable, and CI emulates -----------------------


def test_qemu_source_takes_the_accelerator_variable() -> None:
    assert hcl_attribute(qemu_source(), "accelerator") == "var.accelerator"
    assert variable_default("accelerator") == "kvm"


def test_release_build_emulates() -> None:
    _, step = step_running(build_steps(), "make build")
    assert step.get("env", {}).get("PKR_VAR_accelerator") == "tcg"


@pytest.mark.parametrize(("value", "accepted"), [("tcg", True), ("kvm", True), ("bogus", False), ("", False)])
def test_packer_validates_the_accelerator(value: str, accepted: bool) -> None:
    packer = shutil.which("packer")
    if not packer:
        skip_or_fail("packer is required to validate the accelerator variable", os.environ)
    result = subprocess.run(
        [packer, "validate", f"-var=accelerator={value}", "."],
        cwd=PACKER,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_S,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0 and "Unsupported Packer Core version" in output:
        skip_or_fail(f"installed packer does not satisfy required_version: {output.strip()}", os.environ)
    assert (result.returncode == 0) is accepted, output
    if not accepted:
        assert "accelerator must be one of" in output


# --- #43: the compress step reads the directory Packer writes ----------------------------


def test_compress_step_reads_the_flavor_output_directory() -> None:
    assert hcl_attribute(qemu_source(), "output_directory") == '"${var.output_dir}/${var.flavor}"'
    steps = build_steps()
    _, build = step_running(steps, "make build")
    assert "make build" in build["run"]
    assert build.get("env", {}).get("PKR_VAR_flavor") == "${{ matrix.flavor }}"
    _, compress = step_running(steps, "zstd ")
    script = compress["run"]
    flavor = compress.get("env", {}).get("FLAVOR")
    if flavor:
        script = script.replace("${FLAVOR}", flavor)
    expected = f'cd "packer/{variable_default("output_dir")}/${{{{ matrix.flavor }}}}"'
    assert script.lstrip().startswith(expected + "\n"), script


# --- #39: the seed ISO has an authoring tool ---------------------------------------------


def test_release_build_installs_an_iso_author_before_packer() -> None:
    assert "cd_files" in qemu_source()
    steps = build_steps()
    install_at, install = step_running(steps, "apt-get install")
    build_at, _ = step_running(steps, "make build")
    packages = set(install["run"].split("apt-get install", 1)[1].split())
    assert packages & ISO_AUTHORS, packages
    assert install_at < build_at
