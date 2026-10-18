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

### Version pins and apt source

`versions.json` (`drivers.amd`) holds every coordinate [`32-gpu-amd-rocm.sh`](https://github.com/cordanaLLM/imago/blob/main/packer/provisioners/32-gpu-amd-rocm.sh) fetches:

| Field | Value | Use |
| :--- | :--- | :--- |
| `rocm_bleeding_version` | `7.2.4` | the ROCm release the image installs (`ROCM_VERSION`) |
| `rocm_legacy_version` | `6.4.4` | the last 6.x release; pinned, not yet installed by any flavor |
| `rocm_repo` | `https://repo.radeon.com/rocm` | key `rocm.gpg.key` and `apt/<version>` live below it |
| `rocm_apt_suite` | `noble` | the apt suite of the ROCm repository |

AMD publishes ROCm for Ubuntu 22.04 (`jammy`) and 24.04 (`noble`) only. The image is Ubuntu 26.04 (`resolute`), so it installs the `noble` packages, and the provisioner prints that substitution in the build log. The Ubuntu 26.04 archive also ships an older ROCm (7.1); an apt pin (`/etc/apt/preferences.d/rocm-pin-600`, priority 600 for `o=repo.radeon.com`, as in AMD's install guide) keeps apt from mixing the two.

`tools/ci/upstream_sources.py check` requests the key and the `Release` file of every pinned version before the Packer build in `release-matrix.yml`; a pin AMD does not publish fails that step in seconds:

```bash
python3 -I tools/ci/upstream_sources.py urls    # list the URLs
python3 -I tools/ci/upstream_sources.py check   # exit 1 names each URL that did not answer 200
```

### Installed packages

- **Packages**: `rocm-hip-runtime`, `rocminfo`, `hwinfo`.
- **Use Case**: RDNA 2/3/4 Radeon and Instinct accelerators covered by the ROCm 7.2 support matrix.
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
