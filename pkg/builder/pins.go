// Copyright 2026 Lusoris
package builder

import (
	"encoding/hex"
	"encoding/json/jsontext"
	"encoding/json/v2"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
)

// Pins contains the toolchain versions and platform-specific QEMU binary digest.
type Pins struct {
	PackerVersion     string
	QemuPluginVersion string
	QemuPluginSHA256  string
}

// LoadPins reads only the build toolchain pins; unrelated manifest keys are allowed.
// Duplicate keys at any depth are refused before decoding.
func LoadPins(path string) (Pins, error) {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return Pins{}, fmt.Errorf("builder: read pins %q: %w", path, err)
	}
	if err := uniqueJSONKeys(data); err != nil {
		return Pins{}, fmt.Errorf("builder: pins %q: %w", path, err)
	}
	var manifest struct {
		Build struct {
			Packer struct {
				Version string `json:"version"`
			} `json:"packer"`
			Plugins map[string]map[string]string `json:"packer_plugins"`
		} `json:"build"`
	}
	if err := json.Unmarshal(data, &manifest); err != nil {
		return Pins{}, fmt.Errorf("builder: decode pins %q: %w", path, err)
	}
	pins := Pins{PackerVersion: manifest.Build.Packer.Version,
		QemuPluginVersion: manifest.Build.Plugins["qemu"]["version"],
		QemuPluginSHA256:  manifest.Build.Plugins["qemu"]["sha256_"+runtime.GOOS+"_"+runtime.GOARCH]}
	if err := pins.validate(); err != nil {
		return Pins{}, fmt.Errorf("builder: pins %q: %w", path, err)
	}
	return pins, nil
}

func (p Pins) validate() error {
	version := regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+$`)
	if !version.MatchString(p.PackerVersion) {
		return fmt.Errorf("build.packer.version missing or invalid: %q", p.PackerVersion)
	}
	if !version.MatchString(p.QemuPluginVersion) {
		return fmt.Errorf("build.packer_plugins.qemu.version missing or invalid: %q", p.QemuPluginVersion)
	}
	digest, err := hex.DecodeString(p.QemuPluginSHA256)
	if err != nil {
		return fmt.Errorf("build.packer_plugins.qemu.sha256_%s_%s: %w", runtime.GOOS, runtime.GOARCH, err)
	}
	if len(digest) != 32 {
		return fmt.Errorf("build.packer_plugins.qemu.sha256_%s_%s missing or invalid", runtime.GOOS, runtime.GOARCH)
	}
	return nil
}

func uniqueJSONKeys(data []byte) error {
	var raw any
	if err := json.Unmarshal(data, &raw); err != nil {
		if serr, ok := errors.AsType[*jsontext.SyntacticError](err); ok && serr.Err == jsontext.ErrDuplicateName {
			return fmt.Errorf("duplicate JSON key %q: %w", serr.JSONPointer.LastToken(), err)
		}
		return fmt.Errorf("invalid JSON document: %w", err)
	}
	return nil
}
