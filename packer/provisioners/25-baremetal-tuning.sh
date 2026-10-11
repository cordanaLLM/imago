#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 25-baremetal-tuning.sh — Bare-metal hardware, CPU generation, and firmware tuning
# Configures Intel/AMD microcode, physical NIC drivers, IOMMU, and NVMe optimization.
set -euo pipefail

BM_GEN="${BM_GEN:-generic}"

install_microcode_and_firmware() {
  echo "==> Configuring bare-metal CPU microcode and hardware firmware for '${BM_GEN}'..."
  sudo apt-get update

  case "${BM_GEN}" in
    *intel*)
      echo "    Installing Intel microcode and QAT firmware..."
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        intel-microcode linux-firmware
      ;;
    *amd*)
      echo "    Installing AMD microcode and SEV firmware..."
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        amd64-microcode linux-firmware
      ;;
    *)
      echo "    Installing universal microcode (both Intel & AMD safe auto-detect)..."
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        intel-microcode amd64-microcode linux-firmware
      ;;
  esac
}

configure_kernel_and_iommu() {
  echo "==> Configuring bare-metal IOMMU, CPU scaling, and hugepage parameters..."
  local iommu_param="iommu=pt"

  case "${BM_GEN}" in
    *intel*)
      iommu_param="intel_iommu=on iommu=pt intel_pstate=active"
      ;;
    *amd*)
      iommu_param="amd_iommu=on iommu=pt amd_pstate=active"
      ;;
    *)
      iommu_param="intel_iommu=on amd_iommu=on iommu=pt"
      ;;
  esac

  if [ -f /etc/default/grub ]; then
    sudo sed -i "s/GRUB_CMDLINE_LINUX_DEFAULT=\"[^\"]*/& ${iommu_param}/" /etc/default/grub
    sudo update-grub
  fi
}

configure_nvme_and_expansion() {
  echo "==> Configuring NVMe storage scheduler and cloud-guest auto-growroot..."
  cat <<'EOF' | sudo tee /etc/udev/rules.d/60-baremetal-storage.rules
# Bare-metal NVMe, VirtIO, and high-speed SAS storage tuning
ACTION=="add|change", KERNEL=="nvme[0-9]*", ATTR{queue/scheduler}="none"
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="mq-deadline"
ACTION=="add|change", KERNEL=="vd[a-z]", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="mq-deadline"
EOF

  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    cloud-guest-utils fdisk parted
}

install_disk_stream_helper() {
  echo "==> Installing bare-metal direct-to-disk stream helper..."
  cat <<'EOF' | sudo tee /usr/local/bin/lusoris-install-to-disk
#!/usr/bin/env bash
# Stream and flash a compressed lusoris cloud image directly to physical storage.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <image-url-or-file.raw.zst> <target-disk-dev>"
  echo "Example: $0 https://releases.lusoris.org/lusoris-base-generic.raw.zst /dev/nvme0n1"
  exit 1
fi

SRC="$1"
DEST="$2"

if [ ! -b "${DEST}" ]; then
  echo "Error: Target '${DEST}' is not a valid block device." >&2
  exit 1
fi

echo "==> Flashing '${SRC}' to '${DEST}'..."
if [[ "${SRC}" =~ ^https?:// ]]; then
  curl -fsSL "${SRC}" | zstdcat | sudo dd of="${DEST}" bs=4M status=progress conv=fsync
else
  zstdcat "${SRC}" | sudo dd of="${DEST}" bs=4M status=progress conv=fsync
fi

echo "==> Flash complete. Re-reading partition table..."
sudo partprobe "${DEST}" || true
echo "==> Ready to boot."
EOF
  sudo chmod +x /usr/local/bin/lusoris-install-to-disk
}

main() {
  install_microcode_and_firmware
  configure_kernel_and_iommu
  configure_nvme_and_expansion
  install_disk_stream_helper
  echo "==> 25-baremetal-tuning: Complete."
}

main "$@"
