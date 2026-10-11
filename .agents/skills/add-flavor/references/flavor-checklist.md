# New Flavor Addition Quality Gate Checklist

> Rigorous verification checklist for adding any new image flavor to `lusoris-cloud-images`. Follow every gate before proposing a pull request.

---

## 1. Single Source of Truth (`versions.json`)
- [ ] If flavor introduces new software, repositories, or driver branches, add them to `versions.json`.
- [ ] Validate against schema: `python3 -c "import json, jsonschema; s=json.load(open('versions.schema.json')); d=json.load(open('versions.json')); jsonschema.validate(d, s)"`.
- [ ] Ensure **zero** hardcoded URLs or versions in Packer templates or shell scripts.

## 2. Packer HCL2 Build Definition (`packer/builds.pkr.hcl`)
- [ ] Define `build { name = "<flavor-id>" sources = ["source.qemu.image"] ... }`.
- [ ] Assign proper provisioners in strict execution order (00-base, 05-agents, 10-time, 20-sysctl, 25-baremetal, hardware, runtime, 99-cleanup).
- [ ] Validate syntax: `cd packer && packer validate .`.

## 3. Shell Provisioner Standards (`packer/provisioners/*.sh`)
- [ ] Script starts with `#!/usr/bin/env bash` and `set -euo pipefail`.
- [ ] All functions are $\le 60$ lines (NASA/JPL Power of 10).
- [ ] Bounded loops and checked return codes.
- [ ] Zero ShellCheck warnings: `shellcheck packer/provisioners/NN-script.sh`.
- [ ] File permissions are executable (`chmod +x`).

## 4. Test Suite Synchrony (`tests/test_flavors.py`)
- [ ] Add `<flavor-id>` to `EXPECTED_FLAVORS` list in `tests/test_flavors.py`.
- [ ] Verify test suite passes: `pytest tests/test_flavors.py -v`.

## 5. Build Automation (`Makefile` & Workflows)
- [ ] Add `build-<flavor-id>` target in `Makefile`.
- [ ] Add flavor to workflow matrix in `.github/workflows/release-matrix.yml` (if release-eligible).

## 6. Documentation & Architecture Synchrony (Same PR)
- [ ] Add flavor row to `FLAVORS.md` under the correct workload tier.
- [ ] Add flavor row to `docs/flavors/matrix.md`.
- [ ] Add description and usage guide in relevant `docs/flavors/*.md` topic page.
- [ ] Verify Material for MkDocs builds cleanly: `mkdocs build --strict`.

## 7. Security & Zero-Leak Invariants
- [ ] Verify zero private RFC 1918 IPs: `pytest tests/test_security_privacy.py -k test_no_private_rfc1918_ips`.
- [ ] Verify zero developer workstation paths: `pytest tests/test_security_privacy.py -k test_no_developer_workstation_paths`.

