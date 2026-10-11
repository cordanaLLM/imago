# Copyright 2026 Lusoris
"""Hermetic Mock Execution Sandbox for Shell Provisioners.

Executes shell provisioner scripts in an isolated, sandboxed environment using
Git Bash, intercepting system commands (apt-get, systemctl, modprobe, curl, tee, etc.)
and recording execution journals and simulated filesystem mutations.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional


def _find_bash() -> Optional[Path]:
    found = shutil.which("bash")
    if found:
        return Path(found)
    if sys.platform == "win32":
        for cand in [
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
        ]:
            if cand.exists():
                return cand
    for cand in [Path("/bin/bash"), Path("/usr/bin/bash")]:
        if cand.exists():
            return cand
    return None


BASH_BIN = _find_bash()
GIT_BASH = BASH_BIN

# Bash prelude sourced through BASH_ENV before a provisioner runs. It replaces the system
# commands a provisioner calls with functions that journal the call instead of executing it.
_PRELUDE = r"""# Mock Prelude
# mock_status is the exit status of a mocked command: 1 when MOCK_FAIL names the command,
# 0 otherwise. A test sets MOCK_FAIL to prove that a provisioner stops on that failure.
mock_status() {
  case " ${MOCK_FAIL:-} " in
    *" $1 "*) return 1 ;;
  esac
  return 0
}
export -f mock_status

sudo() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -E|-u|-i|-s|--preserve-env|--) shift ;;
      -*) shift ;;
      *=* ) export "$1"; shift ;;
      *) break ;;
    esac
  done
  "$@"
}
export -f sudo

tee() {
  local append=""
  local target=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -a|--append) append="1"; shift ;;
      -*) shift ;;
      *) target="$1"; shift ;;
    esac
  done
  if [ -n "$target" ] && [ -n "$SANDBOX_ROOT" ]; then
    local clean="${target#/}"
    local dest="$SANDBOX_ROOT/$clean"
    command mkdir -p "$(dirname "$dest")" 2>/dev/null || true
    if [ -n "$append" ]; then
      cat >> "$dest"
    else
      cat > "$dest"
    fi
    echo "$target" >> "$SANDBOX_ROOT/journal_files.log"
  else
    cat >/dev/null
  fi
}
export -f tee

