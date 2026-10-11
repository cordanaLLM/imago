# Intel GPU Acceleration Stack

Supported hardware: Intel Core Gen 8–15 (UHD/Iris Xe), Intel Arc Alchemist (A380, A750, A770), Intel Arc Battlemage Xe2 (B580, B570), and Intel Data Center Flex series.

---

## Included Packages & Runtimes

- **Intel Media Driver (`intel-media-va-driver-non-free`)**: Hardware-accelerated video decode and encode (AV1, HEVC, H.264, VP9) via VA-API.
- **Level Zero Runtime (`libze1`, `libze-intel-gpu1`)**: Low-level hardware abstraction interface for Intel Xe and Xe2 microarchitectures.
- **oneVPL (`libvpl2`)**: Intel oneAPI Video Processing Library for unified transcode pipelines.
- **OpenCL (`intel-opencl-icd`)**: Intel Compute Runtime for OpenCL applications and AI frameworks (OpenVINO).
- **Diagnostics**: `vainfo`, `clinfo`, and `hwinfo` pre-installed for hardware verification.
- **Container Device Interface**: Generates `/etc/cdi/intel.yaml` granting container runtimes direct access to `/dev/dri/renderD*` devices.

---

## Verifying Intel GPU Acceleration

```bash
# Verify VA-API hardware acceleration
vainfo --display drm --device /dev/dri/renderD128

# Verify OpenCL compute platform
clinfo -l
```
