#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 55-k8s-precache.sh — Modular pre-pulling of Kubernetes DaemonSets and runtime images
# Supports profiles: lean (pause only), cilium, calico, flannel.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

PREHEAT_PROFILE="${PREHEAT_PROFILE:-lean}"

precache_by_profile() {
  local pause_img="${IMG_PAUSE:?IMG_PAUSE must be set by the Packer build}"
  local coredns_img="${IMG_COREDNS:?IMG_COREDNS must be set by the Packer build}"
  local kubevip_img="${IMG_KUBE_VIP:?IMG_KUBE_VIP must be set by the Packer build}"
  local exporter_img="${IMG_NODE_EXPORTER:?IMG_NODE_EXPORTER must be set by the Packer build}"
  local images_to_pull=("${pause_img}")

  echo "==> Executing preheat profile: '${PREHEAT_PROFILE}'..."
  sudo systemctl start containerd

  case "${PREHEAT_PROFILE}" in
    cilium)
      local cilium_img="${IMG_CILIUM:?IMG_CILIUM must be set by the Packer build}"
      local operator_img="${IMG_CILIUM_OPERATOR:?IMG_CILIUM_OPERATOR must be set by the Packer build}"
      images_to_pull+=("${coredns_img}" "${cilium_img}" "${operator_img}" "${kubevip_img}" "${exporter_img}")
      ;;
    calico)
      local calico_cni="${IMG_CALICO_CNI:?IMG_CALICO_CNI must be set by the Packer build}"
      local calico_node="${IMG_CALICO_NODE:?IMG_CALICO_NODE must be set by the Packer build}"
      local calico_ctrl="${IMG_CALICO_CTRL:?IMG_CALICO_CTRL must be set by the Packer build}"
      images_to_pull+=("${coredns_img}" "${calico_cni}" "${calico_node}" "${calico_ctrl}" "${kubevip_img}" "${exporter_img}")
      ;;
    flannel)
      local flannel_img="${IMG_FLANNEL:?IMG_FLANNEL must be set by the Packer build}"
      local flannel_cni="${IMG_FLANNEL_CNI:?IMG_FLANNEL_CNI must be set by the Packer build}"
      images_to_pull+=("${coredns_img}" "${flannel_img}" "${flannel_cni}" "${kubevip_img}" "${exporter_img}")
      ;;
    lean | none | *)
      echo "    Lean profile selected: caching pause container only (~1.2GB image target)."
      ;;
  esac

  # A preheated image is the whole reason these flavors exist, so a pull that fails
  # fails the build. Warning and continuing produced an image that advertised a cached
  # CNI and contained none, which is discovered on a cluster rather than here.
  for img in "${images_to_pull[@]}"; do
    echo "    Pulling: ${img}"
    if ! sudo ctr -n k8s.io images pull "${img}"; then
      echo "    Error: could not pull ${img}; this flavor is defined by carrying it." >&2
      return 1
    fi
  done
}

# pull_plugin caches one hardware plugin and refuses to continue without it, for the
# same reason as the CNI images: a GPU flavor that does not carry its device plugin is
# the one thing that flavor promises.
pull_plugin() {
  local image="$1"
  if ! sudo ctr -n k8s.io images pull "${image}"; then
    echo "    Error: could not pull ${image}; this flavor is defined by carrying it." >&2
    return 1
  fi
}

precache_hardware_plugins() {
  local flavor="${FLAVOR:-}"
  echo "==> Checking hardware plugin images for '${flavor}'..."

  case "${flavor}" in
    *intel*)
      local intel_plugin="${IMG_INTEL_PLUGIN:?IMG_INTEL_PLUGIN must be set by the Packer build}"
      echo "    Pulling Intel Device Plugin: ${intel_plugin}..."
      pull_plugin "${intel_plugin}"
      ;;
    *nvidia*)
      local nvidia_plugin="${IMG_NVIDIA_PLUGIN:?IMG_NVIDIA_PLUGIN must be set by the Packer build}"
      echo "    Pulling NVIDIA Device Plugin: ${nvidia_plugin}..."
      pull_plugin "${nvidia_plugin}"
      ;;
    *amd*)
      local amd_plugin="${IMG_AMD_PLUGIN:?IMG_AMD_PLUGIN must be set by the Packer build}"
      echo "    Pulling AMD Device Plugin: ${amd_plugin}..."
      pull_plugin "${amd_plugin}"
      ;;
    *)
      echo "    No extra hardware daemonsets required for flavor '${flavor}'"
      ;;
  esac
}

main() {
  precache_by_profile
  precache_hardware_plugins
  echo "==> 55-k8s-precache: Complete."
}

main "$@"
