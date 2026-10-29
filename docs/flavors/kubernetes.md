# Kubernetes Node Flavors

`k8s-node-*` flavors provide production-grade, hardened Kubernetes worker node appliances running on Ubuntu 26.04 LTS (Resolute) with containerd 2.x and strict Cgroup v2 resource accounting.

To balance zero first-boot latency with disk footprint, `imago` provides both **Lean (Zero-Preheat)** and **Preheated CNI Profiles** (`cilium`, `calico`, `flannel`).

---

## Pre-Baked Runtimes & Container Standards

- **Distro Base**: Ubuntu 26.04 LTS (Resolute) cloud kernel.
- **Container Runtime**: `containerd 2.3.5` with native Cgroup v2 systemd driver (`SystemdCgroup = true`), `discard_unpacked_layers = true` for SSD/NVMe endurance, and `sandbox_image = "registry.k8s.io/pause:3.10"`.
- **Node Binaries**: Pinned Kubernetes `v1.37.0` (`kubelet`, `kubeadm`, `kubectl`) held via `apt-mark hold`.
- **Kernel Acceleration**: OverlayFS metacopy and redirect directory acceleration (`metacopy=on`, `redirect_dir=on`), BPF JIT compiler hardening (`bpf_jit_harden=2`), and conntrack table scaled to 1,048,576 entries.
- **Networking**: `br_netfilter` loaded, bridge sysctls active (`net.bridge.bridge-nf-call-iptables = 1`), IP forwarding enabled, and swap permanently disabled.

```mermaid
flowchart TD
    %% Semantic class definitions with vibrant, high-contrast jewel palettes
    classDef vip fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#ffffff
    classDef core fill:#e11d48,stroke:#be123c,stroke-width:2px,color:#ffffff
    classDef runtime fill:#7c3aed,stroke:#6d28d9,stroke-width:2px,color:#ffffff
    classDef cni fill:#059669,stroke:#047857,stroke-width:2px,color:#ffffff
    classDef hw fill:#d97706,stroke:#b45309,stroke-width:2px,color:#ffffff
    classDef os fill:#334155,stroke:#1e293b,stroke-width:2px,color:#ffffff

    subgraph ControlPlaneVIP["High Availability Virtual IP"]
        KV["kube-vip:v1.2.3<br/><small>Control Plane API HA</small>"]:::vip
    end

    subgraph NodeStack["Kubernetes Worker Node Architecture"]
        direction TB
        subgraph K8sCore["Node Core Binaries (Pinned v1.37.0)"]
            Kubelet["kubelet (Cgroup v2)"]:::core
            Kubeadm["kubeadm & kubectl"]:::core
        end

        subgraph RuntimeLayer["Container Runtime (containerd 2.3.5)"]
            Containerd["containerd.service<br/><small>SystemdCgroup = true · discard_unpacked_layers</small>"]:::runtime
            Pause["registry.k8s.io/pause:3.10"]:::runtime
        end

        subgraph CNIProfiles["Modular CNI Profiles"]
            Cilium["Cilium 1.20.1<br/><small>eBPF Routing & Policies</small>"]:::cni
            Calico["Calico 3.32.2<br/><small>BGP & VXLAN Overlay</small>"]:::cni
            Flannel["Flannel 0.28.9<br/><small>Lightweight VXLAN</small>"]:::cni
        end

        subgraph HardwareCDI["Hardware Acceleration & CDI"]
            IntelDP["Intel GPU Device Plugin<br/><small>Level Zero / iHD</small>"]:::hw
            AMDDP["AMD ROCm Device Plugin<br/><small>/dev/kfd & /dev/dri</small>"]:::hw
            NvidiaDP["NVIDIA Device Plugin<br/><small>CDI / NVLink Fabric</small>"]:::hw
        end

        subgraph OSFoundation["Linux Kernel 6.14+ (Hardened Foundation)"]
            BBR["BBR + TCP ECN"]:::os
            BPF["bpf_jit_harden = 2"]:::os
            Netfilter["br_netfilter & OverlayFS Metacopy"]:::os
        end
    end

    OSFoundation --> RuntimeLayer
    RuntimeLayer --> K8sCore
    RuntimeLayer --> CNIProfiles
    RuntimeLayer --> HardwareCDI
    K8sCore -.-> KV

    style ControlPlaneVIP fill:none,stroke:#0284c7,stroke-width:2px,stroke-dasharray: 4 4
    style NodeStack fill:none,stroke:#64748b,stroke-width:2px
    style K8sCore fill:none,stroke:#e11d48,stroke-width:2px,stroke-dasharray: 4 4
    style RuntimeLayer fill:none,stroke:#7c3aed,stroke-width:2px,stroke-dasharray: 4 4
    style CNIProfiles fill:none,stroke:#059669,stroke-width:2px,stroke-dasharray: 4 4
    style HardwareCDI fill:none,stroke:#d97706,stroke-width:2px,stroke-dasharray: 4 4
    style OSFoundation fill:none,stroke:#334155,stroke-width:2px,stroke-dasharray: 4 4
```

---

## Modular Preheat Profiles

Image pre-caching is driven declaratively via the `preheat_profile` Packer variable:

