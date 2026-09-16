// Copyright 2026 Lusoris
package aegis_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/aegis"
)

const (
	fixturePath = "testdata/product-input.json"
	fixtureCID  = "aegis-m18-product-input-0001"
	fixtureRev  = "61f2fe16bab7889e007b2fd1474b025023906e91"
)

// fixture returns the vendored Aegis manifest as a mutable JSON object.
func fixture(t *testing.T) map[string]any {
	t.Helper()
	data, err := os.ReadFile(fixturePath)
	require.NoError(t, err)
	var m map[string]any
	require.NoError(t, json.Unmarshal(data, &m))
	return m
}

// nested returns the named object inside a fixture map.
func nested(t *testing.T, m map[string]any, key string) map[string]any {
	t.Helper()
	obj, ok := m[key].(map[string]any)
	require.True(t, ok, "fixture key %q is not an object", key)
	return obj
}

// parse marshals a JSON object and runs it through the strict parser.
func parse(t *testing.T, m map[string]any) (*aegis.ProductInput, error) {
	t.Helper()
	data, err := json.Marshal(m)
	require.NoError(t, err)
	return aegis.Parse(data)
}

// requireRejected asserts a correlated *Error with the expected id, field, cause, and text.
func requireRejected(t *testing.T, err error, cid, field string, cause error) {
	t.Helper()
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, cid, aerr.CorrelationID)
	assert.Equal(t, field, aerr.Field)
	assert.ErrorIs(t, err, cause)
	assert.True(t, strings.HasPrefix(err.Error(), "aegis product-input "+cid+": "+field+": "), err.Error())
}

// padded returns the fixture followed by spaces up to n bytes.
func padded(t *testing.T, n int) []byte {
	t.Helper()
	data, err := os.ReadFile(fixturePath)
	require.NoError(t, err)
	require.LessOrEqual(t, len(data), n)
	return append(data, bytes.Repeat([]byte(" "), n-len(data))...)
}

func TestPositiveFixtureAcceptedAndMapped(t *testing.T) {
	p, err := aegis.Load(fixturePath)
	require.NoError(t, err)
	assert.Equal(t, aegis.Schema, p.Schema)
	assert.Equal(t, fixtureCID, p.CorrelationID)
	assert.Equal(t, fixtureRev, p.Revision)
	assert.Equal(t, aegis.Distribution{ID: "arch", Snapshot: "2026/09/13"}, p.Distribution)
	assert.Equal(t, []string{"linux-rt", "systemd", "systemd-ukify"}, p.Packages)
	assert.Equal(t, aegis.Kernel{Source: "built-here", DefaultPackage: "linux-rt"}, p.Kernel)

	req, err := p.BuildRequest()
	require.NoError(t, err)
	assert.Equal(t, fixtureCID, req.CorrelationID)
	assert.Equal(t, fixtureRev, req.Revision)
	assert.Equal(t, "build/repart.d", req.Definitions.Repart)
	assert.Equal(t, "build/sysupdate.d", req.Definitions.Sysupdate)
	assert.Equal(t, "build/mkosi.conf", req.Definitions.Mkosi)
	assert.Equal(t, "build/kernel-requirement.json", req.Definitions.KernelRequirement)
	assert.Equal(t, "built-here", req.KernelSource)
	assert.Equal(t, "linux-rt", req.KernelPackage)
	assert.Equal(t, aegis.RetryPolicy{Attempts: 3, Backoff: 30 * time.Second}, req.Retry)

	req.Packages[0] = "mutated"
	assert.Equal(t, "linux-rt", p.Packages[0], "the request must not alias the manifest")
}

func TestPositiveBuildRequestJSON(t *testing.T) {
	p, err := aegis.Load(fixturePath)
	require.NoError(t, err)
	req, err := p.BuildRequest()
	require.NoError(t, err)
	out, err := json.Marshal(req)
	require.NoError(t, err)
	assert.Contains(t, string(out), `"correlation_id":"`+fixtureCID+`"`)
	assert.Contains(t, string(out), `"kernel_requirement":"build/kernel-requirement.json"`)
	assert.Contains(t, string(out), `"retry":{"attempts":3,"backoff":"30s"}`)
}

