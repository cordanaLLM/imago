# Copyright 2026 Lusoris
"""Live Container Integration Test Suite using Docker.

Validates hardened configurations (OpenSSH daemon syntax, sysctl file parsing,
and rootfs filesystem contracts) inside an ephemeral Ubuntu 24.04 container.
"""

import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVISIONERS_DIR = REPO_ROOT / "packer" / "provisioners"

UBUNTU_IMAGE = "ubuntu:24.04"

# Bounds in seconds. Starting the container and installing openssh-server
# depend on the host's disk, network and load, so each has its own bound and a
# host that exceeds one skips the sshd tests with the measured time. `sshd -t` itself
# returns in well under a second and keeps a short budget.
CONTAINER_START_BOUND_S = 120
INSTALL_BOUND_S = 300
SSHD_CHECK_BOUND_S = 20
CONTAINER_REMOVE_BOUND_S = 60
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


class SshdContainer(NamedTuple):
    name: str
    install_seconds: float


def run_preparation(cmd: list[str], bound_s: float, what: str) -> subprocess.CompletedProcess[str]:
    """Run a host-dependent preparation step; skip the test when it exceeds its bound."""
    started = time.monotonic()
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=bound_s, check=False)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        pytest.skip(
            f"{what} did not finish within {bound_s:g} s on this host "
            f"(stopped after {elapsed:.1f} s); sshd -t was not run"
        )


def start_container(name: str) -> None:
    """Start an idle Ubuntu container under `name`."""
    cmd = ["docker", "run", "-d", "--rm", "--name", name, UBUNTU_IMAGE, "sleep", str(CONTAINER_LIFETIME_S)]
    res = run_preparation(cmd, CONTAINER_START_BOUND_S, "container start")
    assert res.returncode == 0, f"docker run failed: {res.stderr or res.stdout}"


def install_openssh(name: str, bound_s: float) -> float:
    """Install openssh-server in the container; return the measured time in seconds."""
    started = time.monotonic()
    res = run_preparation(
        ["docker", "exec", name, "bash", "-c", INSTALL_SCRIPT], bound_s, "openssh-server installation"
    )
    assert res.returncode == 0, f"openssh-server installation failed: {res.stderr or res.stdout}"
    return time.monotonic() - started


def remove_container(name: str) -> None:
    """Remove the container; an absent container is not an error for `docker rm -f`."""
    res = subprocess.run(
        ["docker", "rm", "-f", name],
        capture_output=True,
        text=True,
        timeout=CONTAINER_REMOVE_BOUND_S,
        check=False,
    )
    assert res.returncode == 0, f"docker rm -f {name} failed: {res.stderr or res.stdout}"


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


@pytest.fixture(scope="class")
def sshd_container() -> Iterator[SshdContainer]:
    """One Ubuntu container with openssh-server installed, shared by the sshd tests."""
    name = f"imago-sshd-syntax-{uuid.uuid4().hex[:12]}"
    try:
        start_container(name)
        yield SshdContainer(name, install_openssh(name, INSTALL_BOUND_S))
    finally:
        remove_container(name)


@docker_required
class TestContainerIntegration:
    def test_openssh_configuration_syntax_in_ubuntu(self, sshd_container: SshdContainer) -> None:
        """Verify 00-hardened-sshd.conf passes sshd -t syntax and cryptographic validation in real Ubuntu."""
        res = sshd_syntax_check(sshd_container.name, hardened_sshd_config())

        took = f"installation took {sshd_container.install_seconds:.1f} s"
        assert res.returncode == 0, f"sshd -t failed in Ubuntu 24.04 ({took}): {res.stderr or res.stdout}"
        assert "SSHD_SYNTAX_VALID" in res.stdout

    def test_openssh_invalid_directive_is_rejected(self, sshd_container: SshdContainer) -> None:
        """A drop-in with a directive sshd does not know must fail the same check."""
        config = hardened_sshd_config() + "ImagoNoSuchDirective yes\n"

        res = sshd_syntax_check(sshd_container.name, config)

        assert res.returncode != 0, "sshd -t accepted a drop-in with an unknown directive"
        assert "ImagoNoSuchDirective" in res.stderr
        assert "SSHD_SYNTAX_VALID" not in res.stdout

    def test_openssh_installation_timeout_skips(self, sshd_container: SshdContainer) -> None:
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

    def test_cdi_spec_json_validation_in_ubuntu(self) -> None:
        """Verify generated CDI specification conforms to valid JSON / YAML structure."""
        script_path = PROVISIONERS_DIR / "75-appliance-vision.sh"
        content = script_path.read_text(encoding="utf-8")

        start_marker = "cat <<'CDI' | sudo tee /etc/cdi/coral.yaml >/dev/null\n"
        end_marker = "\nCDI\n"
        start_idx = content.find(start_marker)
        assert start_idx != -1
        end_idx = content.find(end_marker, start_idx)
        assert end_idx != -1
        cdi_yaml = content[start_idx + len(start_marker) : end_idx]

        bash_cmd = f"""set -euo pipefail
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-yaml >/dev/null
python3 -c "
import yaml
data = yaml.safe_load('''{cdi_yaml}''')
assert data['cdiVersion'] == '0.6.0'
assert data['kind'] == 'coral.google.com/edgetpu'
assert len(data['devices']) == 1
print('CDI_SPEC_VALID')
"
"""

        res = subprocess.run(
            ["docker", "run", "--rm", "ubuntu:24.04", "bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )

        assert res.returncode == 0, f"CDI verification failed: {res.stderr}"
        assert "CDI_SPEC_VALID" in res.stdout
