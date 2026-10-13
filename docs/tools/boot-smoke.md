# Boot Smoke Test

A Packer build that finishes shows only that the provisioners ran. It does not show that the image boots. The `Boot the Image Once` step of [`release-matrix.yml`](https://github.com/cordanaLLM/imago/blob/main/.github/workflows/release-matrix.yml) boots every built flavor once, before its SBOM is generated and before it is compressed, catalogued and released. A flavor that does not boot fails its job and is never published.

## Run it

```bash
python3 -I tools/ci/boot_smoke.py --image packer/output-images/base-generic/<image>.qcow2 --accel kvm
```

It needs `qemu-system-x86_64` and `xorriso`. `--accel` is `kvm` on a workstation and `tcg` on a hosted runner, which has no `/dev/kvm`. `--timeout` (default 1500 s) is the deadline for the marker. The script exits 0 and prints `boot smoke test passed:` with the marker line, or prints `::error::boot smoke test failed for <image>:` with the reason and the last 40 lines of the QEMU and serial log, and exits 1.

## What it does

[`tools/ci/boot_smoke.py`](https://github.com/cordanaLLM/imago/blob/main/tools/ci/boot_smoke.py):

1. Writes a NoCloud seed (`cidata` ISO) with a fresh instance id, so cloud-init runs again on an image whose state `99-cleanup.sh` cleared.
2. Boots the image with `snapshot=on`: writes go to a throw-away overlay and the image file stays byte-identical.
3. The seed's `runcmd` writes `IMAGO-BOOT-OK <nonce> <kernel release>` to `ttyS0` and powers the machine off.
4. Polls the serial log until the marker with this run's nonce appears, QEMU exits or the deadline passes.

The marker proves that the kernel booted, the root file system mounted, systemd reached `cloud-final.service` and cloud-init read the seed. The seed holds the nonce reversed and the guest's `rev` turns it round, so a console that only echoes the seed shows no marker.

| Case | Result |
| :--- | :--- |
| Marker with this run's nonce | pass |
| Marker with another nonce, or the seed echoed | fail at the deadline |
| No output | fail at the deadline |
| QEMU exits before the marker | fail at once, with its exit code |
| Missing file, not `.qcow2`, unknown accelerator | fail before QEMU starts |

## Evidence

- **Live.** The Ubuntu 26.04 cloud image booted to the marker under KVM in 25 s and under emulation (`tcg`) in 95 s on a workstation; its SHA-256 was unchanged afterwards. An empty disk failed at the deadline.
- **Tests.** [`tests/test_boot_smoke.py`](https://github.com/cordanaLLM/imago/blob/main/tests/test_boot_smoke.py) runs the script against a stub QEMU for every case of the table, holds the overlay and read-only seed in the QEMU command line, and checks that the workflow runs the step between the build and compression, without `continue-on-error`.
