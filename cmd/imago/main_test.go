// Copyright 2026 Lusoris
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/aegis"
	"github.com/cordanaLLM/imago/pkg/builder"
	"github.com/cordanaLLM/imago/pkg/kernel"
)

func executeCommand(args ...string) (string, error) {
	cmd := newRootCmd()
	buf := new(bytes.Buffer)
	cmd.SetOut(buf)
	cmd.SetErr(buf)
	cmd.SetArgs(args)
	err := cmd.Execute()
	return buf.String(), err
}

func TestRootHelp(t *testing.T) {
	out, err := executeCommand("--help")
	require.NoError(t, err)
	assert.Contains(t, out, "Imago — Unified CLI & AI MCP Server")
	assert.Contains(t, out, "flavors")
	assert.Contains(t, out, "manifest")
	assert.Contains(t, out, "standards")
}

func TestFlavorsList(t *testing.T) {
	out, err := executeCommand("flavors", "list")
	require.NoError(t, err)
	assert.Contains(t, out, "base-generic")
	assert.Contains(t, out, "docker-generic")
	assert.Contains(t, out, "k8s-node-generic")
}

func TestFlavorsListFilterTier(t *testing.T) {
	out, err := executeCommand("flavors", "list", "--tier=base")
	require.NoError(t, err)
	assert.Contains(t, out, "base-generic")
	assert.NotContains(t, out, "appliance-game-server")
}

func TestFlavorsListJSON(t *testing.T) {
	out, err := executeCommand("flavors", "list", "--json")
	require.NoError(t, err)
	assert.Contains(t, out, `"id": "base-generic"`)
}

func TestFlavorsGet(t *testing.T) {
	out, err := executeCommand("flavors", "get", "base-generic")
	require.NoError(t, err)
	assert.Contains(t, out, `"id": "base-generic"`)
	assert.Contains(t, out, `"tier_id": "base"`)
}

func TestFlavorsGetInvalid(t *testing.T) {
	_, err := executeCommand("flavors", "get", "non-existent-flavor-xyz")
	assert.Error(t, err)
}

func TestManifestValidate(t *testing.T) {
	manifestPath, err := filepath.Abs("../../versions.json")
	require.NoError(t, err)

	out, err := executeCommand("manifest", "validate", "--path", manifestPath)
	require.NoError(t, err)
	assert.Contains(t, out, "is valid")
}

func TestStandardsList(t *testing.T) {
	out, err := executeCommand("standards", "list")
	require.NoError(t, err)
	assert.Contains(t, out, "FLAVOR ID")
}

func TestEpicsList(t *testing.T) {
	epicsPath, err := filepath.Abs("../../.github/epics.json")
	require.NoError(t, err)

	out, err := executeCommand("epics", "list", "--path", epicsPath)
	require.NoError(t, err)
	assert.Contains(t, out, "EPIC")
}

func TestMilestonesList(t *testing.T) {
	milestonesPath, err := filepath.Abs("../../.github/milestones.json")
	require.NoError(t, err)

	out, err := executeCommand("milestones", "list", "--path", milestonesPath)
	require.NoError(t, err)
	assert.Contains(t, out, "TITLE")
	assert.Contains(t, out, "0.1.0 — First release")
}

func TestStandardsGet(t *testing.T) {
	out, err := executeCommand("standards", "get", "base-generic")
	require.NoError(t, err)
	assert.Contains(t, out, `"flavor_id": "base-generic"`)
}

func TestCloudInitGenerate(t *testing.T) {
	out, err := executeCommand("cloud-init", "generate", "--flavor=base-generic", "--platform=proxmox")
	require.NoError(t, err)
	assert.Contains(t, out, "#cloud-config")
}

func TestCloudInitMetadata(t *testing.T) {
	out, err := executeCommand("cloud-init", "metadata", "--hostname=test-node")
	require.NoError(t, err)
	assert.Contains(t, out, `instance-id: "test-node-01"`)
}

