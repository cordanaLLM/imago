# ADR 0003: NVIDIA Multi-Generational CUDA & Driver Segmentation

## Status

Accepted

## Context

NVIDIA driver releases regularly deprecate older GPU architectures (e.g. CUDA 12.8 drops Pascal sm_60/61). Conversely, newer Blackwell and Hopper GPUs require cutting-edge 615/610 drivers, Open Kernel Modules, and Fabric Manager for NVLink, whereas Turing and Ampere remain most stable on the 565 branch. A single monolithic NVIDIA image causes driver breakage on older hardware and missing features on cutting-edge chips.

## Decision

We partition NVIDIA support into dedicated provisioners and flavor tiers:

1. `*-nvidia-legacy`: NVIDIA 535 LTS branch (`535.309.01`, CUDA 12.2) for Pascal and Volta.
2. `*-nvidia-mainstream`: NVIDIA 565 branch (`565.77`, CUDA 12.8) for Turing and Ampere.
3. `*-nvidia-modern`: NVIDIA 610 branch (`610.57.04`, CUDA 13.3.1) for Ada Lovelace and Hopper.
4. `*-nvidia-bleeding`: NVIDIA 615 branch (`615.71.09`, CUDA 13.4) for Blackwell (RTX 5090, B200).
5. `*-nvidia-datacenter`: NVIDIA Open Kernel Modules + Fabric Manager for Hopper and Blackwell multi-GPU NVLink meshes.

## Consequences

- Pascal and Volta users retain fully functioning CUDA without driver panics.
- Turing, Ampere, and Ada users run stable production-grade drivers.
- Blackwell RTX 5090 / B200 users get instant day-zero acceleration with CUDA 13.4 and native CDI.
- Datacenter operators get turnkey NVLink mesh networking without manual setup.
