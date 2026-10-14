// Copyright 2026 Lusoris
// Package kernel implements the two halves of the kernel contract between
// imago and cordanaLLM/nucleus: the Aegis kernel-requirement payload imago
// sends upstream (aegis.p01-nucleus.kernel-requirement.v1) and the kernel
// artifact manifest nucleus publishes with every release
// (imago.nucleus.kernel-artifact.v1), which is verified digest by digest
// before an image build consumes the artifact.
package kernel

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"

	"github.com/cordanaLLM/imago/pkg/reason"
)

// ErrTooLarge is returned when a document or artifact exceeds its read bound.
var ErrTooLarge = errors.New("exceeds read bound")

// Placeholders reported in place of a correlation value that cannot be echoed.
const (
	missingValue = "(missing)"
	invalidValue = "(invalid)"
)

// reported maps a raw correlation value to the text an error may repeat: a
// value that failed its own check is not echoed (ADR-0028).
func reported(raw string, valid bool) string {
	switch {
	case raw == "":
		return missingValue
	case !valid:
		return invalidValue
	}
	return raw
}

// boundedError reports text cut by reason.Bound and keeps the full cause in
// the chain for errors.Is and errors.As.
type boundedError struct {
	text string
	err  error
}

func (e *boundedError) Error() string { return e.text }

func (e *boundedError) Unwrap() error { return e.err }

// bounded returns err with its text at most reason.MaxLen bytes. Every error an
// exported function of this package returns passes through it (ADR-0028).
func bounded(err error) error {
	return &boundedError{text: reason.Bound(err.Error()), err: err}
}

// decodeStrict decodes exactly one JSON document of at most limit bytes into v.
// Unknown fields, trailing data, and oversized input are rejected.
func decodeStrict(r io.Reader, limit int64, v any) error {
	lr := &io.LimitedReader{R: r, N: limit + 1}
	dec := json.NewDecoder(lr)
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		if lr.N <= 0 {
			return fmt.Errorf("document %w of %d bytes", ErrTooLarge, limit)
		}
		return fmt.Errorf("decode: %w", err)
	}
	if lr.N <= 0 {
		return fmt.Errorf("document %w of %d bytes", ErrTooLarge, limit)
	}
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		return errors.New("decode: trailing data after document")
	}
	return nil
}

// boundedToken reports whether s is non-empty, at most max bytes, and matches re.
func boundedToken(s string, max int, re *regexp.Regexp) bool {
	return s != "" && len(s) <= max && re.MatchString(s)
}

// digestFile returns the lowercase hex SHA-256 of a file, reading at most
// limit bytes; a larger file is reported as ErrTooLarge, never truncated.
func digestFile(path string, limit int64) (string, int64, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(h, io.LimitReader(f, limit+1))
	if err != nil {
		return "", n, fmt.Errorf("read %s: %w", path, err)
	}
	if n > limit {
		return "", n, fmt.Errorf("%s %w of %d bytes", filepath.Base(path), ErrTooLarge, limit)
	}
	return hex.EncodeToString(h.Sum(nil)), n, nil
}
