# 34. iPXE Netboot Assets and Root Integrity

Date: 2026-10-17

## Status

Accepted. Implements issue #5.

## Context

Bare-metal hosts should boot a flavor over the network without a local disk image. The previous guidance in `docs/platforms/baremetal.md` section 4 told operators to serve their own kernel and initrd with `root=/dev/ram0`. No initrd in the image understands that argument as a network root, so the snippet could not boot.

The facts below were measured on 2026-10-17. The raw notes live in the local evidence file `imago-5-netroot-facts.md`.

1. **The netboot mechanism is dracut, not casper or live-boot.** The Ubuntu 26.04 (resolute) cloud image manifest lists `dracut` 110-11ubuntu0.1, `dracut-core` and `dracut-network`. It lists only `initramfs-tools-core`, not the `initramfs-tools` generator. Neither `casper` nor `live-boot` is installed.
   - `casper` 26.04.2 netboots only through `url=*.iso` or `iso-url=*.iso`, which download a whole ISO.
   - `live-boot` 1:20250815 (universe) is an initramfs-tools hook. Its `verify-checksums` option is a media check that reboots afterwards, so it does not gate the boot.
   - Neither package applies to a dracut-built initrd.
2. **dracut 110 boots a root image over HTTP.** `dracut.cmdline(7)` documents `root=live:<url>` for http, https, ftp, torrent and tftp. It needs the `livenet` module (from `dracut-network`) and the `dmsquash-live` module (from `dracut-core`).
   - The `livenet` module's `check()` returns 255, so dracut includes it only when it is named explicitly.
   - `livenetroot.sh` fetches the image with `curl` and verifies no checksum.
   - `rd.live.ram=1` and `rd.live.overlay.size=` control the copy to RAM and the size of the writable overlay.
3. **iPXE cannot compare digests.** At iPXE master `c51ca76a6e56` (2026-10-15), `md5sum` and `sha1sum` only print a digest, and `imgverify` checks a CMS signature. iPXE does provide the `${cwduri}` setting, the directory of the current script, and it resolves relative URIs against the script's own URI.
4. **Size.** The rootfs of the daily resolute cloud image (sha256 `8800651811af9a85…`) unpacks to 3,153,971,370 B. `mksquashfs` 4.7.5 with zstd level 19 packs it into 634,195,968 B (about 605 MiB). The forge's per-asset limit is 2 GiB (`ASSET_LIMIT_BYTES` in `tools/ci/release_assets.py`). Flavors with GPU stacks are larger than the base image and are measured by the matrix itself.

## Decision

1. **Assets per flavor.** Each release flavor in `.github/workflows/release-matrix.yml` ships four extra assets:
   - `<flavor>-netboot.vmlinuz`: the image's own kernel;
   - `<flavor>-netboot.initrd`: a netboot initrd built by dracut inside the image;
   - `<flavor>-root.squashfs`: the image's root filesystem, packed with zstd;
   - `<flavor>.ipxe`: the boot script.
   All four go into `checksums-<flavor>.sha256`, and so into the cosign-signed `SHA256SUMS`. That signature is what makes the iPXE script a signed asset; iPXE itself does not check it (Context 3).
2. **The netboot initrd.** A Packer provisioner builds it in the guest with `dracut --add "livenet dmsquash-live imago-netroot"`. The kernel the image boots from disk keeps its own initrd unchanged.
3. **Root integrity check.** A new dracut module `imago-netroot` closes the gap in Context 2. It reads `imago.root-sha256=<64 hex>` from the kernel command line and compares it with the sha256 of the fetched squashfs. It runs before `dmsquash-live` mounts the image.
   - A mismatch, a missing value or a malformed value stops the boot with a console message.
   - It never falls back to an unchecked root, and no option skips the check.
   - Hook point: `livenetroot.sh` (dracut 110, `modules.d/70livenet/livenetroot.sh:83`) ends its bounded fetch loop with `exec /sbin/dmsquash-live-root "$root"`, which `70dmsquash-live/module-setup.sh:32` installs. The module installs after `70dmsquash-live` (dracut installs modules in `modules.d` glob order), renames that program to `dmsquash-live-root.orig` and takes its place, so every fetched image, including one fetched after a retry, passes the check before the original runs.
   - dracut ignores a failing module `install()`, so the provisioner reads the built initrd back with `lsinitrd` and fails the build when the module or the renamed original is missing.
4. **The iPXE script.** The script fetches the kernel and initrd by URIs relative to itself. It passes `root=live:${cwduri}<flavor>-root.squashfs`, `ip=dhcp`, `rd.neednet=1` and `imago.root-sha256=<digest>`. An operator therefore serves the four assets from one directory and chains the script. The digest is written into the script at build time from the same file that goes into `SHA256SUMS`.
5. **Kernel and initrd integrity.** iPXE cannot verify these (Context 3). The operator verifies `SHA256SUMS` with `cosign verify-blob` and checks the four assets against it before serving them. `docs/platforms/baremetal.md` states this step. The squashfs digest is checked again at boot (item 3).
6. **Size limit.** The matrix's `release_assets.py sizes` step covers the new assets. An asset at or above 2 GiB fails the flavor build, and a planted oversize asset in the tests proves that.
7. **CI proof.** A test boots `base-generic` in QEMU through iPXE over a local HTTP server: the iPXE script loads the kernel and initrd, and the initrd fetches the squashfs and reaches a multi-user marker on the serial console. The same run with a wrong `imago.root-sha256` must stop before the root is mounted.
8. **Documentation.** `docs/platforms/baremetal.md` section 4 replaces the `root=/dev/ram0` snippet with the shipped script and the verification step.

## Consequences

- Each release flavor grows by about one compressed root image (about 605 MiB for the base image) plus a kernel and an initrd.
- A netbooted host runs from RAM with a writable overlay. Its changes are lost at reboot unless the operator adds persistent storage.
- The image's `/etc/fstab` refers to disk partitions that a netbooted host lacks. The CI boot in item 7 shows whether those entries need handling, and the implementation records the result here.
- A change to the dracut `livenet` or `dmsquash-live` command line is caught by the CI boot, not by a unit test.

## References

- Issue #5.
- `dracut.cmdline(7)`, dracut 110; `modules.d/70livenet` (`livenetroot.sh`, `parse-livenet.sh`), `modules.d/70dmsquash-live` (`module-setup.sh`) and `dracut.sh` at that version.
- iPXE `src/hci/commands/digest_cmd.c`, `src/hci/commands/image_trust_cmd.c`, `src/core/settings.c` at `c51ca76a6e56`.
- Ubuntu resolute cloud image manifest; `casper(7)` 26.04.2; live-boot 1:20250815.
- [ADR-0033](0033-aegis-build-workflow.md) for the 2 GiB asset limit as applied to Aegis.
