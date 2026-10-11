# Copyright 2026 Lusoris
"""Live Container Integration Test Suite using Docker.

Validates hardened configurations (OpenSSH daemon syntax, sysctl file parsing,
and rootfs filesystem contracts) inside an ephemeral Ubuntu 24.04 container.
"""

import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVISIONERS_DIR = REPO_ROOT / "packer" / "provisioners"

UBUNTU_IMAGE = "ubuntu:24.04"

# Bounds in seconds. Starting a container and installing a package depend on
# the host's disk, network and load, so each has its own bound and a host that
# exceeds one skips the tests that need the container, with the measured time.
# The checks themselves return in well under a second and keep a short budget.
CONTAINER_START_BOUND_S = 120
INSTALL_BOUND_S = 300
SSHD_CHECK_BOUND_S = 20
CDI_CHECK_BOUND_S = 20
CONTAINER_REMOVE_BOUND_S = 60
# A loaded host can answer `docker rm -f` with an error while the container is
# still stopping, so the removal is tried this many times, with a pause between
# the attempts, before a container that remains fails the test.
CONTAINER_REMOVE_ATTEMPTS = 3
CONTAINER_REMOVE_PAUSE_S = 2.0
# The idle container removes itself after this time, also when the test process
# is killed before its own cleanup runs.
CONTAINER_LIFETIME_S = 900

SSHD_DROP_IN = "/etc/ssh/sshd_config.d/00-hardened-sshd.conf"

INSTALL_SCRIPT = """set -euo pipefail
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server >/dev/null
mkdir -p /etc/ssh/sshd_config.d /run/sshd
touch /etc/ssh/trusted-user-ca-keys.pub
"""

YAML_INSTALL_SCRIPT = """set -euo pipefail
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-yaml >/dev/null
"""

CDI_SPEC_PATH = "/etc/cdi/coral.yaml"

# The specification arrives on standard input, so its text never becomes Python or shell syntax.
CDI_CHECK_SCRIPT = """import sys
import yaml
data = yaml.safe_load(sys.stdin)
assert data['cdiVersion'] == '0.6.0', data['cdiVersion']
assert data['kind'] == 'coral.google.com/edgetpu', data['kind']
assert len(data['devices']) == 1, len(data['devices'])
print('CDI_SPEC_VALID')
"""

# The drop-in arrives on standard input, so its text never becomes shell syntax.
SSHD_CHECK_SCRIPT = f"""set -euo pipefail
cat > {SSHD_DROP_IN}
/usr/sbin/sshd -t
echo "SSHD_SYNTAX_VALID"
"""


def is_docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


docker_required = pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker daemon is required for live container integration tests",
)


class PreparedContainer(NamedTuple):
    name: str
    install_seconds: float


def run_preparation(cmd: list[str], bound_s: float, what: str) -> subprocess.CompletedProcess[str]:
    """Run a host-dependent preparation step; skip the test when it exceeds its bound."""
    started = time.monotonic()
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=bound_s, check=False)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        raise pytest.skip.Exception(
            f"{what} did not finish within {bound_s:g} s on this host "
            f"(stopped after {elapsed:.1f} s); the check that needs it was not run"
        ) from None


def start_container(name: str) -> None:
    """Start an idle Ubuntu container under `name`."""
    cmd = ["docker", "run", "-d", "--rm", "--name", name, UBUNTU_IMAGE, "sleep", str(CONTAINER_LIFETIME_S)]
    res = run_preparation(cmd, CONTAINER_START_BOUND_S, "container start")
    assert res.returncode == 0, f"docker run failed: {res.stderr or res.stdout}"


def install_in_container(name: str, script: str, bound_s: float, what: str) -> float:
    """Run an installation script in the container; return the measured time in seconds."""
    started = time.monotonic()
    res = run_preparation(["docker", "exec", name, "bash", "-c", script], bound_s, what)
    assert res.returncode == 0, f"{what} failed: {res.stderr or res.stdout}"
    return time.monotonic() - started


