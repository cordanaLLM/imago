// Copyright 2026 Lusoris
// Package aegis is the acceptance boundary for the Aegis product-input manifest
// (schema aegis.p01.product-input.v1, cordanaLLM/Aegis-OS build/product-input.json).
// It decodes the manifest strictly, validates every field against documented
// bounds, and maps it to an imago-side build request. Every rejection is an
// *Error carrying the manifest's correlation identifier.
//
// The package stops at acceptance. Binding the accepted request to an executor
// (mkosi/UKI image synthesis) is the next planning step; the Packer flavor
// dispatcher in pkg/builder is not the target of this contract (ADR-0020).
package aegis

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// Schema is the only product-input schema identifier this package accepts.
const Schema = "aegis.p01.product-input.v1"

// Documented bounds. Each one is a contract constant recorded in ADR-0020.
const (
	// MaxInputBytes bounds the manifest size read by Decode, Parse, and Load (1 MiB).
	MaxInputBytes = 1 << 20
	// MaxRetryAttempts is the inclusive upper bound of retries.max-attempts.
	MaxRetryAttempts = 10
	// MaxBackoffSeconds is the inclusive upper bound of retries.backoff-seconds (one hour).
	MaxBackoffSeconds = 3600
	// MaxPackages is the inclusive upper bound of the packages list length.
	MaxPackages = 256
	// MaxCorrelationIDLen bounds correlation-id.
	MaxCorrelationIDLen = 128
	// MaxPathLen bounds each definitions path.
	MaxPathLen = 256
	// MaxTokenLen bounds distribution, snapshot, package, and kernel tokens.
	MaxTokenLen = 128
	// RevisionLen is the exact length of the lowercase hex git revision.
	RevisionLen = 40
)

// ProductInput mirrors build/product-input.json field for field. JSON keys are
// the hyphenated Aegis wire names; unknown keys are rejected at decode time.
type ProductInput struct {
	Schema        string       `json:"schema"`
	CorrelationID string       `json:"correlation-id"`
	Revision      string       `json:"revision"`
	Distribution  Distribution `json:"distribution"`
	Definitions   Definitions  `json:"definitions"`
	Packages      []string     `json:"packages"`
	Kernel        Kernel       `json:"kernel"`
	Retries       Retries      `json:"retries"`
}

// Distribution pins the base distribution and its archive snapshot (Aegis D18).
type Distribution struct {
	ID       string `json:"id"`
	Snapshot string `json:"snapshot"`
}

// Definitions references the four reviewed configuration inputs, as paths
// relative to the Aegis repository root.
type Definitions struct {
	Repart            string `json:"repart"`
	Sysupdate         string `json:"sysupdate"`
	Mkosi             string `json:"mkosi"`
	KernelRequirement string `json:"kernel-requirement"`
}

// Kernel identifies the boot kernel (Aegis D07).
type Kernel struct {
	Source         string `json:"source"`
	DefaultPackage string `json:"default-package"`
}

// Retries bounds how often and how fast a producer may retry the request.
type Retries struct {
	MaxAttempts    int `json:"max-attempts"`
	BackoffSeconds int `json:"backoff-seconds"`
}

// Load opens a manifest file and returns the validated product input. The read
// is bounded by MaxInputBytes.
func Load(path string) (*ProductInput, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, &Error{CorrelationID: MissingCorrelationID, Field: "input", Reason: "open manifest: " + err.Error(), Err: err}
	}
	p, err := Decode(f)
	cerr := f.Close()
	if err != nil {
		return nil, err
	}
	if cerr != nil {
		return nil, &Error{CorrelationID: p.CorrelationID, Field: "input", Reason: "close manifest: " + cerr.Error(), Err: cerr}
	}
	return p, nil
}

// Decode reads at most MaxInputBytes from r and parses one manifest. A stream
// longer than the bound is refused with ErrInputTooLarge before parsing.
func Decode(r io.Reader) (*ProductInput, error) {
	data, err := io.ReadAll(io.LimitReader(r, MaxInputBytes+1))
	if err != nil {
		return nil, &Error{CorrelationID: MissingCorrelationID, Field: "input", Reason: "read manifest: " + err.Error(), Err: err}
	}
	return Parse(data)
}

// Parse strictly decodes and validates one manifest held in memory: unknown
// fields, trailing content, and inputs above MaxInputBytes are rejected.
func Parse(data []byte) (*ProductInput, error) {
	if len(data) > MaxInputBytes {
		return nil, &Error{
			CorrelationID: MissingCorrelationID, Field: "input",
			Reason: fmt.Sprintf("exceeds %d bytes", MaxInputBytes), Err: ErrInputTooLarge,
		}
	}
	cid := probeCorrelationID(data)
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var p ProductInput
	if err := dec.Decode(&p); err != nil {
		return nil, &Error{CorrelationID: cid, Field: "input", Reason: "strict decode: " + err.Error(), Err: fmt.Errorf("%w: %w", ErrDecode, err)}
	}
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		return nil, &Error{CorrelationID: cid, Field: "input", Reason: "trailing content after the manifest", Err: ErrTrailingContent}
	}
	if err := p.Validate(); err != nil {
		return nil, err
	}
	return &p, nil
}

// probeCorrelationID leniently extracts correlation-id from the first JSON
// value so a strict-decode or trailing-content failure can still be correlated
// regardless of key order. It never fails: an unreadable or absent id yields
// the missing placeholder.
func probeCorrelationID(data []byte) string {
	var probe struct {
		CorrelationID string `json:"correlation-id"`
	}
	if err := json.NewDecoder(bytes.NewReader(data)).Decode(&probe); err != nil {
		return MissingCorrelationID
	}
	return reportedCorrelationID(probe.CorrelationID)
}