func TestPositiveDecodeToleratesTrailingWhitespace(t *testing.T) {
	data, err := os.ReadFile(fixturePath)
	require.NoError(t, err)
	p, err := aegis.Decode(bytes.NewReader(append(data, "\n\n  \t"...)))
	require.NoError(t, err)
	assert.Equal(t, fixtureCID, p.CorrelationID)
}

func TestNegativeMissingCorrelationID(t *testing.T) {
	m := fixture(t)
	delete(m, "correlation-id")
	_, err := parse(t, m)
	requireRejected(t, err, aegis.MissingCorrelationID, "correlation-id", aegis.ErrMissingField)
	assert.Equal(t, "aegis product-input (missing): correlation-id: required", err.Error())
}

func TestNegativeInvalidCorrelationIDIsNotEchoed(t *testing.T) {
	m := fixture(t)
	m["correlation-id"] = "aegis m18\x1b[31m"
	_, err := parse(t, m)
	requireRejected(t, err, aegis.InvalidCorrelationID, "correlation-id", aegis.ErrInvalidField)
	assert.NotContains(t, err.Error(), "\x1b")
}

func TestNegativeUnknownField(t *testing.T) {
	m := fixture(t)
	m["extra"] = true
	_, err := parse(t, m)
	requireRejected(t, err, fixtureCID, "input", aegis.ErrDecode)
	assert.Contains(t, err.Error(), `unknown field "extra"`)

	m = fixture(t)
	nested(t, m, "retries")["jitter-seconds"] = 1
	_, err = parse(t, m)
	requireRejected(t, err, fixtureCID, "input", aegis.ErrDecode)
	assert.Contains(t, err.Error(), `unknown field "jitter-seconds"`)
}

func TestNegativeMalformedJSON(t *testing.T) {
	_, err := aegis.Parse([]byte(`{"schema": "aegis.p01.product-input.v1", "correlation-id": }`))
	requireRejected(t, err, aegis.MissingCorrelationID, "input", aegis.ErrDecode)
	var syntax *json.SyntaxError
	assert.ErrorAs(t, err, &syntax, "the encoding/json error stays reachable")

	_, err = aegis.Parse([]byte(`{"schema": "aegis.p01.product-input.v1", "correlation-id": `))
	requireRejected(t, err, aegis.MissingCorrelationID, "input", aegis.ErrDecode)
	assert.ErrorIs(t, err, io.ErrUnexpectedEOF, "a truncated manifest is reported as such")
}

func TestNegativeTrailingContent(t *testing.T) {
	data, err := os.ReadFile(fixturePath)
	require.NoError(t, err)
	for name, tail := range map[string]string{"object": "{}", "garbage": "xyz", "scalar": " 1"} {
		t.Run(name, func(t *testing.T) {
			_, err := aegis.Parse(append(append([]byte(nil), data...), tail...))
			requireRejected(t, err, fixtureCID, "input", aegis.ErrTrailingContent)
		})
	}
}

func TestNegativeWrongSchema(t *testing.T) {
	m := fixture(t)
	m["schema"] = "aegis.p01.product-input.v2"
	_, err := parse(t, m)
	requireRejected(t, err, fixtureCID, "schema", aegis.ErrSchema)
}

func TestNegativeRevisionNotLowercaseHex(t *testing.T) {
	cases := map[string]string{
		"uppercase": strings.ToUpper(fixtureRev),
		"short":     fixtureRev[:39],
		"long":      fixtureRev + "0",
		"non-hex":   fixtureRev[:39] + "g",
		"empty":     "",
	}
	for name, rev := range cases {
		t.Run(name, func(t *testing.T) {
			m := fixture(t)
			m["revision"] = rev
			_, err := parse(t, m)
			requireRejected(t, err, fixtureCID, "revision", aegis.ErrInvalidField)
		})
	}
}

func TestNegativeDefaultPackageNotInPackages(t *testing.T) {
	m := fixture(t)
	nested(t, m, "kernel")["default-package"] = "linux-zen"
	_, err := parse(t, m)
	requireRejected(t, err, fixtureCID, "kernel.default-package", aegis.ErrInvalidField)
	assert.Contains(t, err.Error(), "must be one of packages")
}

