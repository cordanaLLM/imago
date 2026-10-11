---
name: add-flavor
description: Add a new image flavor (hardware or workload tier) to lusoris-cloud-images with full SSOT, test, and documentation synchrony.
references:
  - references/flavor-checklist.md
---

# Add Flavor Skill

Follow this end-to-end workflow when creating new OS image flavor in `lusoris-cloud-images`.

## Invariants to Preserve
1. **Single Source of Truth**: All versions, container tags, and driver branches must be defined in `versions.json`. Never hardcode strings in templates or provisioners.
2. **NASA/JPL Power of 10**: Any new shell provisioner scripts must enforce `set -euo pipefail`, have functions $\le$ 60 lines, check all return codes, and pass ShellCheck.
3. **Docs & Code Synchrony**: New flavor must be documented in `docs/` and `README.md` in exact same commit/PR.
4. **Trunk-Based PR Flow**: Develop on dedicated `feat/<flavor-name>` branch and open PR.

## Procedure

1. **Update Version Manifest**: Add dependencies to `versions.json` (drivers, images, runtimes).
2. **Define Build Target in Packer**: Add `build { name = "<flavor-id>" ... }` in `packer/builds.pkr.hcl`.
3. **Add or Configure Provisioners**: Create or edit `packer/provisioners/NN-script.sh` complying with Power of 10.
4. **Update Verification Suite**: Add flavor to `EXPECTED_FLAVORS` in `tests/test_flavors.py`.
5. **Update Makefile**: Add `build-<flavor-id>` target in `Makefile`.
6. **Update Documentation**: Add to `FLAVORS.md`, `docs/flavors/matrix.md`, and relevant `docs/flavors/` topic guide.
7. **Verify Gates**: Consult the complete gate checklist in [`references/flavor-checklist.md`](references/flavor-checklist.md).