mkdir() {
  echo "mkdir $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  for arg in "$@"; do
    case "$arg" in
      -*) ;;
      /*)
        local clean="${arg#/}"
        command mkdir -p "$SANDBOX_ROOT/$clean" 2>/dev/null || true
        ;;
      *)
        command mkdir -p "$arg" 2>/dev/null || true
        ;;
    esac
  done
  return 0
}
export -f mkdir

touch() {
  echo "touch $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  for arg in "$@"; do
    case "$arg" in
      -*) ;;
      /*)
        local clean="${arg#/}"
        command mkdir -p "$(dirname "$SANDBOX_ROOT/$clean")" 2>/dev/null || true
        command touch "$SANDBOX_ROOT/$clean" 2>/dev/null || true
        ;;
      *)
        command touch "$arg" 2>/dev/null || true
        ;;
    esac
  done
  return 0
}
export -f touch

gpg() {
  echo "gpg $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -o|--output)
        shift
        local target="$1"
        if [ -n "$target" ] && [ -n "$SANDBOX_ROOT" ]; then
          local clean="${target#/}"
          command mkdir -p "$(dirname "$SANDBOX_ROOT/$clean")" 2>/dev/null || true
          command touch "$SANDBOX_ROOT/$clean" 2>/dev/null || true
        fi
        ;;
      *) ;;
    esac
    shift
  done
  return 0
}
export -f gpg

grep() {
  local args=()
  for arg in "$@"; do
    case "$arg" in
      /*)
        local clean="${arg#/}"
        if [ -f "$SANDBOX_ROOT/$clean" ]; then
          args+=("$SANDBOX_ROOT/$clean")
        else
          args+=("$arg")
        fi
        ;;
      *)
        args+=("$arg")
        ;;
    esac
  done
  command grep "${args[@]}"
}
export -f grep

apt-get() {
  echo "apt-get $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  mock_status apt-get
}
export -f apt-get

apt-mark() {
  echo "apt-mark $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  mock_status apt-mark
}
export -f apt-mark

apt-key() {
  echo "apt-key $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f apt-key

debconf-set-selections() {
  echo "debconf-set-selections $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  mock_status debconf-set-selections
}
export -f debconf-set-selections

dpkg() {
  echo "dpkg $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  if [ "$1" = "--print-architecture" ]; then
    echo "${MOCK_ARCH}"
    return 0
  fi
  return 0
}
export -f dpkg

systemctl() {
  echo "systemctl $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  mock_status systemctl
}
export -f systemctl

modprobe() {
  echo "modprobe $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  mock_status modprobe
}
export -f modprobe

containerd() {
  echo "containerd $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  if [ "$1" = "config" ] && [ "$2" = "default" ]; then
    cat <<'EOF'
version = 3
[plugins."io.containerd.cri.v1.runtime".containerd.runtimes.runc]
  runtime_type = "io.containerd.runc.v2"
EOF
    return 0
  fi
  return 0
}
export -f containerd

update-grub() {
  echo "update-grub $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f update-grub

swapoff() {
  echo "swapoff $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f swapoff

sed() {
  echo "sed $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f sed

curl() {
  echo "curl $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f curl

udevadm() {
  echo "udevadm $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f udevadm

partprobe() {
  echo "partprobe $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f partprobe

parted() {
  echo "parted $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f parted

fstrim() {
  echo "fstrim $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f fstrim

install() {
  echo "install $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f install

tar() {
  echo "tar $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f tar

chown() {
  echo "chown $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f chown

chmod() {
  echo "chmod $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f chmod

rm() {
  echo "rm $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  for arg in "$@"; do
    case "$arg" in
      -*) ;;
      /*)
        local clean="${arg#/}"
        if [ -e "$SANDBOX_ROOT/$clean" ]; then
          command rm -rf "$SANDBOX_ROOT/$clean" 2>/dev/null || true
        fi
        ;;
      *)
        if [ -e "$arg" ]; then
          command rm -rf "$arg" 2>/dev/null || true
        fi
        ;;
    esac
  done
  return 0
}
export -f rm

ln() {
  echo "ln $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  return 0
}
export -f ln

usermod() {
  echo "usermod $*" >> "$SANDBOX_ROOT/journal_cmds.log"
  mock_status usermod
}
export -f usermod
"""


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    commands_log: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    sandbox_root: Optional[Path] = None

    def read_file(self, rel_path: str) -> Optional[str]:
        """Read content of a file created in the sandbox (e.g. 'etc/sysctl.d/99-lusoris.conf')."""
        if not self.sandbox_root:
            return None
        target = self.sandbox_root / rel_path.lstrip("/\\")
        if target.exists():
            return target.read_text(encoding="utf-8", errors="replace")
        return None

    def has_command(self, cmd_prefix: str) -> bool:
        """Check if any logged command starts with cmd_prefix."""
        return any(c.startswith(cmd_prefix) for c in self.commands_log)

    def find_commands(self, cmd_name: str) -> List[str]:
        """Return all logged commands matching cmd_name."""
        return [c for c in self.commands_log if c.startswith(cmd_name + " ") or c == cmd_name]


class MockSandbox:
    def __init__(self, tmp_path: Path, arch: str = "amd64"):
        self.tmp_path = tmp_path
        self.arch = arch
        self.sandbox_root = tmp_path / "rootfs"
        self.prelude_file = tmp_path / "prelude.sh"
        self.setup_sandbox()

    def setup_sandbox(self) -> None:
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.prelude_file.write_text(_PRELUDE, encoding="utf-8", newline="\n")

    def run_script(
        self, script_path: Path, env_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        if not BASH_BIN or not BASH_BIN.exists():
            raise RuntimeError("Bash executable not found")

        if sys.platform == "win32" and self.sandbox_root.drive:
            drive = self.sandbox_root.drive.rstrip(":").lower()
            sandbox_posix = f"/{drive}{self.sandbox_root.as_posix()[2:]}"
            prelude_posix = f"/{drive}{self.prelude_file.as_posix()[2:]}"
            script_posix = f"/{drive}{script_path.as_posix()[2:]}"
        else:
            sandbox_posix = str(self.sandbox_root.resolve())
            prelude_posix = str(self.prelude_file.resolve())
            script_posix = str(script_path.resolve())

        run_env = os.environ.copy()
        run_env["SANDBOX_ROOT"] = sandbox_posix
        run_env["MOCK_ARCH"] = self.arch
        run_env["BASH_ENV"] = prelude_posix

        if env_vars:
            for k, v in env_vars.items():
                run_env[k] = v

        cmd = [str(BASH_BIN), "-euo", "pipefail", script_posix]
        proc = subprocess.run(
            cmd,
            env=run_env,
            capture_output=True,
            text=True,
            cwd=str(self.sandbox_root),
        )

        cmds_file = self.sandbox_root / "journal_cmds.log"
        cmds = []
        if cmds_file.exists():
            cmds = [
                line.strip()
                for line in cmds_file.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            ]

        files_file = self.sandbox_root / "journal_files.log"
        files = []
        if files_file.exists():
            files = [
                line.strip()
                for line in files_file.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            ]

        return ExecutionResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            commands_log=cmds,
            files_created=files,
            sandbox_root=self.sandbox_root,
        )