| Preheat Profile | Cached Images | Use Case |
| :--- | :--- | :--- |
| **`lean`** | `pause:3.10` only | Bare minimum footprint (~800MB root). Ideal for clusters pulling images from a local pull-through registry or air-gapped mirror. |
| **`cilium`** | `pause:3.10`, `coredns:v1.14.7`, `cilium:v1.20.1`, `cilium/operator-generic:v1.20.1`, `kube-vip:v1.2.3`, `node-exporter:v1.12.1` | eBPF-native clusters using Cilium for L3/L4/L7 routing, egress gateway, and NetworkPolicy. |
| **`calico`** | `pause:3.10`, `coredns:v1.14.7`, `calico/cni:v3.32.2`, `calico/node:v3.32.2`, `calico/kube-controllers:v3.32.2`, `kube-vip:v1.2.3`, `node-exporter:v1.12.1` | Enterprise BGP and standard IP-in-IP / VXLAN overlay clusters using Tigera Calico. |
| **`flannel`** | `pause:3.10`, `coredns:v1.14.7`, `flannel:v0.28.9`, `flannel-cni-plugin:v1.6.2-flannel1`, `kube-vip:v1.2.3`, `node-exporter:v1.12.1` | Minimal, lightweight overlay networking for edge or resource-constrained nodes. |

---

## Hardware-Specific Node Flavors

All hardware-specific flavors include the respective Container Device Interface (CDI) specifications and device plugins preheated in containerd's `k8s.io` namespace:

- **`k8s-node-generic`**: Standard CPU worker node with `lean` zero-preheat footprint.
- **`k8s-node-cilium`**: Standard CPU worker node with preheated Cilium eBPF stack.
- **`k8s-node-calico`**: Standard CPU worker node with preheated Calico networking.
- **`k8s-node-flannel`**: Standard CPU worker node with preheated Flannel overlay.
- **`k8s-node-intel`**: Intel Arc/Xe2 acceleration with Intel Device Plugin (`docker.io/intel/intel-gpu-plugin:0.36.0`).
- **`k8s-node-amd`**: AMD ROCm 7.2 compute runtime with AMD GPU Device Plugin (`docker.io/rocm/k8s-device-plugin:1.31.0.11`).
- **`k8s-node-nvidia`**: NVIDIA Mainstream 595 driver with NVIDIA K8s Device Plugin (`nvcr.io/nvidia/k8s-device-plugin:v0.20.0`).
- **`k8s-node-nvidia-modern`**: NVIDIA Modern 615 driver (Ada Lovelace / Hopper) with NVIDIA K8s Device Plugin.
- **`k8s-node-nvidia-bleeding`**: NVIDIA Bleeding 615 driver (Blackwell RTX 5090 / B200) with NVIDIA K8s Device Plugin.

---

## High-Performance Dual Runtimes (`runc` & `crun`)

Following [ADR-0010](../adr/0010-container-ecosystem-runtimes-and-tooling.md), all `k8s-node-*` appliances ship with both standard `runc` and the ultra-fast, C-based `crun` OCI runtime:

- **Default Runtime (`runc`)**: Guarantees universal compatibility with third-party tools, security scanners, and stock Kubernetes workloads.
- **Accelerated Runtime (`crun`)**: Pre-registered in `/etc/containerd/config.toml` (`io.containerd.runc.v2` with `BinaryName = "crun"`). Cuts container creation latency by 2–3x and reduces per-container runtime resident memory from ~25MB to ~4MB.
- **crun version floor**: `crun` comes from the Ubuntu archive; `runtimes.crun` in `versions.json` is the lowest release the image accepts, and `50-k8s-runtime.sh` and `41-podman-runtime.sh` fail the build when the archive ships an older one.

To utilize `crun` on any deployment, define a cluster `RuntimeClass` and reference it in the Pod spec:

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: crun
handler: crun
---
apiVersion: v1
kind: Pod
metadata:
  name: high-performance-workload
spec:
  runtimeClassName: crun
  containers:
    - name: app
      image: registry.example.com/workload:latest
```

---

## Zero-Footprint Container Diagnostics (`cdebug`)

All Kubernetes node images pre-bake `cdebug` under `/usr/local/bin/cdebug`. Operators can troubleshoot distroless or minimal containers directly on the host without mutating the target container or installing debugging packages inside production pods:

```bash
# Attach an ephemeral debugging shell to a running container via containerd
sudo cdebug exec -it --runtime containerd <container-id>

# Attach a fully-equipped network diagnostic toolkit (netshoot) to a pod namespace
sudo cdebug exec -it --image nicolaka/netshoot --runtime containerd <container-id>
```

---

## Lazy-Pulling Snapshotter (`stargz-snapshotter`)

Following [ADR-0010](../adr/0010-container-ecosystem-runtimes-and-tooling.md), the Kubernetes images that run `50-k8s-runtime.sh` (`k8s-node-*`, `cloudnative-k8s`) register `stargz-snapshotter` as an opt-in proxy plugin in `/etc/containerd/config.toml` (`[proxy_plugins.stargz]`). overlayfs stays the default snapshotter. A pull opts in with `sudo ctr-remote image rpull <image>`; making it the CRI default is an operator choice in the same file.