func TestApplyCommand(t *testing.T) {
	out, err := executeCommand("apply", "--flavor=base-generic", "--dry-run")
	require.NoError(t, err)
	assert.Contains(t, out, "#!/usr/bin/env bash")
	assert.Contains(t, out, "DRY-RUN:")
}

func TestBootCommand(t *testing.T) {
	out, err := executeCommand("boot", "--flavor=base-generic")
	require.NoError(t, err)
	assert.Contains(t, out, "qemu-system-x86_64")
	assert.Contains(t, out, "-kernel")
}

func TestBuildCommand(t *testing.T) {
	out, err := executeCommand("build", "--flavor=base-generic", "--backend=local", "--dry-run")
	require.NoError(t, err)
	assert.Contains(t, out, "==> Build plan (planned): dry-run:")
	assert.Contains(t, out, "no build was executed")
}

// Remote backends retain the unavailable error without execution evidence.
func TestBuildCommandRefusesEveryBackendWithoutExecutor(t *testing.T) {
	for _, backend := range []string{"gitea", "proxmox", "gitlab", "woodpecker", "harbor", "minio", "jenkins", "github"} {
		t.Run(backend, func(t *testing.T) {
			out, err := executeCommand("build", "--flavor=base-generic", "--backend="+backend)
			require.ErrorIs(t, err, builder.ErrBackendUnavailable)
			assert.NotContains(t, out, "==> Build")
			assert.NotContains(t, out, "Pipeline ID")
			assert.NotContains(t, out, "Artifact")
		})
	}
}

func TestBuildCommandDryRunRefusesUnknownBackend(t *testing.T) {
	out, err := executeCommand("build", "--backend=unknown", "--dry-run")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "unsupported backend")
	assert.NotContains(t, out, "==> Build")
}

func TestAegisValidate(t *testing.T) {
	fixturePath, err := filepath.Abs("../../pkg/aegis/testdata/product-input.json")
	require.NoError(t, err)

	out, err := executeCommand("aegis", "validate", fixturePath)
	require.NoError(t, err)
	assert.Contains(t, out, "aegis-m18-product-input-0001 accepted")
	assert.Contains(t, out, "Kernel: linux-rt (built-here); packages: 3")
	assert.Contains(t, out, "Retries: 3 attempts, 30s backoff")
}

func TestAegisValidateJSON(t *testing.T) {
	fixturePath, err := filepath.Abs("../../pkg/aegis/testdata/product-input.json")
	require.NoError(t, err)

	out, err := executeCommand("aegis", "validate", fixturePath, "--json")
	require.NoError(t, err)
	assert.Contains(t, out, `"correlation_id": "aegis-m18-product-input-0001"`)
	assert.Contains(t, out, `"revision": "61f2fe16bab7889e007b2fd1474b025023906e91"`)
	assert.Contains(t, out, `"backoff": "30s"`)
}

func TestAegisValidateRejectsMissingCorrelationID(t *testing.T) {
	path := filepath.Join(t.TempDir(), "product-input.json")
	require.NoError(t, os.WriteFile(path, []byte(`{"schema": "aegis.p01.product-input.v1"}`), 0o600))

	_, err := executeCommand("aegis", "validate", path)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "aegis product-input (missing): correlation-id: required")
}

func TestAegisValidateRejectsUnknownField(t *testing.T) {
	path := filepath.Join(t.TempDir(), "product-input.json")
	require.NoError(t, os.WriteFile(path, []byte(`{"schema": "aegis.p01.product-input.v1", "correlation-id": "cid-1", "extra": 1}`), 0o600))

	_, err := executeCommand("aegis", "validate", path)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "aegis product-input cid-1: input: strict decode")
}

