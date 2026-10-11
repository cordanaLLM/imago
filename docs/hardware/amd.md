# AMD Radeon & ROCm Acceleration Stack

Supported hardware: AMD Radeon RX 6000/7000/8000 series, Ryzen APUs, Radeon Pro, and AMD Instinct MI200/MI300 series.

---

## 1. AMD Mesa Graphics Stack (`*-amd`)

- **Use Case**: Video transcoding, lightweight 3D rendering, desktop acceleration, and general GPU passthrough.
- **Packages**: `mesa-va-drivers` (`radeonsi`), `mesa-vulkan-drivers` (`radv`), `libdrm-amdgpu1`.
- **Diagnostics**: `vainfo`, `vulkan-tools`.
- **CDI**: Generates `/etc/cdi/amd.yaml` granting container access to `/dev/dri/card*` and `/dev/dri/renderD*`.

---

## 2. AMD ROCm Compute Stacks (`*-amd-rocm` / `*-rocm`)

`lusoris-cloud-images` segments AMD compute into **ROCm Legacy** and **ROCm Bleeding-Edge**:

### ROCm Legacy (`rocm_legacy_version: 7.14.0`)

- **Use Case**: Older AMD architectures (RDNA 2, Vega, early CDNA) supported under the stable ROCm 7.x line.
- **Packages**: `rocm-hip-runtime`, `rocminfo`, `hip-runtime-amd`.

### ROCm Bleeding-Edge (`rocm_bleeding_version: 10.0.0` / TheRock)

- **Use Case**: Cutting-edge RDNA 3, RDNA 4 (RX 8000 series), and Instinct MI300/MI325 accelerators with unified ROCm 10 kernel drivers and modern PyTorch 2.6+ wheels.
- **Kernel & Memory**: Configured with 48-bit GPU virtual addressing, IOMMU page tables, and HugeTLB support.
- **Permissions**: Udev rule pre-configured at `/etc/udev/rules.d/70-kfd.rules` granting the `render` group full read/write access to `/dev/kfd`.
- **CDI Specification**: Generates `/etc/cdi/amd.yaml` with explicit `/dev/kfd` and `/dev/dri` device bindings for rootless container execution.

---

## Verifying AMD ROCm & Mesa

```bash
# Check ROCm hardware discovery and HIP runtime
rocminfo

# Verify Mesa VA-API hardware acceleration
vainfo --display drm --device /dev/dri/renderD128
```
