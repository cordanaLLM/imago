# NVIDIA Multi-Generational Acceleration Stacks

To prevent driver incompatibilities, symbol conflicts, and runtime panics across disparate GPU microarchitectures, `lusoris-cloud-images` segments NVIDIA support into four distinct hardware generations plus a dedicated datacenter tier.

All modern and bleeding flavors generate native Container Device Interface (CDI) specifications at `/etc/cdi/nvidia.yaml`, providing seamless device pass-through across Docker, Podman, and containerd without wrapper runtimes.

---

## 1. NVIDIA Legacy (`*-nvidia-legacy`)

- **Microarchitectures**: Pascal (`sm_60`, `sm_61`) and Volta (`sm_70`).
- **Target GPUs**: GTX 1070/1080/1080Ti, Tesla P4, P40, P100, Titan Xp, Tesla V100.
- **Driver & CUDA**: NVIDIA 535 LTS headless branch (`535.309.01`) with CUDA 12.2.
- **Why this exists**: Modern CUDA 12.8+ and driver branches >= 560 officially drop support for Pascal hardware. This flavor guarantees rock-solid stability and compute capability for legacy accelerators.

---

## 2. NVIDIA Mainstream (`*-nvidia-mainstream` / `*-nvidia`)

- **Microarchitectures**: Turing (`sm_75`) and Ampere (`sm_80`, `sm_86`).
- **Target GPUs**: RTX 20/30 series, Tesla T4, A100, A10, A30, L4, RTX A6000.
- **Driver & CUDA**: NVIDIA 565 headless branch (`565.77`) with CUDA 12.8.
- **Container Device Interface**: Modern CDI v0.6+ specifications generated at `/etc/cdi/nvidia.yaml`.

---

## 3. NVIDIA Modern (`*-nvidia-modern`)

- **Microarchitectures**: Ada Lovelace (`sm_89`) and Hopper (`sm_90`).
- **Target GPUs**: RTX 4080/4090, RTX 6000 Ada, L40, L40S, H100 PCIe.
- **Driver & CUDA**: NVIDIA 610 branch (`610.57.04`) with CUDA 13.3.1.
- **Container Device Interface**: Native CDI specifications generated at `/etc/cdi/nvidia.yaml`.
- **Features**: Ada FP8 Tensor Cores, modern Transformer Engine support, optical flow acceleration.

---

## 4. NVIDIA Bleeding-Edge (`*-nvidia-bleeding`)

- **Microarchitectures**: Blackwell (`sm_100`, `sm_120`).
- **Target GPUs**: GeForce RTX 5080/5090, B100, B200, GB200 NVL.
- **Driver & CUDA**: NVIDIA 615 branch (`615.71.09`) with CUDA 13.4.
- **Features**: Blackwell 2nd-gen Transformer Engine, native NVLink-C2C, micro-scaling formats (MXFP4/MXFP6/MXFP8), cutting-edge kernel support on Ubuntu 26.04.

---

## 5. NVIDIA Datacenter (`*-nvidia-datacenter`)

- **Microarchitectures**: Hopper (`sm_90`) and Blackwell (`sm_100`).
- **Target GPUs**: H100, H200, B100, B200, GB200 Superchip clusters.
- **Open Kernel Modules**: Installs official `nvidia-open` 615 kernel modules.
- **Fabric Manager**: Pre-configures and automatically enables `nvidia-fabricmanager-615` for full-mesh NVLink and NVSwitch multi-GPU scaling.
- **GPUDirect Storage (GDS)**: Pre-configured with RDMA, NVMe-oF, and peer-to-peer DMA hooks.