func TestNegativeDuplicatePackage(t *testing.T) {
	m := fixture(t)
	m["packages"] = []any{"linux-rt", "systemd", "linux-rt"}
	_, err := parse(t, m)
	requireRejected(t, err, fixtureCID, "packages[2]", aegis.ErrInvalidField)
}

func TestNegativeDefinitionPaths(t *testing.T) {
	cases := map[string]struct {
		path  string
		cause error
	}{
		"parent segment":    {"build/../etc/repart.d", aegis.ErrInvalidField},
		"leading parent":    {"../repart.d", aegis.ErrInvalidField},
		"absolute":          {"/build/repart.d", aegis.ErrInvalidField},
		"backslash":         {`build\repart.d`, aegis.ErrInvalidField},
		"control character": {"build/re\x00part.d", aegis.ErrInvalidField},
		"empty segment":     {"build//repart.d", aegis.ErrInvalidField},
		"empty":             {"", aegis.ErrMissingField},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			m := fixture(t)
			nested(t, m, "definitions")["repart"] = tc.path
			_, err := parse(t, m)
			requireRejected(t, err, fixtureCID, "definitions.repart", tc.cause)
		})
	}
}

func TestNegativeMissingFile(t *testing.T) {
	_, err := aegis.Load("testdata/does-not-exist.json")
	requireRejected(t, err, aegis.MissingCorrelationID, "input", fs.ErrNotExist)
}

func TestBoundaryRetries(t *testing.T) {
	cases := []struct {
		name  string
		field string
		value int
		ok    bool
	}{
		{"attempts at bound", "max-attempts", aegis.MaxRetryAttempts, true},
		{"attempts above bound", "max-attempts", aegis.MaxRetryAttempts + 1, false},
		{"attempts minimum", "max-attempts", 1, true},
		{"attempts zero", "max-attempts", 0, false},
		{"backoff at bound", "backoff-seconds", aegis.MaxBackoffSeconds, true},
		{"backoff above bound", "backoff-seconds", aegis.MaxBackoffSeconds + 1, false},
		{"backoff zero", "backoff-seconds", 0, true},
		{"backoff negative", "backoff-seconds", -1, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			m := fixture(t)
			nested(t, m, "retries")[tc.field] = tc.value
			_, err := parse(t, m)
			if tc.ok {
				require.NoError(t, err)
				return
			}
			requireRejected(t, err, fixtureCID, "retries."+tc.field, aegis.ErrOutOfBounds)
		})
	}
}

func TestBoundaryPackageCount(t *testing.T) {
	for _, tc := range []struct {
		n  int
		ok bool
	}{{aegis.MaxPackages, true}, {aegis.MaxPackages + 1, false}} {
		t.Run(fmt.Sprintf("%d packages", tc.n), func(t *testing.T) {
			pkgs := make([]any, 0, tc.n)
			pkgs = append(pkgs, "linux-rt")
			for i := 1; i < tc.n; i++ {
				pkgs = append(pkgs, fmt.Sprintf("pkg-%03d", i))
			}
			m := fixture(t)
			m["packages"] = pkgs
			_, err := parse(t, m)
			if tc.ok {
				require.NoError(t, err)
				return
			}
			requireRejected(t, err, fixtureCID, "packages", aegis.ErrOutOfBounds)
		})
	}
}

func TestBoundaryInputSize(t *testing.T) {
	_, err := aegis.Decode(bytes.NewReader(padded(t, aegis.MaxInputBytes)))
	require.NoError(t, err, "a manifest exactly at the bound is accepted")

	_, err = aegis.Decode(bytes.NewReader(padded(t, aegis.MaxInputBytes+1)))
	requireRejected(t, err, aegis.MissingCorrelationID, "input", aegis.ErrInputTooLarge)

	_, err = aegis.Parse(padded(t, aegis.MaxInputBytes+1))
	requireRejected(t, err, aegis.MissingCorrelationID, "input", aegis.ErrInputTooLarge)
}

