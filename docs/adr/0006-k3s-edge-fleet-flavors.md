# ADR 0006: K3s Lightweight Fleet Edge Flavors

## Status

Accepted

## Context

Standard Kubernetes worker nodes (`k8s-node-*`) run full kubelet, kubeadm, and containerd stacks that require at least 2GB of memory overhead, making them suboptimal for resource-constrained edge systems, single-board computers, low-power mini-PCs (Intel N100 Alder Lake-N), and micro-clusters in homelabs. Users frequently deploy K3s for home automation, Frigate NVR, Jellyfin/Plex transcoding, and edge IoT workloads due to its $\le 300\text{MB}$ idle footprint and self-contained battery-included runtime.

## Decision

We introduce 5 dedicated `k3s-*` image flavors:

1. **`k3s-agent-generic`**: Standard lightweight worker node for low-overhead edge clusters.
2. **`k3s-agent-intel`**: Worker node equipped with Intel Media Driver (`iHD`), QuickSync `/dev/dri/renderD128` access, Level Zero compute, and Intel Device Plugin support.
3. **`k3s-agent-amd`**: Worker node configured with AMD ROCm 10 compute runtime, `/dev/kfd` permissions, and RADV Vulkan.
4. **`k3s-agent-nvidia`**: Worker node configured with NVIDIA Mainstream driver (565), CUDA 12.8, NVIDIA Container Toolkit, and Container Device Interface (CDI) support.
5. **`k3s-server-generic`**: Standalone single-node or control plane master with embedded SQLite/etcd and local-path-provisioner storage.

All K3s flavors:

- Install the official K3s binary pinned from `versions.json` via `packer/provisioners/52-k3s-runtime.sh`.
- Leave systemd services disabled on build to ensure nodes do not start unconfigured prior to cloud-init token discovery.
- Include `/etc/rancher/k3s/registries.yaml` for local registry mirror and caching integration.

## Consequences

- Expands the flavor matrix to 35 fully automated flavors.
- Enables turnkey sub-minute provisioning of lightweight Kubernetes clusters on low-power hardware.
- Full parity with Single Source of Truth (`versions.json`) and NASA/JPL Power of 10 bash rules.
