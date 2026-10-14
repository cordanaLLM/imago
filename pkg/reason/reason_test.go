// Copyright 2026 Lusoris
package reason_test

import (
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/stretchr/testify/assert"

	"github.com/cordanaLLM/imago/pkg/reason"
)

func TestBoundKeepsShortText(t *testing.T) {
	assert.Equal(t, "", reason.Bound(""))
	assert.Equal(t, "short", reason.Bound("short"))
}

func TestBoundaryExactlyMaxLen(t *testing.T) {
	text := strings.Repeat("a", reason.MaxLen)
	assert.Equal(t, text, reason.Bound(text))
}

func TestBoundaryOneAboveMaxLen(t *testing.T) {
	got := reason.Bound(strings.Repeat("a", reason.MaxLen+1))
	assert.Len(t, got, reason.MaxLen)
	assert.True(t, strings.HasSuffix(got, reason.TruncatedMark), got)
}

func TestNegativeCutInsideMultiByteCharacter(t *testing.T) {
	got := reason.Bound("a" + strings.Repeat("é", 4000))
	assert.LessOrEqual(t, len(got), reason.MaxLen)
	assert.True(t, utf8.ValidString(got), "bounded text is not valid UTF-8")
	assert.True(t, strings.HasSuffix(got, reason.TruncatedMark), got)
}
