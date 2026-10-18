#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 80-netboot-initrd.sh — Build the iPXE netboot initrd with the imago-netroot integrity check
# Installs dracut module imago-netroot and builds /boot/imago-netboot.initrd beside the
# normal initrd, which stays unchanged (ADR-0034).
set -euo pipefail

MODULE_DIR="/usr/lib/dracut/modules.d/95imago-netroot"
NETBOOT_INITRD="/boot/imago-netboot.initrd"
NETBOOT_KERNEL="/boot/imago-netboot.vmlinuz"

install_dracut_packages() {
  echo "==> Installing dracut netboot modules (livenet, dmsquash-live)..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends dracut-core dracut-network
}

# dracut sources module-setup.sh into its own shell, so the file sets no shell options.
# Modules install in modules.d glob order (dracut.sh 110), so 70dmsquash-live has placed
# /sbin/dmsquash-live-root before this install() renames it and takes its name.
write_module_setup() {
  sudo tee "${MODULE_DIR}/module-setup.sh" >/dev/null <<'EOF'
#!/bin/bash
# Copyright 2026 Lusoris
# imago-netroot: check the fetched live root against imago.root-sha256= before mounting.

check() {
  return 255
}

depends() {
  echo dmsquash-live
  return 0
}

install() {
  inst_multiple cat sha256sum
  # shellcheck disable=SC2154
  mv "${initdir}/sbin/dmsquash-live-root" "${initdir}/sbin/dmsquash-live-root.orig" || return 1
  # shellcheck disable=SC2154
  inst_script "${moddir}/imago-netroot-verify.sh" "/sbin/dmsquash-live-root"
}
EOF
}

# livenetroot (dracut 110 modules.d/70livenet/livenetroot.sh:83) execs
# /sbin/dmsquash-live-root once its bounded fetch loop holds the image, so every fetched
# image passes this check before dmsquash-live mounts it. dracut-lib.sh 110 aborts under
# set -eu (debug_on reads RD_DEBUG unguarded), so it is sourced only for the final die().
write_verify_hook() {
  sudo tee "${MODULE_DIR}/imago-netroot-verify.sh" >/dev/null <<'EOF'
#!/bin/sh
# Copyright 2026 Lusoris
# imago-netroot-verify.sh — refuse a live root whose sha256 differs from imago.root-sha256=
set -eu

fail() {
  echo "imago-netroot: root sha256 $1" >/dev/kmsg
  echo "imago-netroot: root sha256 $1" >&2
  set +eu
  # shellcheck disable=SC1091
  . /lib/dracut-lib.sh
  die "imago-netroot: root sha256 $1"
  exit 1
}

expected=""
set -f
# shellcheck disable=SC2013
for arg in $(cat /proc/cmdline); do
  case "${arg}" in
    imago.root-sha256=*) expected="${arg#imago.root-sha256=}" ;;
  esac
done
set +f

[ -n "${expected}" ] || fail missing
case "${expected}" in
  *[!0-9a-f]*) fail malformed ;;
esac
[ "${#expected}" -eq 64 ] || fail malformed
image="${1:-}"
[ -n "${image}" ] && [ -r "${image}" ] || fail "image unreadable"

actual="$(sha256sum "${image}")"
actual="${actual%% *}"
[ "${actual}" = "${expected}" ] || fail mismatch
echo "imago-netroot: root sha256 verified ${actual}" >/dev/kmsg
exec /sbin/dmsquash-live-root.orig "$@"
EOF
}

install_imago_netroot_module() {
  echo "==> Installing dracut module imago-netroot into ${MODULE_DIR}..."
  sudo mkdir -p "${MODULE_DIR}"
  write_module_setup
  write_verify_hook
  sudo chmod 0755 "${MODULE_DIR}/module-setup.sh" "${MODULE_DIR}/imago-netroot-verify.sh"
}

find_kernel_version() {
  local kver
  kver="$(find /lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -V | tail -n 1)"
  if [ -z "${kver}" ]; then
    echo "ERROR: no kernel under /lib/modules" >&2
    return 1
  fi
  echo "${kver}"
}

# dracut ignores a failing module install() (dracut.sh 110), so the built image is read
# back: the renamed original and the check must both be inside.
check_netboot_initrd() {
  local listing
  listing="$(sudo lsinitrd "${NETBOOT_INITRD}")"
  if ! grep -q 'sbin/dmsquash-live-root\.orig$' <<<"${listing}"; then
    echo "ERROR: ${NETBOOT_INITRD} lacks dmsquash-live-root.orig; imago-netroot did not wrap it" >&2
    return 1
  fi
  if ! grep -q 'imago-netroot' <<<"${listing}"; then
    echo "ERROR: ${NETBOOT_INITRD} lacks the imago-netroot module" >&2
    return 1
  fi
}

build_netboot_initrd() {
  local kver
  kver="$(find_kernel_version)"
  echo "==> Building ${NETBOOT_INITRD} for kernel ${kver}..."
  sudo dracut --no-hostonly --add "livenet dmsquash-live imago-netroot" --force "${NETBOOT_INITRD}" "${kver}"
  check_netboot_initrd
  # The release step publishes the kernel this link names, so kernel and initrd always pair.
  sudo ln -sfn "vmlinuz-${kver}" "${NETBOOT_KERNEL}"
}

main() {
  install_dracut_packages
  install_imago_netroot_module
  build_netboot_initrd
  echo "==> 80-netboot-initrd: Complete."
}

main "$@"