def install_openssh(name: str, bound_s: float) -> float:
    """Install openssh-server in the container; return the measured time in seconds."""
    return install_in_container(name, INSTALL_SCRIPT, bound_s, "openssh-server installation")


def install_python_yaml(name: str, bound_s: float) -> float:
    """Install python3-yaml in the container; return the measured time in seconds."""
    return install_in_container(name, YAML_INSTALL_SCRIPT, bound_s, "python3-yaml installation")


def docker_rm(name: str) -> str:
    """Run `docker rm -f` once; return an empty string on success, else the reason."""
    cmd = ["docker", "rm", "-f", name]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=CONTAINER_REMOVE_BOUND_S, check=False)
    except subprocess.TimeoutExpired:
        return f"no answer within {CONTAINER_REMOVE_BOUND_S} s"
    if res.returncode == 0:
        return ""
    return (res.stderr or res.stdout).strip() or f"exit status {res.returncode}"


def container_remains(name: str) -> bool:
    """Report whether a container of this name exists; a query without an answer counts as remaining."""
    cmd = ["docker", "ps", "--all", "--quiet", "--filter", f"name=^{name}$"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=CONTAINER_REMOVE_BOUND_S, check=False)
    except subprocess.TimeoutExpired:
        return True
    return res.returncode != 0 or bool(res.stdout.strip())


def remove_container(name: str) -> int:
    """Remove the container and return the number of attempts it took.

    An absent container is not an error for `docker rm -f`. An attempt that
    reports an error still counts as done when the container is gone. A
    container that remains after CONTAINER_REMOVE_ATTEMPTS attempts fails the caller.
    """
    reasons = []
    for attempt in range(1, CONTAINER_REMOVE_ATTEMPTS + 1):
        if attempt > 1:
            time.sleep(CONTAINER_REMOVE_PAUSE_S)
        reason = docker_rm(name)
        if not reason or not container_remains(name):
            return attempt
        reasons.append(reason)
    raise AssertionError(f"container {name} remains after {CONTAINER_REMOVE_ATTEMPTS} removal attempts: {reasons}")


def hardened_sshd_config() -> str:
    """Return the drop-in that 00-base-strip.sh writes, read from the provisioner itself."""
    content = (PROVISIONERS_DIR / "00-base-strip.sh").read_text(encoding="utf-8")
    start_marker = f"cat <<'EOF' | sudo tee {SSHD_DROP_IN}\n"
    end_marker = "\nEOF\n"
    start_idx = content.find(start_marker)
    assert start_idx != -1, f"00-base-strip.sh no longer writes {SSHD_DROP_IN} from a heredoc"
    end_idx = content.find(end_marker, start_idx)
    assert end_idx != -1
    return content[start_idx + len(start_marker) : end_idx] + "\n"


def sshd_syntax_check(name: str, config: str) -> subprocess.CompletedProcess[str]:
    """Write `config` as the hardened drop-in inside the container and run `sshd -t`."""
    return subprocess.run(
        ["docker", "exec", "-i", name, "bash", "-c", SSHD_CHECK_SCRIPT],
        input=config,
        capture_output=True,
        text=True,
        timeout=SSHD_CHECK_BOUND_S,
        check=False,
    )


def coral_cdi_spec() -> str:
    """Return the CDI specification that 75-appliance-vision.sh writes, read from the provisioner itself."""
    content = (PROVISIONERS_DIR / "75-appliance-vision.sh").read_text(encoding="utf-8")
    start_marker = f"cat <<'CDI' | sudo tee {CDI_SPEC_PATH} >/dev/null\n"
    end_marker = "\nCDI\n"
    start_idx = content.find(start_marker)
    assert start_idx != -1, f"75-appliance-vision.sh no longer writes {CDI_SPEC_PATH} from a heredoc"
    end_idx = content.find(end_marker, start_idx)
    assert end_idx != -1
    return content[start_idx + len(start_marker) : end_idx] + "\n"


def cdi_spec_check(name: str, spec: str) -> subprocess.CompletedProcess[str]:
    """Load `spec` with python3-yaml inside the container and check the Coral device contract."""
    return subprocess.run(
        ["docker", "exec", "-i", name, "python3", "-c", CDI_CHECK_SCRIPT],
        input=spec,
        capture_output=True,
        text=True,
        timeout=CDI_CHECK_BOUND_S,
        check=False,
    )