func TestAegisResultEmit(t *testing.T) {
	fixturePath, err := filepath.Abs("../../pkg/aegis/testdata/product-input.json")
	require.NoError(t, err)

	dir := t.TempDir()
	imgPath := filepath.Join(dir, "image.raw")
	imgData := []byte("built image payload")
	require.NoError(t, os.WriteFile(imgPath, imgData, 0o600))
	imgHex := sha256Hex(imgData)

	sumsPath := filepath.Join(dir, "SHA256SUMS")
	require.NoError(t, os.WriteFile(sumsPath, []byte(fmt.Sprintf("%s  image.raw\n", imgHex)), 0o600))

	sigRef := "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle"
	bootRef := "evidence/boot/aegis-m18-product-input-0001.json"

	out, err := executeCommand("aegis", "result", "emit",
		"--request", fixturePath,
		"--image", imgPath,
		"--checksums", sumsPath,
		"--signature-ref", sigRef,
		"--boot-evidence-ref", bootRef,
	)
	require.NoError(t, err)

	res, err := aegis.ParseResult([]byte(out))
	require.NoError(t, err)
	assert.Equal(t, "aegis-m18-product-input-0001", res.CorrelationID)
	assert.Equal(t, "sha256:"+imgHex, res.ImageDigest)
	assert.Equal(t, sigRef, res.SignatureRef)
	assert.Equal(t, bootRef, res.BootEvidenceRef)
}

func TestAegisResultEmitRejectsUnlistedImage(t *testing.T) {
	fixturePath, err := filepath.Abs("../../pkg/aegis/testdata/product-input.json")
	require.NoError(t, err)

	dir := t.TempDir()
	imgPath := filepath.Join(dir, "image.raw")
	require.NoError(t, os.WriteFile(imgPath, []byte("built image payload"), 0o600))

	sumsPath := filepath.Join(dir, "SHA256SUMS")
	otherHex := strings.Repeat("0", 64)
	require.NoError(t, os.WriteFile(sumsPath, []byte(fmt.Sprintf("%s  other.raw\n", otherHex)), 0o600))

	sigRef := "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle"
	bootRef := "evidence/boot/aegis-m18-product-input-0001.json"

	_, err = executeCommand("aegis", "result", "emit",
		"--request", fixturePath,
		"--image", imgPath,
		"--checksums", sumsPath,
		"--signature-ref", sigRef,
		"--boot-evidence-ref", bootRef,
	)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "does not list the image digest")
}

func TestAegisResultEmitRejectsOtherSignatureForm(t *testing.T) {
	fixturePath, err := filepath.Abs("../../pkg/aegis/testdata/product-input.json")
	require.NoError(t, err)

	dir := t.TempDir()
	imgPath := filepath.Join(dir, "image.raw")
	imgData := []byte("built image payload")
	require.NoError(t, os.WriteFile(imgPath, imgData, 0o600))
	imgHex := sha256Hex(imgData)

	sumsPath := filepath.Join(dir, "SHA256SUMS")
	require.NoError(t, os.WriteFile(sumsPath, []byte(fmt.Sprintf("%s  image.raw\n", imgHex)), 0o600))

	_, err = executeCommand("aegis", "result", "emit",
		"--request", fixturePath,
		"--image", imgPath,
		"--checksums", sumsPath,
		"--signature-ref", "sigstore://rekor.example.com/entries/0001",
		"--boot-evidence-ref", "evidence/boot/aegis-m18-product-input-0001.json",
	)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "signature-ref")
}

func TestAegisResultEmitRequiresEveryFlag(t *testing.T) {
	allFlags := map[string]string{
		"request":           "req.json",
		"image":             "img.raw",
		"checksums":         "SHA256SUMS",
		"signature-ref":     "https://github.com/x/SHA256SUMS.bundle",
		"boot-evidence-ref": "evidence.json",
	}

	for dropFlag := range allFlags {
		t.Run("missing "+dropFlag, func(t *testing.T) {
			args := []string{"aegis", "result", "emit"}
			for flag, val := range allFlags {
				if flag != dropFlag {
					args = append(args, "--"+flag, val)
				}
			}
			out, err := executeCommand(args...)
			require.Error(t, err)
			assert.Contains(t, err.Error(), dropFlag)
			assert.NotContains(t, out, `"schema"`)
		})
	}
}

