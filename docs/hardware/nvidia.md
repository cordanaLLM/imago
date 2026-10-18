# NVIDIA Multi-Generational Acceleration Stacks

To prevent driver incompatibilities, symbol conflicts, and runtime panics across disparate GPU microarchitectures, `lusoris-cloud-images` segments NVIDIA support into four distinct hardware generations plus a dedicated datacenter tier.

All modern and bleeding flavors generate native Container Device Interface (CDI) specifications at `/etc/cdi/nvidia.yaml`, providing seamless device pass-through across Docker, Podman, and containerd without wrapper runtimes.

---

## 1. NVIDIA Legacy (`*-nvidia-legacy`)

- **Microarchitectures**: Pascal (`sm_60`, `sm_61`) and Volta (`sm_70`).
- **Target GPUs**: GTX 1070/1080/1080Ti, Tesla P4, P40, P100, Titan Xp, Tesla V100.
- **Driver & CUDA**: NVIDIA 580 headless branch (`580`) with CUDA 13.0.
- **Why this exists**: The 580 branch is the last NVIDIA driver branch that supports Maxwell, Pascal and Volta; newer branches drop them. The driver exposes the CUDA 13.0 runtime, but CUDA Toolkit 13.0 removed offline compilation and library support for these architectures, so workloads ship containers built with a CUDA 12.x toolkit, which run on this driver.

---

## 2. NVIDIA Mainstream (`*-nvidia-mainstream` / `*-nvidia`)

- **Microarchitectures**: Turing (`sm_75`) and Ampere (`sm_80`, `sm_86`).
- **Target GPUs**: RTX 20/30 series, Tesla T4, A100, A10, A30, L4, RTX A6000.
- **Driver & CUDA**: NVIDIA 595 headless branch (`595`) with CUDA 13.2.
- **Container Device Interface**: Modern CDI v0.6+ specifications generated at `/etc/cdi/nvidia.yaml`.

---

## 3. NVIDIA Modern (`*-nvidia-modern`)

- **Microarchitectures**: Ada Lovelace (`sm_89`) and Hopper (`sm_90`).
- **Target GPUs**: RTX 4080/4090, RTX 6000 Ada, L40, L40S, H100 PCIe.
- **Driver & CUDA**: NVIDIA 615 branch (`615`) with CUDA 13.4.
- **Container Device Interface**: Native CDI specifications generated at `/etc/cdi/nvidia.yaml`.
- **Features**: Ada FP8 Tensor Cores, modern Transformer Engine support, optical flow acceleration.

---

## 4. NVIDIA Bleeding-Edge (`*-nvidia-bleeding`)

- **Microarchitectures**: Blackwell (`sm_100`, `sm_120`).
- **Target GPUs**: GeForce RTX 5080/5090, B100, B200, GB200 NVL.
- **Driver & CUDA**: NVIDIA 615 branch (`615`) with CUDA 13.4.
- **Features**: Blackwell 2nd-gen Transformer Engine, native NVLink-C2C, micro-scaling formats (MXFP4/MXFP6/MXFP8), cutting-edge kernel support on Ubuntu 26.04.

---

## 5. NVIDIA Datacenter (`*-nvidia-datacenter`)

- **Microarchitectures**: Hopper (`sm_90`) and Blackwell (`sm_100`).
- **Target GPUs**: H100, H200, B100, B200, GB200 Superchip clusters.
- **Open Kernel Modules**: Installs the Ubuntu server open kernel modules (`nvidia-headless-615-server-open`, `nvidia-utils-615-server`).
- **Fabric Manager**: Pre-configures and automatically enables `nvidia-fabricmanager-615` for full-mesh NVLink and NVSwitch multi-GPU scaling.
- **GPUDirect Storage (GDS)**: Pre-configured with RDMA, NVMe-oF, and peer-to-peer DMA hooks.

---

## Pinned packages and their check

Every branch and CUDA label comes from `drivers.nvidia` in `versions.json`; the provisioners stop with an error when a pin is missing instead of falling back to a built-in branch.

| Tier | Driver key | Packages | CUDA key |
| :--- | :--- | :--- | :--- |
| legacy | `legacy_driver` (580) | `nvidia-headless-580`, `nvidia-utils-580` | `cuda_legacy` (13.0) |
| mainstream | `mainstream_driver` (595) | `nvidia-headless-595`, `nvidia-utils-595` | `cuda_mainstream` (13.2) |
| modern | `modern_driver` (615) | `nvidia-headless-615-open`, `nvidia-utils-615` | `cuda_modern` (13.4) |
| bleeding | `bleeding_driver` (615) | `nvidia-headless-615-open`, `nvidia-utils-615` | `cuda_bleeding` (13.4) |
| datacenter | `datacenter_driver` (615) | `nvidia-headless-615-server-open`, `nvidia-utils-615-server`, `nvidia-fabricmanager-615` | none |

Modern and bleeding share the 615 branch: the archive carries 610 only as transitional packages that install 615.

`tools/ci/upstream_sources.py check` runs before the Packer build in `release-matrix.yml`. For each tier it reads the Ubuntu 26.04 `Packages` index and fails when a package is absent or transitional (section `oldlibs`, or a single dependency on the same package at another branch). It also fails when the CUDA label has no `cuda-compat-<major>-<minor>` package in NVIDIA's ubuntu2404 repository, or when that package depends on a different driver branch:

```bash
python3 -I tools/ci/upstream_sources.py check   # exit 1 names each missing source
```