func TestBoundaryStringLengths(t *testing.T) {
	cases := []struct {
		name  string
		set   func(m map[string]any, s string)
		fill  string
		limit int
		cause error
	}{
		{"correlation-id", func(m map[string]any, s string) { m["correlation-id"] = s }, "c", aegis.MaxCorrelationIDLen, aegis.ErrInvalidField},
		{"definitions.mkosi", func(m map[string]any, s string) { nested(t, m, "definitions")["mkosi"] = s }, "m", aegis.MaxPathLen, aegis.ErrOutOfBounds},
		{"distribution.id", func(m map[string]any, s string) { nested(t, m, "distribution")["id"] = s }, "d", aegis.MaxTokenLen, aegis.ErrInvalidField},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			m := fixture(t)
			tc.set(m, strings.Repeat(tc.fill, tc.limit))
			_, err := parse(t, m)
			require.NoError(t, err, "value at the bound is accepted")

			m = fixture(t)
			tc.set(m, strings.Repeat(tc.fill, tc.limit+1))
			_, err = parse(t, m)
			require.Error(t, err, "value above the bound is refused")
			var aerr *aegis.Error
			require.ErrorAs(t, err, &aerr)
			assert.Equal(t, tc.name, aerr.Field)
			assert.ErrorIs(t, err, tc.cause)
		})
	}
}

func validResult() aegis.Result {
	return aegis.Result{
		Schema:          aegis.ResultSchema,
		CorrelationID:   fixtureCID,
		ImageDigest:     aegis.DigestPrefix + strings.Repeat("ab", 32),
		SignatureRef:    "sigstore://rekor.example.com/entries/0001",
		BootEvidenceRef: "evidence/boot/aegis-m18-product-input-0001.json",
	}
}

func TestPositiveResultValid(t *testing.T) {
	r := validResult()
	require.NoError(t, r.Validate())
}

func TestNegativeResult(t *testing.T) {
	cases := map[string]struct {
		mutate func(r *aegis.Result)
		cid    string
		field  string
		cause  error
	}{
		"wrong schema":          {func(r *aegis.Result) { r.Schema = aegis.Schema }, fixtureCID, "schema", aegis.ErrSchema},
		"missing correlation":   {func(r *aegis.Result) { r.CorrelationID = "" }, aegis.MissingCorrelationID, "correlation-id", aegis.ErrMissingField},
		"invalid correlation":   {func(r *aegis.Result) { r.CorrelationID = "has space" }, aegis.InvalidCorrelationID, "correlation-id", aegis.ErrInvalidField},
		"digest uppercase":      {func(r *aegis.Result) { r.ImageDigest = aegis.DigestPrefix + strings.Repeat("AB", 32) }, fixtureCID, "image-digest", aegis.ErrInvalidField},
		"digest wrong prefix":   {func(r *aegis.Result) { r.ImageDigest = "sha512:" + strings.Repeat("ab", 32) }, fixtureCID, "image-digest", aegis.ErrInvalidField},
		"digest short":          {func(r *aegis.Result) { r.ImageDigest = aegis.DigestPrefix + strings.Repeat("ab", 31) }, fixtureCID, "image-digest", aegis.ErrInvalidField},
		"missing signature":     {func(r *aegis.Result) { r.SignatureRef = "" }, fixtureCID, "signature-ref", aegis.ErrMissingField},
		"evidence control byte": {func(r *aegis.Result) { r.BootEvidenceRef = "evidence\n.json" }, fixtureCID, "boot-evidence-ref", aegis.ErrInvalidField},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			r := validResult()
			tc.mutate(&r)
			requireRejected(t, r.Validate(), tc.cid, tc.field, tc.cause)
		})
	}
}

func TestBoundaryResultReferenceLength(t *testing.T) {
	r := validResult()
	r.SignatureRef = strings.Repeat("s", aegis.MaxReferenceLen)
	require.NoError(t, r.Validate())

	r.SignatureRef = strings.Repeat("s", aegis.MaxReferenceLen+1)
	requireRejected(t, r.Validate(), fixtureCID, "signature-ref", aegis.ErrOutOfBounds)
}