func writeValidResultFile(t *testing.T) string {
	t.Helper()
	res := map[string]any{
		"schema":            aegis.ResultSchema,
		"correlation-id":    "aegis-m18-product-input-0001",
		"image-digest":      "sha256:" + strings.Repeat("ab", 32),
		"signature-ref":     "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle",
		"boot-evidence-ref": "evidence/boot/aegis-m18-product-input-0001.json",
	}
	data, err := json.Marshal(res)
	require.NoError(t, err)
	path := filepath.Join(t.TempDir(), "result.json")
	require.NoError(t, os.WriteFile(path, data, 0o600))
	return path
}

func TestAegisResultValidate(t *testing.T) {
	path := writeValidResultFile(t)

	out, err := executeCommand("aegis", "result", "validate", path)
	require.NoError(t, err)
	assert.Contains(t, out, "accepted (imago.p01.product-result.v1)")
	assert.Contains(t, out, "Image digest:")
	assert.Contains(t, out, "Signature ref:")
	assert.Contains(t, out, "Boot evidence ref:")

	outJSON, err := executeCommand("aegis", "result", "validate", path, "--json")
	require.NoError(t, err)
	assert.Contains(t, outJSON, `"schema": "imago.p01.product-result.v1"`)
}

func TestAegisResultValidateRejectsUnknownField(t *testing.T) {
	badJSON := []byte(`{
		"schema": "imago.p01.product-result.v1",
		"correlation-id": "cid-1",
		"image-digest": "sha256:` + strings.Repeat("ab", 32) + `",
		"signature-ref": "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle",
		"boot-evidence-ref": "evidence/boot/aegis-m18-product-input-0001.json",
		"unknown": 1
	}`)
	path := filepath.Join(t.TempDir(), "bad.json")
	require.NoError(t, os.WriteFile(path, badJSON, 0o600))

	_, err := executeCommand("aegis", "result", "validate", path)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "strict decode")
}

func TestSignatureBundleNameMatchesKernelRelease(t *testing.T) {
	assert.Equal(t, kernel.BundleFile, aegis.SignatureBundleFile)
}

const testKernelRevision = "188c35d188c35d188c35d188c35d188c35d18800"

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// writeKernelRelease lays out a nucleus-style release (two artifacts,
// SHA256SUMS, placeholder bundle) and its manifest; it returns both paths.
func writeKernelRelease(t *testing.T) (manifestPath, dir string) {
	t.Helper()
	dir = t.TempDir()
	names := []string{"linux-image-7.2.4-lusoris1_x86_64.deb", "kernel-mainstream.config"}
	var sums strings.Builder
	artifacts := make([]map[string]any, 0, len(names))
	for i, name := range names {
		data := bytes.Repeat([]byte{byte(i + 1)}, 512)
		require.NoError(t, os.WriteFile(filepath.Join(dir, name), data, 0o600))
		fmt.Fprintf(&sums, "%s  %s\n", sha256Hex(data), name)
		artifacts = append(artifacts, map[string]any{"name": name, "sha256": sha256Hex(data), "size": len(data)})
	}
	sumsData := []byte(sums.String())
	require.NoError(t, os.WriteFile(filepath.Join(dir, "SHA256SUMS"), sumsData, 0o600))
	require.NoError(t, os.WriteFile(filepath.Join(dir, "SHA256SUMS.bundle"), []byte("{}"), 0o600))
	doc := map[string]any{
		"schema":    "imago.nucleus.kernel-artifact.v1",
		"provider":  "cordanaLLM/nucleus",
		"stream":    "mainstream",
		"version":   "7.2.4-lusoris1",
		"kernel":    map[string]any{"release": "7.2.4-lusoris1", "config_digest": "sha256:" + strings.Repeat("c", 64)},
		"artifacts": artifacts,
		"checksums": map[string]any{"file": "SHA256SUMS", "sha256": sha256Hex(sumsData)},
		"provenance": map[string]any{
			"repository":      "cordanaLLM/nucleus",
			"tag":             "v7.2.4-lusoris1",
			"revision":        testKernelRevision,
			"bundle":          "SHA256SUMS.bundle",
			"signer_identity": "https://github.com/cordanaLLM/nucleus/.github/workflows/publish-release.yml@refs/tags/v7.2.4-lusoris1",
		},
	}
	raw, err := json.Marshal(doc)
	require.NoError(t, err)
	manifestPath = filepath.Join(t.TempDir(), "kernel-mainstream.manifest.json")
	require.NoError(t, os.WriteFile(manifestPath, raw, 0o600))
	return manifestPath, dir
}