@pytest.fixture(scope="class")
def sshd_container() -> Iterator[PreparedContainer]:
    """One Ubuntu container with openssh-server installed, shared by the sshd tests."""
    name = f"imago-sshd-syntax-{uuid.uuid4().hex[:12]}"
    try:
        start_container(name)
        yield PreparedContainer(name, install_openssh(name, INSTALL_BOUND_S))
    finally:
        remove_container(name)


@pytest.fixture(scope="class")
def yaml_container() -> Iterator[PreparedContainer]:
    """One Ubuntu container with python3-yaml installed, shared by the CDI tests."""
    name = f"imago-cdi-spec-{uuid.uuid4().hex[:12]}"
    try:
        start_container(name)
        yield PreparedContainer(name, install_python_yaml(name, INSTALL_BOUND_S))
    finally:
        remove_container(name)


class TestContainerRemoval:
    """`remove_container` against a stubbed Docker client; no Docker daemon is needed."""

    @staticmethod
    def stub_docker(monkeypatch: pytest.MonkeyPatch, answers: list[str], remains: bool = True) -> list[str]:
        """Stub `docker_rm` with `answers` in order and `container_remains` with `remains`; return the call log."""
        module = sys.modules[__name__]
        calls: list[str] = []

        def fake_rm(name: str) -> str:
            calls.append(f"rm {name}")
            return answers[len(calls) - 1]

        def fake_remains(name: str) -> bool:
            return remains

        monkeypatch.setattr(module, "docker_rm", fake_rm)
        monkeypatch.setattr(module, "container_remains", fake_remains)
        monkeypatch.setattr(module, "CONTAINER_REMOVE_PAUSE_S", 0.0)
        return calls

    def test_first_attempt_removes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.stub_docker(monkeypatch, [""])

        assert remove_container("c1") == 1
        assert calls == ["rm c1"]

    def test_removal_is_retried_after_a_daemon_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.stub_docker(monkeypatch, ["did not receive an exit event", ""])

        assert remove_container("c1") == 2
        assert calls == ["rm c1", "rm c1"]

    def test_error_with_the_container_gone_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.stub_docker(monkeypatch, ["removal is already in progress", ""], remains=False)

        assert remove_container("c1") == 1
        assert calls == ["rm c1"]

    def test_last_allowed_attempt_still_counts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.stub_docker(monkeypatch, ["busy", "busy", ""])

        assert remove_container("c1") == CONTAINER_REMOVE_ATTEMPTS
        assert len(calls) == CONTAINER_REMOVE_ATTEMPTS

    def test_remaining_container_fails_after_the_bound(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.stub_docker(monkeypatch, ["busy", "busy", "still busy", ""])

        with pytest.raises(AssertionError, match="container c1 remains after 3 removal attempts.*still busy"):
            remove_container("c1")
        assert len(calls) == CONTAINER_REMOVE_ATTEMPTS


@docker_required
class TestContainerIntegration:
    def test_removal_leaves_no_container(self) -> None:
        """Against the real daemon: a started container is found, removed in one attempt and then gone."""
        name = f"imago-removal-{uuid.uuid4().hex[:12]}"
        try:
            start_container(name)
            assert container_remains(name), "the started container was not found by its name"
            assert not container_remains(name[:-1]), "a shorter name matched the container"
        finally:
            attempts = remove_container(name)
        assert attempts == 1
        assert not container_remains(name)

    def test_openssh_configuration_syntax_in_ubuntu(self, sshd_container: PreparedContainer) -> None:
        """Verify 00-hardened-sshd.conf passes sshd -t syntax and cryptographic validation in real Ubuntu."""
        res = sshd_syntax_check(sshd_container.name, hardened_sshd_config())

        took = f"installation took {sshd_container.install_seconds:.1f} s"
        assert res.returncode == 0, f"sshd -t failed in Ubuntu 24.04 ({took}): {res.stderr or res.stdout}"
        assert "SSHD_SYNTAX_VALID" in res.stdout

    def test_openssh_invalid_directive_is_rejected(self, sshd_container: PreparedContainer) -> None:
        """A drop-in with a directive sshd does not know must fail the same check."""
        config = hardened_sshd_config() + "ImagoNoSuchDirective yes\n"

        res = sshd_syntax_check(sshd_container.name, config)

        assert res.returncode != 0, "sshd -t accepted a drop-in with an unknown directive"
        assert "ImagoNoSuchDirective" in res.stderr
        assert "SSHD_SYNTAX_VALID" not in res.stdout

    def test_openssh_installation_timeout_skips(self, sshd_container: PreparedContainer) -> None:
        """An installation that exceeds its bound skips; it neither passes nor fails."""
        with pytest.raises(pytest.skip.Exception, match="openssh-server installation did not finish within"):
            install_openssh(sshd_container.name, 0.01)

    def test_sysctl_configuration_syntax_in_ubuntu(self) -> None:
        """Verify 99-lusoris.conf sysctl configuration file parses without syntax errors."""
        script_path = PROVISIONERS_DIR / "20-kernel-sysctl.sh"
        content = script_path.read_text(encoding="utf-8")

        # Extract heredoc between cat <<'EOF' | sudo tee /etc/sysctl.d/99-lusoris.conf and EOF
        start_marker = "cat <<'EOF' | sudo tee /etc/sysctl.d/99-lusoris.conf\n"
        end_marker = "\nEOF\n"
        start_idx = content.find(start_marker)
        assert start_idx != -1
        end_idx = content.find(end_marker, start_idx)
        assert end_idx != -1
        sysctl_conf = content[start_idx + len(start_marker) : end_idx]

        bash_cmd = f"""set -euo pipefail
mkdir -p /etc/sysctl.d
cat <<'EOF' > /etc/sysctl.d/99-lusoris.conf
{sysctl_conf}
EOF
# Verify key-value formatting
grep -v '^#' /etc/sysctl.d/99-lusoris.conf | grep -v '^[[:space:]]*$' | while read -r line; do
  if ! echo "$line" | grep -q ' = '; then
    echo "MALFORMED_LINE: $line" >&2
    exit 1
  fi
done
echo "SYSCTL_SYNTAX_VALID"
"""

        res = subprocess.run(
            ["docker", "run", "--rm", "ubuntu:24.04", "bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert res.returncode == 0, f"Sysctl syntax check failed: {res.stderr}"
        assert "SYSCTL_SYNTAX_VALID" in res.stdout

    def test_cdi_spec_json_validation_in_ubuntu(self, yaml_container: PreparedContainer) -> None:
        """Verify generated CDI specification conforms to valid JSON / YAML structure."""
        res = cdi_spec_check(yaml_container.name, coral_cdi_spec())

        took = f"installation took {yaml_container.install_seconds:.1f} s"
        assert res.returncode == 0, f"CDI verification failed ({took}): {res.stderr or res.stdout}"
        assert "CDI_SPEC_VALID" in res.stdout

    def test_cdi_spec_with_another_kind_is_rejected(self, yaml_container: PreparedContainer) -> None:
        """A specification for another device kind must fail the same check."""
        spec = coral_cdi_spec()
        assert spec.count("coral.google.com/edgetpu") == 1
        spec = spec.replace("coral.google.com/edgetpu", "example.com/other")

        res = cdi_spec_check(yaml_container.name, spec)

        assert res.returncode != 0, "the check accepted a specification for another device kind"
        assert "example.com/other" in res.stderr
        assert "CDI_SPEC_VALID" not in res.stdout

    def test_yaml_installation_timeout_skips(self, yaml_container: PreparedContainer) -> None:
        """An installation that exceeds its bound skips with the measured time; it neither passes nor fails."""
        pattern = r"python3-yaml installation did not finish within 0\.01 s on this host \(stopped after \d+\.\d s\)"
        with pytest.raises(pytest.skip.Exception, match=pattern):
            install_python_yaml(yaml_container.name, 0.01)
