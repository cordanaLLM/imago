---
name: build-image
description: Build a specific Lusoris cloud or k8s node image flavor (generic, intel, amd, nvidia) via Packer QEMU or Proxmox
references:
  - references/flavor-matrix.md
---

# /build-image — Build Image Skill

Execute automated Packer HCL2 builds to produce hardened, cloud-init ready `.qcow2.zst`, `.raw.zst`, or `.vmdk.zst` artifacts.

## Usage

```bash
# 1. Build via Makefile targets
make build-generic
make build-intel
make build-amd
make build-nvidia
make build-k8s-generic

# 2. Or build directly with Packer
cd packer
packer init .
packer build -only="<flavor-id>.qemu.image" .
```

## Progressive Disclosure & Reference Tables

For complete flavor IDs, hardware requirements, and target flags across all 44 flavors in 7 workload tiers, consult Layer 3 reference:
- [`references/flavor-matrix.md`](references/flavor-matrix.md)

## Execution Invariants
1. **SSOT Enforcement**: All versions originate from [`versions.json`](../../versions.json).
2. **Artifact Verification**: Build outputs are placed in `output/` with automated sha256 checksums.
3. **Power of 10**: Shell execution must respect timeout ceilings and fail-closed error handling.
