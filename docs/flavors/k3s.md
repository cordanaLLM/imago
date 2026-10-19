# K3s Edge Fleet Flavors

`k3s-*` flavors provide lightweight, battery-included Kubernetes node images designed for resource-constrained edge devices, mini-PCs (Intel N100/N200/N305), single-board computers, and homelab virtualization.

Unlike enterprise `k8s-node-*` flavors requiring $\ge$ 2GB of RAM for the control plane and kubelet stack, K3s runs in $\le$ 300MB of idle memory by packaging containerd, Flannel, CoreDNS, metrics-server, and local-path storage into a single binary.

---

## The 5 K3s Fleet Flavors

| Flavor Name | Role | Hardware Tier | Key Features | Target Homelab Hardware |
| :--- | :--- | :--- | :--- | :--- |
| **`k3s-agent-generic`** | Worker node | VirtIO / CPU | Lightweight K3s agent, pre-configured containerd, Flannel | Intel N95/N100, Raspberry Pi 5, mini-PCs |
| **`k3s-agent-intel`** | Transcode worker | Intel GPU | Intel Media Driver (`iHD`), QuickSync `/dev/dri/renderD128`, Level Zero | Alder Lake-N (N100/N305), Core Ultra (Meteor Lake) |
| **`k3s-agent-amd`** | Compute worker | AMD GPU | AMD ROCm 7.2 compute runtime, `/dev/kfd` permissions, RADV Vulkan | AMD Ryzen 7040/8040 APUs, Radeon RX 7000 |
| **`k3s-agent-nvidia`** | GPU worker | NVIDIA Mainstream | NVIDIA 595 driver branch, CUDA 13.2, Container Toolkit & CDI | NVIDIA RTX 3060/4090, Tesla P4/P40 |
| **`k3s-server-generic`** | Control plane | VirtIO / CPU | K3s server, embedded SQLite/etcd, local-path-provisioner storage | Proxmox standalone VM, micro-cluster master |

---

## Edge & Homelab Architecture

### 1. Minimal Footprint & Fast Discovery

- **Idle Memory**: Operates reliably on 1GB–2GB RAM edge nodes without memory starvation.
- **ZRAM Swap Guard**: Integrated with ZRAM compressed memory swap (`zstd`, 25% RAM), preventing hard OOM kills on memory-dense homelab containers.
- **Fast Boot**: Cloud-init fast boot discovers `NoCloud` or `ConfigDrive` datasources in $< 2$ seconds.

### 2. Container Device Interface (CDI) Ready

All GPU-accelerated agent flavors (`k3s-agent-intel`, `k3s-agent-amd`, `k3s-agent-nvidia`) pre-create `/etc/cdi` specification directories, allowing containers to access hardware accelerators declaratively without proprietary runtime wrappers.

### 3. Declarative Registries & Mirroring

Pre-configures `/etc/rancher/k3s/registries.yaml` with registry mirror fallbacks, allowing seamless offline caching against local pull-through mirrors (such as Harbor or Spegel) to prevent Docker Hub rate-limits.

---

## Cloud-Init Bootstrap Examples

Every K3s image ships with `k3s.service` and `k3s-agent.service` disabled: the installer runs with `INSTALL_K3S_SKIP_ENABLE=true`, and `packer/provisioners/52-k3s-runtime.sh` fails the build when `systemctl is-enabled` reports the role's unit enabled. The node starts K3s only after cloud-init has written the join or server configuration, as the `runcmd` lines below do. An image built before this check booted with the unit enabled; on a netboot root, whose root file system is an overlay, the server crash-looped because containerd's overlayfs snapshotter cannot use that root as an upper directory, and the boot never reached `multi-user.target` (release-matrix run 39140519699).

### Worker Node (`k3s-agent-*`)

To join a K3s cluster, provide the cluster URL and token in your cloud-init `user-data`:

```yaml
#cloud-config
write_files:
  - path: /etc/rancher/k3s/config.yaml.d/20-join.yaml
    permissions: "0600"
    content: |
      server: "https://192.0.2.10:6443"
      token: "K10sampleclusterjointoken::server:secret"
      node-name: "k3s-worker-01"

runcmd:
  - systemctl enable --now k3s-agent.service
```

### Standalone Server (`k3s-server-generic`)

To boot a self-contained single-node cluster with local storage:

```yaml
#cloud-config
write_files:
  - path: /etc/rancher/k3s/config.yaml.d/20-server.yaml
    permissions: "0600"
    content: |
      token: "K10sampleclusterjointoken::server:secret"
      write-kubeconfig-mode: "0644"
      tls-san:
        - "192.0.2.10"
        - "k3s.example.com"

runcmd:
  - systemctl enable --now k3s.service
```