func TestKernelRequirementValidateAegisFixture(t *testing.T) {
	fixture, err := filepath.Abs("../../pkg/kernel/testdata/aegis/kernel-requirement.json")
	require.NoError(t, err)

	out, err := executeCommand("kernel", "requirement", "validate", fixture)
	require.NoError(t, err)
	assert.Contains(t, out, "Kernel requirement aegis-m18-kernel-requirement-0001 is valid")
	assert.Contains(t, out, "Features: 14")
	assert.Contains(t, out, "CONFIG_DEBUG_INFO_BTF")
}

func TestKernelRequirementValidateRepositoryRequirement(t *testing.T) {
	path, err := filepath.Abs("../../kernel/requirement.json")
	require.NoError(t, err)

	out, err := executeCommand("kernel", "requirement", "validate", path)
	require.NoError(t, err)
	assert.Contains(t, out, "imago-kernel-requirement-0001 is valid")
}

func TestKernelRequirementValidateRejectsEmptyFeatures(t *testing.T) {
	path := filepath.Join(t.TempDir(), "empty.json")
	doc := `{"schema":"aegis.p01-nucleus.kernel-requirement.v1","correlation-id":"boundary-0001","architectures":["x86-64"],"abi":{"minimum-release":"6.12"},"features":[]}`
	require.NoError(t, os.WriteFile(path, []byte(doc), 0o600))

	_, err := executeCommand("kernel", "requirement", "validate", path)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "kernel requirement boundary-0001: features: feature list is empty")
}

func TestKernelArtifactVerifyPinnedRelease(t *testing.T) {
	manifestPath, dir := writeKernelRelease(t)
	versions, err := filepath.Abs("../../versions.json")
	require.NoError(t, err)

	out, err := executeCommand("kernel", "artifact", "verify", "--manifest", manifestPath, "--dir", dir,
		"--versions", versions, "--expect-stream", "mainstream", "--expect-version", "7.2.4-lusoris1", "--expect-tag", "v7.2.4-lusoris1")
	require.NoError(t, err)
	assert.Contains(t, out, "Kernel artifact mainstream@7.2.4-lusoris1 verified (2 artifacts)")

	out, err = executeCommand("kernel", "artifact", "verify", "--manifest", manifestPath, "--dir", dir, "--versions", versions, "--json")
	require.NoError(t, err)
	var res map[string]any
	require.NoError(t, json.Unmarshal([]byte(out), &res))
	assert.Equal(t, "mainstream", res["stream"])
	assert.True(t, strings.HasPrefix(res["artifact_digest"].(string), "sha256:"))
	assert.Equal(t, true, res["bundle_present"])
}

func TestKernelArtifactVerifyRejectsTamperedArtifact(t *testing.T) {
	manifestPath, dir := writeKernelRelease(t)
	versions, err := filepath.Abs("../../versions.json")
	require.NoError(t, err)
	tampered := filepath.Join(dir, "linux-image-7.2.4-lusoris1_x86_64.deb")
	require.NoError(t, os.WriteFile(tampered, bytes.Repeat([]byte{0xff}, 512), 0o600))

	_, err = executeCommand("kernel", "artifact", "verify", "--manifest", manifestPath, "--dir", dir, "--versions", versions)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "digest mismatch")

	_, err = executeCommand("kernel", "artifact", "verify", "--manifest", manifestPath, "--dir", dir, "--versions", versions, "--expect-stream", "lts")
	require.Error(t, err)
	assert.Contains(t, err.Error(), `stream: expected "lts"`)

	_, err = executeCommand("kernel", "artifact", "verify", "--dir", dir, "--versions", versions)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "--manifest and --dir are required")
}
