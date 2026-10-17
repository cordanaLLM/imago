// Copyright 2026 Lusoris
// Package kernel implements the two halves of the kernel contract between
// imago and cordanaLLM/nucleus: the Aegis kernel-requirement payload imago
// sends upstream (aegis.p01-nucleus.kernel-requirement.v1) and the kernel
// artifact manifest nucleus publishes with every release
// (imago.nucleus.kernel-artifact.v1), which is verified digest by digest
// before an image build consumes the artifact.
package kernel

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json/jsontext"
	"encoding/json/v2"
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
// Unknown members, member names that differ only in case, duplicate members,
// trailing data, and oversized input are rejected, as the schema owner's
// decoder rejects them (ADR-0030).
func decodeStrict(r io.Reader, limit int64, v any) error {
	data, err := io.ReadAll(io.LimitReader(r, limit+1))
	if err != nil {
		return fmt.Errorf("read: %w", err)
	}
	if int64(len(data)) > limit {
		return fmt.Errorf("document %w of %d bytes", ErrTooLarge, limit)
	}
	dec := jsontext.NewDecoder(bytes.NewReader(data))
	if err := json.UnmarshalDecode(dec, v, json.RejectUnknownMembers(true)); err != nil {
		return fmt.Errorf("decode: %w", decodeError(err))
	}
	if _, err := dec.ReadToken(); !errors.Is(err, io.EOF) {
		return errors.New("decode: trailing data after document")
	}
	return nil
}

// decodeError reports an unknown or duplicate member by its name alone, in the
// text the package reported before ADR-0030, and keeps the cause in the chain.
// The caller bounds the text.
func decodeError(err error) error {
	if serr, ok := errors.AsType[*json.SemanticError](err); ok && serr.Err == json.ErrUnknownName {
		return &boundedError{text: fmt.Sprintf("json: unknown field %q", serr.JSONPointer.LastToken()), err: err}
	}
	if serr, ok := errors.AsType[*jsontext.SyntacticError](err); ok && serr.Err == jsontext.ErrDuplicateName {
		return &boundedError{text: fmt.Sprintf("json: duplicate field %q", serr.JSONPointer.LastToken()), err: err}
	}
	return err
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
