// Copyright 2026 Lusoris
// Package reason bounds the text of a rejection. Decoder and I/O errors repeat
// caller-controlled text, such as an unknown field name or a path, at any
// length; every contract parser in this repository passes the text it reports
// through Bound so that no input can make a log line or a CLI message
// arbitrarily long (ADR-0028).
package reason

import "strings"

// MaxLen bounds a reported reason in bytes.
const MaxLen = 256

// TruncatedMark ends a reason that Bound cut.
const TruncatedMark = " (truncated)"

// Bound returns text cut to MaxLen bytes, ending in TruncatedMark when it was
// cut. A cut inside a multi-byte character drops the partial character.
func Bound(text string) string {
	if len(text) <= MaxLen {
		return text
	}
	return strings.ToValidUTF8(text[:MaxLen-len(TruncatedMark)], "") + TruncatedMark
}
