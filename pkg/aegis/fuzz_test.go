// Copyright 2026 Lusoris
package aegis_test

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"reflect"
	"strings"
	"testing"

	"github.com/cordanaLLM/imago/pkg/aegis"
)

// FuzzParse feeds arbitrary bytes to the acceptance boundary. The seed corpus
// is the vendored Aegis manifest plus one input per early rejection path; the
// seeds run as ordinary cases in every `go test`.
func FuzzParse(f *testing.F) {
	valid, err := os.ReadFile(fixturePath)
	if err != nil {
		f.Fatal(err)
	}
	f.Add(valid)
	f.Add(append(bytes.Clone(valid), " {}"...))
	f.Add([]byte(`{"correlation-id":"fuzz-seed-0001","unknown":1}`))
	f.Add([]byte(`{"correlation-id":"not a token"}`))
	f.Add([]byte(`{"correlation-id":"` + strings.Repeat("x", aegis.MaxCorrelationIDLen+1) + `"}`))
	f.Add([]byte(`{"correlation-id":"fuzz-seed-0002","` + strings.Repeat("u", 2*aegis.MaxReasonLen) + `":1}`))
	f.Add([]byte(`{"schema":`))
	f.Add([]byte(`[]`))
	f.Add([]byte{})
	f.Fuzz(func(t *testing.T, data []byte) {
		p, err := aegis.Parse(data)
		if err != nil {
			checkRejection(t, p, err)
			return
		}
		checkAcceptance(t, data, p)
	})
}

// checkRejection holds the documented shape of a refusal: no value, an *Error,
// a correlation id that is a bounded token or one of the two placeholders, and
// a reason no longer than MaxReasonLen.
func checkRejection(t *testing.T, p *aegis.ProductInput, err error) {
	t.Helper()
	if p != nil {
		t.Fatalf("a rejected manifest returned a value: %+v", p)
	}
	var aerr *aegis.Error
	if !errors.As(err, &aerr) {
		t.Fatalf("rejection is %T, not *aegis.Error: %v", err, err)
	}
	if aerr.Field == "" || aerr.Err == nil {
		t.Fatalf("rejection names no field or no cause: %+v", aerr)
	}
	if len(aerr.CorrelationID) > aegis.MaxCorrelationIDLen {
		t.Fatalf("rejection echoes a correlation id of %d bytes", len(aerr.CorrelationID))
	}
	if len(aerr.Reason) > aegis.MaxReasonLen {
		t.Fatalf("rejection reason is %d bytes, bound %d", len(aerr.Reason), aegis.MaxReasonLen)
	}
}

// checkAcceptance holds what an accepted manifest guarantees: it validates, the
// reader entry point agrees, it maps to a build request, and its own encoding
// is accepted again as the same value.
func checkAcceptance(t *testing.T, data []byte, p *aegis.ProductInput) {
	t.Helper()
	if err := p.Validate(); err != nil {
		t.Fatalf("Parse accepted a manifest that Validate rejects: %v", err)
	}
	decoded, err := aegis.Decode(bytes.NewReader(data))
	if err != nil || !reflect.DeepEqual(p, decoded) {
		t.Fatalf("Decode disagrees with Parse: %v", err)
	}
	req, err := p.BuildRequest()
	if err != nil || req.CorrelationID != p.CorrelationID {
		t.Fatalf("an accepted manifest does not map to its build request: %v", err)
	}
	encoded, err := json.Marshal(p)
	if err != nil {
		t.Fatalf("an accepted manifest does not encode: %v", err)
	}
	again, err := aegis.Parse(encoded)
	if err != nil {
		t.Fatalf("the encoding of an accepted manifest is rejected: %v", err)
	}
	if !reflect.DeepEqual(p, again) {
		t.Fatalf("round trip changed the manifest:\n first %+v\nsecond %+v", p, again)
	}
}
