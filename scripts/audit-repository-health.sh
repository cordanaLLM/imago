#!/usr/bin/env bash
# Copyright 2026 Lusoris
# scripts/audit-repository-health.sh — Repository Health & Quality Gate Audit
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

audit_privacy_and_secrets() {
  echo "==> [1/7] Auditing privacy and zero-leak invariants..."
  local leak_count=0

  # Check for private RFC 1918 IPs in tracked non-doc non-test files
  while IFS= read -r file; do
    if [[ "${file}" == *.md || "${file}" == docs/* || "${file}" == tests/* ]]; then
      continue
    fi
    if grep -nE '\b(10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3})\b' "${ROOT_DIR}/${file}" >/dev/null 2>&1; then
      echo "    Error: RFC 1918 IP address detected in ${file}"
      leak_count=$((leak_count + 1))
    fi
  done < <(git -C "${ROOT_DIR}" ls-files)

  # Check for workstation /home/* paths
  while IFS= read -r file; do
    if [[ "${file}" == tests/* || "${file}" == *.pyc ]]; then
      continue
    fi
    if grep -nE '/home/[a-zA-Z0-9_-]+/(dev|workspace|src)' "${ROOT_DIR}/${file}" >/dev/null 2>&1; then
      echo "    Error: Local workstation /home/ user path detected in ${file}"
      leak_count=$((leak_count + 1))
    fi
  done < <(git -C "${ROOT_DIR}" ls-files)

  if [ "${leak_count}" -ne 0 ]; then
    echo "    Privacy audit failed with ${leak_count} violation(s)."
    return 1
  fi
  echo "    ✓ Privacy & zero-leak audit passed."
}

audit_license_headers() {
  echo "==> [2/7] Auditing copyright license headers on scripts..."
  local missing=0
  while IFS= read -r -d '' script; do
    if ! grep -q "Copyright 2026 Lusoris" "${script}"; then
      echo "    Error: Missing copyright license header in ${script}"
      missing=$((missing + 1))
    fi
  done < <(find "${ROOT_DIR}/packer/provisioners" "${ROOT_DIR}/scripts" -type f -name "*.sh" -print0)

  if [ "${missing}" -ne 0 ]; then
    return 1
  fi
  echo "    ✓ All shell scripts carry required license headers."
}

audit_executable_permissions() {
  echo "==> [3/7] Auditing script executable permissions..."
  while IFS= read -r -d '' script; do
    if [ ! -x "${script}" ]; then
      echo "    Fixing: adding executable bit to ${script}"
      chmod +x "${script}"
    fi
  done < <(find "${ROOT_DIR}/packer/provisioners" "${ROOT_DIR}/scripts" -type f -name "*.sh" -print0)
  echo "    ✓ Script permissions verified."
}

audit_manifest_schema() {
  echo "==> [4/7] Auditing versions.json against versions.schema.json..."
  python3 -c "
import json, jsonschema, sys
with open('${ROOT_DIR}/versions.schema.json') as sf, open('${ROOT_DIR}/versions.json') as mf:
    schema = json.load(sf)
    manifest = json.load(mf)
    jsonschema.validate(instance=manifest, schema=schema)
" || {
    echo "    Error: versions.json failed schema validation!"
    return 1
  }
  echo "    ✓ versions.json schema valid."
}

# count_matching_lines prints how many lines of a file match a pattern. grep -c exits 1
# when the count is zero, which is a valid answer here; only a status above 1 is an error.
count_matching_lines() {
  local pattern="$1"
  local file="$2"
  local count
  local status=0
  count=$(grep -c "${pattern}" "${file}") || status=$?
  if [ "${status}" -gt 1 ]; then
    echo "    Error: cannot read ${file}" >&2
    return 1
  fi
  echo "${count}"
}

audit_flavor_synchrony() {
  echo "==> [5/7] Auditing 44-flavor synchrony across repository..."
  local hcl_builds
  hcl_builds=$(count_matching_lines 'name    = "' "${ROOT_DIR}/packer/builds.pkr.hcl")
  if [ "${hcl_builds}" -ne 44 ]; then
    echo "    Error: packer/builds.pkr.hcl contains ${hcl_builds} builds (expected 44)!"
    return 1
  fi

  local rm_flavors
  rm_flavors=$(count_matching_lines '^[[:space:]]*- base-\|^[[:space:]]*- docker-\|^[[:space:]]*- podman-\|^[[:space:]]*- k8s-\|^[[:space:]]*- k3s-\|^[[:space:]]*- cloudnative-\|^[[:space:]]*- ai-infer-\|^[[:space:]]*- appliance-' "${ROOT_DIR}/.github/workflows/release-matrix.yml")
  # 44 in workflow_dispatch + 2 in test matrix = 46 matches
  if [ "${rm_flavors}" -lt 44 ]; then
    echo "    Error: release-matrix.yml has fewer than 44 flavor options!"
    return 1
  fi
  echo "    ✓ All 44 production flavors synchronized across Packer and CI."
}

audit_static_linters() {
  echo "==> [6/7] Running ShellCheck and Yamllint..."
  if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${ROOT_DIR}/packer/provisioners/"*.sh "${ROOT_DIR}/scripts/"*.sh
    echo "    ✓ ShellCheck passed with zero warnings."
  fi

  if command -v yamllint >/dev/null 2>&1; then
    yamllint -c "${ROOT_DIR}/.yamllint.yml" "${ROOT_DIR}/.github/" "${ROOT_DIR}/packer/http/" >/dev/null
    echo "    ✓ Yamllint passed."
  fi
}

audit_actionlint() {
  echo "==> [7/7] Auditing GitHub Actions workflows with actionlint..."
  if command -v actionlint >/dev/null 2>&1; then
    actionlint "${ROOT_DIR}/.github/workflows/"*.yml
    echo "    ✓ Actionlint passed."
  elif [ -x "${HOME}/go/bin/actionlint" ]; then
    "${HOME}/go/bin/actionlint" "${ROOT_DIR}/.github/workflows/"*.yml
    echo "    ✓ Actionlint passed."
  fi
}

main() {
  echo "========================================================"
  echo " Lusoris Cloud Images — Repository Health Quality Audit"
  echo "========================================================"
  audit_privacy_and_secrets
  audit_license_headers
  audit_executable_permissions
  audit_manifest_schema
  audit_flavor_synchrony
  audit_static_linters
  audit_actionlint
  echo "========================================================"
  echo " ✓ REPOSITORY HEALTH AUDIT: ALL QUALITY GATES PASSED"
  echo "========================================================"
}

main "$@"
