// Copyright 2026 Lusoris
package builder

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
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
// Duplicate keys at any depth are refused before decoding (encoding/json otherwise
// silently keeps the last value). The iterative token walk avoids recursive descent.
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

type jsonFrame struct {
	keys    map[string]bool
	wantKey bool
}

func uniqueJSONKeys(data []byte) error {
	if !json.Valid(data) {
		return fmt.Errorf("invalid JSON document")
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	var stack []jsonFrame
	// Each token consumes at least one input byte; EOF ends the walk earlier.
	for i := 0; i <= len(data); i++ {
		token, err := dec.Token()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return fmt.Errorf("read JSON token: %w", err)
		}
		if err := consumeJSONToken(&stack, token); err != nil {
			return err
		}
	}
	return fmt.Errorf("JSON token limit exceeded")
}

func consumeJSONToken(stack *[]jsonFrame, token json.Token) error {
	if delim, ok := token.(json.Delim); ok && (delim == '}' || delim == ']') {
		*stack = (*stack)[:len(*stack)-1]
		return nil
	}
	if err := acceptJSONToken(*stack, token); err != nil {
		return err
	}
	if delim, ok := token.(json.Delim); ok {
		frame := jsonFrame{}
		if delim == '{' {
			frame.keys = make(map[string]bool)
			frame.wantKey = true
		}
		*stack = append(*stack, frame)
	}
	return nil
}

func acceptJSONToken(stack []jsonFrame, token json.Token) error {
	if len(stack) == 0 {
		return nil
	}
	frame := &stack[len(stack)-1]
	if frame.keys == nil {
		return nil
	}
	if frame.wantKey {
		key, ok := token.(string)
		if !ok {
			return fmt.Errorf("invalid JSON object key")
		}
		if frame.keys[key] {
			return fmt.Errorf("duplicate JSON key %q", key)
		}
		frame.keys[key] = true
	}
	frame.wantKey = !frame.wantKey
	return nil
}
