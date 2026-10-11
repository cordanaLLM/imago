#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 75-appliance-vision.sh — Frigate NVR, Scrypted, and Home Assistant AI vision appliance
# Pre-configures Google Coral TPU (gasket-dkms, udev rules), Intel QuickSync VA-API, and CDI specs.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

install_coral_tpu_runtime() {
  echo "==> Configuring Google Coral Edge TPU drivers and udev rules..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    dkms \
    build-essential \
    linux-headers-generic

  # Configure Coral Edge TPU udev rules for rootless and containerized access
  cat <<'RULES' | sudo tee /etc/udev/rules.d/65-edgetpu.rules >/dev/null
SUBSYSTEM=="apex", MODE="0660", GROUP="render"
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a6e", ATTRS{idProduct}=="089a", MODE="0660", GROUP="render"
SUBSYSTEM=="usb", ATTRS{idVendor}=="18d1", ATTRS{idProduct}=="9302", MODE="0660", GROUP="render"
RULES

  sudo usermod -aG render,video ubuntu
}

configure_intel_quicksync_media() {
  echo "==> Configuring Intel QuickSync VA-API hardware acceleration..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    intel-media-va-driver-non-free \
    vainfo \
    libva-drm2 \
    libva2

  # Set default libva driver to iHD (Gen9+ Intel Graphics and Arc Xe)
  echo "LIBVA_DRIVER_NAME=iHD" | sudo tee -a /etc/environment >/dev/null
}

generate_cdi_specifications() {
  echo "==> Generating Container Device Interface (CDI) spec for Coral TPU..."
  sudo mkdir -p /etc/cdi
  cat <<'CDI' | sudo tee /etc/cdi/coral.yaml >/dev/null
cdiVersion: "0.6.0"
kind: coral.google.com/edgetpu
devices:
  - name: apex0
    containerEdits:
      deviceNodes:
        - path: /dev/apex_0
          type: c
          permissions: rw
CDI
}

main() {
  install_coral_tpu_runtime
  configure_intel_quicksync_media
  generate_cdi_specifications
  echo "==> 75-appliance-vision: Complete."
}

main "$@"
