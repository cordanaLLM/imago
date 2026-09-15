// Copyright 2026 Lusoris
package aegis

import (
	"errors"
	"fmt"
)

// Placeholders reported in place of a correlation id that cannot be echoed.
const (
	// MissingCorrelationID is reported when the manifest carries no correlation-id.
	MissingCorrelationID = "(missing)"
	// InvalidCorrelationID is reported when correlation-id is present but is not
	// a valid token, so an unbounded or unprintable value never reaches a log line.
	InvalidCorrelationID = "(invalid)"
)

// Sentinel causes. Every *Error wraps exactly one of them (or an I/O error), so
// callers can classify a rejection with errors.Is without parsing text.
var (
	// ErrInputTooLarge: the manifest exceeds MaxInputBytes.
	ErrInputTooLarge = errors.New("aegis: manifest exceeds the input bound")
	// ErrTrailingContent: bytes other than whitespace follow the manifest.
	ErrTrailingContent = errors.New("aegis: trailing content after the manifest")
	// ErrDecode: the manifest does not decode strictly; the encoding/json error is wrapped.
	ErrDecode = errors.New("aegis: manifest does not decode strictly")
	// ErrSchema: the schema identifier is not the one this package accepts.
	ErrSchema = errors.New("aegis: unsupported schema")
	// ErrMissingField: a required field is absent or empty.
	ErrMissingField = errors.New("aegis: required field missing")
	// ErrInvalidField: a field is present but malformed.
	ErrInvalidField = errors.New("aegis: field is malformed")
	// ErrOutOfBounds: a count, length, or number lies outside its documented bound.
	ErrOutOfBounds = errors.New("aegis: field outside its documented bound")
)

// Error is the correlated rejection every entry point of this package returns.
// Its text reads "aegis product-input <correlation-id>: <field>: <reason>" so a
// refusal can be recorded against the request that caused it.
type Error struct {
	// CorrelationID is the manifest's correlation-id, or one of the placeholders.
	CorrelationID string
	// Field names the rejected manifest field; "input" before decoding succeeds.
	Field string
	// Reason states the violated rule without echoing unbounded input.
	Reason string
	// Err is the cause: a sentinel from this package, optionally wrapping an
	// encoding/json error, or the I/O error that prevented reading.
	Err error
}

// Error implements error.
func (e *Error) Error() string {
	return fmt.Sprintf("aegis product-input %s: %s: %s", e.CorrelationID, e.Field, e.Reason)
}

// Unwrap exposes the cause to errors.Is and errors.As.
func (e *Error) Unwrap() error { return e.Err }

// reportedCorrelationID maps a raw correlation-id to the value an Error reports.
func reportedCorrelationID(raw string) string {
	switch {
	case raw == "":
		return MissingCorrelationID
	case !isToken(raw, MaxCorrelationIDLen, "._-"):
		return InvalidCorrelationID
	default:
		return raw
	}
}
