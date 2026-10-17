// Copyright 2026 Lusoris
package aegis_test

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"testing/iotest"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/aegis"
)

// TestNegativeSignatureRef holds every rule of the signature-ref form with the
// reason of the rule that refuses the value, so removing one rule turns its
// cases red even where another rule would still refuse them.
func TestNegativeSignatureRef(t *testing.T) {
	const (
		scheme  = "must start with https://"
		noPath  = "must contain a path starting with /"
		hostLen = "host must be 1..253 characters"
		hostEnd = "host must begin and end with an alphanumeric character"
		hostSet = "host contains invalid characters"
		pathSet = "path contains invalid characters"
		empty   = "path contains empty segments"
		dots    = "path contains dot segments"
		name    = "last path segment must be SHA256SUMS.bundle"
	)
	cases := map[string]struct{ ref, reason string }{
		"http scheme":                  {"http://github.com/x/SHA256SUMS.bundle", scheme},
		"HTTPS upper case":             {"HTTPS://github.com/x/SHA256SUMS.bundle", scheme},
		"sigstore scheme":              {"sigstore://rekor.example.com/entries/0001", scheme},
		"leading space":                {" https://github.com/x/SHA256SUMS.bundle", scheme},
		"user part":                    {"https://user@github.com/x/SHA256SUMS.bundle", hostSet},
		"port":                         {"https://github.com:443/x/SHA256SUMS.bundle", hostSet},
		"underscore in host":           {"https://git_hub.com/x/SHA256SUMS.bundle", hostSet},
		"empty host":                   {"https:///x/SHA256SUMS.bundle", hostLen},
		"host starting with hyphen":    {"https://-github.com/x/SHA256SUMS.bundle", hostEnd},
		"host ending with dot":         {"https://github.com./x/SHA256SUMS.bundle", hostEnd},
		"query":                        {"https://github.com/x/SHA256SUMS.bundle?x=1", pathSet},
		"fragment":                     {"https://github.com/x/SHA256SUMS.bundle#a", pathSet},
		"percent":                      {"https://github.com/x/SHA256SUMS%2Ebundle", pathSet},
		"space in path":                {"https://github.com/x y/SHA256SUMS.bundle", pathSet},
		"empty segment":                {"https://github.com//SHA256SUMS.bundle", empty},
		"trailing slash":               {"https://github.com/x/SHA256SUMS.bundle/", empty},
		"parent segment":               {"https://github.com/a/../SHA256SUMS.bundle", dots},
		"current segment":              {"https://github.com/a/./SHA256SUMS.bundle", dots},
		"other name":                   {"https://github.com/x/SHA256SUMS", name},
		"suffix":                       {"https://github.com/x/SHA256SUMS.bundle.txt", name},
		"other case":                   {"https://github.com/x/sha256sums.bundle", name},
		"no path":                      {"https://github.com", noPath},
		"name without slash before it": {"https://github.comSHA256SUMS.bundle", noPath},
	}
	for label, tc := range cases {
		t.Run(label, func(t *testing.T) {
			r := validResult()
			r.SignatureRef = tc.ref
			err := r.Validate()
			requireRejected(t, err, fixtureCID, "signature-ref", aegis.ErrInvalidField)
			var aerr *aegis.Error
			require.ErrorAs(t, err, &aerr)
			assert.Equal(t, tc.reason, aerr.Reason)
			assert.NotContains(t, aerr.Reason, tc.ref)
		})
	}
}

// TestSignatureRefGenericBounds holds that the generic reference bounds still
// apply to signature-ref before its form is checked.
func TestSignatureRefGenericBounds(t *testing.T) {
	r := validResult()
	r.SignatureRef = ""
	requireRejected(t, r.Validate(), fixtureCID, "signature-ref", aegis.ErrMissingField)

	r.SignatureRef = "https://github.com/x\\y/SHA256SUMS.bundle"
	err := r.Validate()
	requireRejected(t, err, fixtureCID, "signature-ref", aegis.ErrInvalidField)
	assert.Contains(t, err.Error(), "no control characters or backslashes")

	r.SignatureRef = "https://github.com/x\x00/SHA256SUMS.bundle"
	err = r.Validate()
	requireRejected(t, err, fixtureCID, "signature-ref", aegis.ErrInvalidField)
	assert.Contains(t, err.Error(), "no control characters or backslashes")
}

// TestPositiveSignatureRef holds the admitted alphabet of host and path.
func TestPositiveSignatureRef(t *testing.T) {
	for _, ref := range []string{
		"https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle",
		"https://h/SHA256SUMS.bundle",
		"https://Sub-1.Example.org/a_b/c~d/e.f/-g/SHA256SUMS.bundle",
		"https://example.org/.../SHA256SUMS.bundle",
	} {
		r := validResult()
		r.SignatureRef = ref
		require.NoError(t, r.Validate(), ref)
	}
}

type failReader struct{ err error }

func (f *failReader) Read(p []byte) (int, error) {
	return 0, f.err
}

func TestDigestImageVectorsAndErrors(t *testing.T) {
	ctx := context.Background()

	digest, err := aegis.DigestImage(ctx, fixtureCID, strings.NewReader("abc"))
	require.NoError(t, err)
	assert.Equal(t, "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", digest)

	_, err = aegis.DigestImage(ctx, fixtureCID, strings.NewReader(""))
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "image", aerr.Field)
	assert.Equal(t, "is empty", aerr.Reason)
	assert.ErrorIs(t, err, aegis.ErrInvalidField)

	cancCtx, cancel := context.WithCancel(ctx)
	cancel()
	_, err = aegis.DigestImage(cancCtx, fixtureCID, strings.NewReader("abc"))
	require.Error(t, err)
	assert.True(t, errors.Is(err, context.Canceled), "errors.Is context.Canceled")

	expErr := errors.New("read failed")
	_, err = aegis.DigestImage(ctx, fixtureCID, &failReader{err: expErr})
	require.Error(t, err)
	assert.ErrorIs(t, err, expErr)
}

// TestDigestImageShortReads holds that a reader which returns one byte per
// call is digested whole and still bounded: the loop bound counts whole chunks,
// so a short read must never end the digest early.
func TestDigestImageShortReads(t *testing.T) {
	ctx := context.Background()
	want := sha256.Sum256([]byte("12345678"))

	d, err := aegis.DigestReader(ctx, fixtureCID, iotest.OneByteReader(strings.NewReader("12345678")), 8)
	require.NoError(t, err)
	assert.Equal(t, "sha256:"+hex.EncodeToString(want[:]), d)

	_, err = aegis.DigestReader(ctx, fixtureCID, iotest.OneByteReader(strings.NewReader("123456789")), 8)
	requireRejected(t, err, fixtureCID, "image", aegis.ErrOutOfBounds)

	payload := bytes.Repeat([]byte("short-read-payload"), 4096)
	want = sha256.Sum256(payload)
	d, err = aegis.DigestImage(ctx, fixtureCID, iotest.HalfReader(bytes.NewReader(payload)))
	require.NoError(t, err)
	assert.Equal(t, "sha256:"+hex.EncodeToString(want[:]), d)
}

// TestDigestImageChunkBoundary holds the bound where the limit is a whole
// number of chunks: exactly the limit passes, one byte more is refused.
func TestDigestImageChunkBoundary(t *testing.T) {
	ctx := context.Background()
	const chunk = 1 << 20
	data := bytes.Repeat([]byte{0x5a}, 2*chunk+1)
	want := sha256.Sum256(data[:2*chunk])

	d, err := aegis.DigestReader(ctx, fixtureCID, bytes.NewReader(data[:2*chunk]), 2*chunk)
	require.NoError(t, err)
	assert.Equal(t, "sha256:"+hex.EncodeToString(want[:]), d)

	_, err = aegis.DigestReader(ctx, fixtureCID, bytes.NewReader(data), 2*chunk)
	requireRejected(t, err, fixtureCID, "image", aegis.ErrOutOfBounds)
}

func TestDigestImageBoundsAndChunks(t *testing.T) {
	ctx := context.Background()

	d, err := aegis.DigestReader(ctx, fixtureCID, strings.NewReader("12345678"), 8)
	require.NoError(t, err)
	assert.NotEmpty(t, d)

	_, err = aegis.DigestReader(ctx, fixtureCID, strings.NewReader("123456789"), 8)
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "image", aerr.Field)
	assert.ErrorIs(t, err, aegis.ErrOutOfBounds)

	data := bytes.Repeat([]byte("chunked-digest-test-payload-bytes"), 100000)
	digest, err := aegis.DigestImage(ctx, fixtureCID, bytes.NewReader(data))
	require.NoError(t, err)
	expected := sha256.Sum256(data)
	assert.Equal(t, "sha256:"+hex.EncodeToString(expected[:]), digest)
}

func TestChecksumsListValid(t *testing.T) {
	targetHex := "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	goodDigest := "sha256:" + targetHex

	data2Space := []byte(fmt.Sprintf("%s  image.raw\n", targetHex))
	require.NoError(t, aegis.ChecksumsList(fixtureCID, data2Space, goodDigest))

	dataBinary := []byte(fmt.Sprintf("%s *image.raw\n", targetHex))
	require.NoError(t, aegis.ChecksumsList(fixtureCID, dataBinary, goodDigest))

	dataCRLF := []byte(fmt.Sprintf("%s  image.raw\r\n", targetHex))
	require.NoError(t, aegis.ChecksumsList(fixtureCID, dataCRLF, goodDigest))

	otherData := []byte(fmt.Sprintf("%s  image.raw\n", strings.Repeat("0", 64)))
	err := aegis.ChecksumsList(fixtureCID, otherData, goodDigest)
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "checksums", aerr.Field)
	assert.Equal(t, "does not list the image digest", aerr.Reason)
	assert.ErrorIs(t, err, aegis.ErrInvalidField)
}

func TestChecksumsListMalformed(t *testing.T) {
	goodDigest := "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	malformedCases := map[string]string{
		"63 hex":         strings.Repeat("a", 63) + "  image.raw\n",
		"upper-case hex": strings.Repeat("A", 64) + "  image.raw\n",
		"one space":      strings.Repeat("a", 64) + " image.raw\n",
		"empty name":     strings.Repeat("a", 64) + "  \n",
	}
	for mname, mline := range malformedCases {
		t.Run(mname, func(t *testing.T) {
			err := aegis.ChecksumsList(fixtureCID, []byte(mline), goodDigest)
			require.Error(t, err)
			var aerr *aegis.Error
			require.ErrorAs(t, err, &aerr)
			assert.Equal(t, "checksums", aerr.Field)
			assert.Equal(t, "line 1 is not '<sha256>  <name>'", aerr.Reason)
			assert.ErrorIs(t, err, aegis.ErrInvalidField)
		})
	}
}

func TestChecksumsListBounds(t *testing.T) {
	targetHex := "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	goodDigest := "sha256:" + targetHex

	var b strings.Builder
	fmt.Fprintf(&b, "%s  target.raw\n", targetHex)
	for i := 1; i < aegis.MaxChecksumLines; i++ {
		fmt.Fprintf(&b, "%s  file%04d.raw\n", strings.Repeat("a", 64), i)
	}
	require.NoError(t, aegis.ChecksumsList(fixtureCID, []byte(b.String()), goodDigest))

	fmt.Fprintf(&b, "%s  file-overflow.raw\n", strings.Repeat("a", 64))
	err := aegis.ChecksumsList(fixtureCID, []byte(b.String()), goodDigest)
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "checksums", aerr.Field)
	assert.ErrorIs(t, err, aegis.ErrOutOfBounds)

	err = aegis.ChecksumsList(fixtureCID, make([]byte, aegis.MaxChecksumsBytes+1), goodDigest)
	require.Error(t, err)
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "checksums", aerr.Field)
	assert.ErrorIs(t, err, aegis.ErrOutOfBounds)

	err = aegis.ChecksumsList(fixtureCID, []byte(fmt.Sprintf("%s  image.raw\n", targetHex)), "bad-digest")
	require.Error(t, err)
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "image-digest", aerr.Field)
	assert.ErrorIs(t, err, aegis.ErrInvalidField)
}

func TestNewResult(t *testing.T) {
	manifest, err := aegis.Load("testdata/product-input.json")
	require.NoError(t, err)
	req, err := manifest.BuildRequest()
	require.NoError(t, err)

	imageDigest := "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	sigRef := "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle"
	bootRef := "evidence/boot/aegis-m18-product-input-0001.json"

	res, err := aegis.NewResult(req, imageDigest, sigRef, bootRef)
	require.NoError(t, err)
	assert.Equal(t, req.CorrelationID, res.CorrelationID)
	assert.Equal(t, aegis.ResultSchema, res.Schema)
	assert.Equal(t, imageDigest, res.ImageDigest)

	res, err = aegis.NewResult(req, imageDigest, "bad-signature-ref", bootRef)
	require.Error(t, err)
	assert.Equal(t, aegis.Result{}, res)
}

func TestEmitPositive(t *testing.T) {
	manifest, err := aegis.Load("testdata/product-input.json")
	require.NoError(t, err)
	req, err := manifest.BuildRequest()
	require.NoError(t, err)

	sigRef := "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle"
	bootRef := "evidence/boot/aegis-m18-product-input-0001.json"

	dir := t.TempDir()
	imgPath := filepath.Join(dir, "image.raw")
	imgData := []byte("image payload for testing emit")
	require.NoError(t, os.WriteFile(imgPath, imgData, 0o600))
	imgDigest := sha256.Sum256(imgData)
	imgHex := hex.EncodeToString(imgDigest[:])

	sumsPath := filepath.Join(dir, "SHA256SUMS")
	require.NoError(t, os.WriteFile(sumsPath, []byte(fmt.Sprintf("%s  image.raw\n", imgHex)), 0o600))

	res, err := aegis.Emit(context.Background(), req, aegis.Artifact{
		ImagePath:       imgPath,
		ChecksumsPath:   sumsPath,
		SignatureRef:    sigRef,
		BootEvidenceRef: bootRef,
	})
	require.NoError(t, err)
	require.NoError(t, res.Validate())
	assert.Equal(t, "sha256:"+imgHex, res.ImageDigest)
	assert.Equal(t, req.CorrelationID, res.CorrelationID)
}

func TestEmitNegatives(t *testing.T) {
	manifest, err := aegis.Load("testdata/product-input.json")
	require.NoError(t, err)
	req, err := manifest.BuildRequest()
	require.NoError(t, err)

	dir := t.TempDir()
	write := func(name, content string) string {
		t.Helper()
		path := filepath.Join(dir, name)
		require.NoError(t, os.WriteFile(path, []byte(content), 0o600))
		return path
	}
	image := write("valid.raw", "bytes")
	imageSum := sha256.Sum256([]byte("bytes"))
	listed := write("SHA256SUMS", hex.EncodeToString(imageSum[:])+"  valid.raw\n")
	good := aegis.Artifact{
		ImagePath:       image,
		ChecksumsPath:   listed,
		SignatureRef:    "https://github.com/cordanaLLM/imago/releases/download/aegis-m18-0001/SHA256SUMS.bundle",
		BootEvidenceRef: "evidence/boot/aegis-m18-product-input-0001.json",
	}
	_, err = aegis.Emit(context.Background(), req, good)
	require.NoError(t, err, "the unchanged artifact is accepted")

	cases := map[string]struct {
		change func(a *aegis.Artifact)
		field  string
		cause  error
		reason string
	}{
		"missing image":     {func(a *aegis.Artifact) { a.ImagePath = filepath.Join(dir, "absent.raw") }, "image", os.ErrNotExist, "open image"},
		"empty image":       {func(a *aegis.Artifact) { a.ImagePath = write("empty.raw", "") }, "image", aegis.ErrInvalidField, "is empty"},
		"missing checksums": {func(a *aegis.Artifact) { a.ChecksumsPath = filepath.Join(dir, "absent-sums") }, "checksums", os.ErrNotExist, "open checksums"},
		"unlisted image": {func(a *aegis.Artifact) {
			a.ChecksumsPath = write("other-sums", strings.Repeat("0", 64)+"  other.raw\n")
		}, "checksums", aegis.ErrInvalidField, "does not list the image digest"},
		"malformed line": {func(a *aegis.Artifact) { a.ChecksumsPath = write("bad-sums", "abc  valid.raw\n") }, "checksums", aegis.ErrInvalidField, "line 1 is not"},
		"oversized sums": {func(a *aegis.Artifact) {
			a.ChecksumsPath = write("big-sums", strings.Repeat("\n", aegis.MaxChecksumsBytes+1))
		}, "checksums", aegis.ErrOutOfBounds, "exceeds"},
		"other signature":  {func(a *aegis.Artifact) { a.SignatureRef = "sigstore://rekor.example.com/entries/0001" }, "signature-ref", aegis.ErrInvalidField, "must start with https://"},
		"no boot evidence": {func(a *aegis.Artifact) { a.BootEvidenceRef = "" }, "boot-evidence-ref", aegis.ErrMissingField, "required"},
	}
	for label, tc := range cases {
		t.Run(label, func(t *testing.T) {
			a := good
			tc.change(&a)
			res, err := aegis.Emit(context.Background(), req, a)
			requireRejected(t, err, fixtureCID, tc.field, tc.cause)
			assert.Contains(t, err.Error(), tc.reason)
			assert.Equal(t, aegis.Result{}, res, "a refused emit returns no result")
		})
	}
}

type failWriter struct{ err error }

func (f *failWriter) Write(p []byte) (int, error) {
	return 0, f.err
}

func TestWriteResult(t *testing.T) {
	r := validResult()
	r.BootEvidenceRef = "https://example.org/evidence?run=1&attempt=<2>"

	var buf bytes.Buffer
	require.NoError(t, aegis.WriteResult(&buf, r))
	raw := buf.Bytes()
	assert.True(t, bytes.HasSuffix(raw, []byte("\n")), "ends with newline")
	assert.Contains(t, string(raw), "run=1&attempt=<2>", "references are written unescaped")

	again, err := aegis.ParseResult(raw)
	require.NoError(t, err)
	assert.Equal(t, r, *again)

	invalid := r
	invalid.Schema = "bad.schema"
	var zeroBuf bytes.Buffer
	err = aegis.WriteResult(&zeroBuf, invalid)
	require.Error(t, err)
	assert.Equal(t, 0, zeroBuf.Len(), "zero bytes written")

	err = aegis.WriteResult(&failWriter{err: errors.New("write failed")}, r)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "write result")
}

func TestParseResult(t *testing.T) {
	valid := validResult()
	var buf bytes.Buffer
	require.NoError(t, aegis.WriteResult(&buf, valid))
	validJSON := buf.Bytes()

	res, err := aegis.ParseResult(validJSON)
	require.NoError(t, err)
	assert.Equal(t, valid, *res)

	raw := []byte(`{"schema":"imago.p01.product-result.v1","correlation-id":"test-cid","extra":1}`)
	aerr := requireParseError(t, raw, "input", aegis.ErrDecode)
	assert.Equal(t, "test-cid", aerr.CorrelationID)

	trailing := append(bytes.Clone(validJSON), " {}"...)
	requireParseError(t, trailing, "input", aegis.ErrTrailingContent)
	requireParseError(t, make([]byte, aegis.MaxInputBytes+1), "input", aegis.ErrInputTooLarge)

	badSchema := valid
	badSchema.Schema = "bad.schema"
	requireParseError(t, marshalResult(t, badSchema), "schema", aegis.ErrSchema)

	oldSig := valid
	oldSig.SignatureRef = "sigstore://rekor.example.com/entries/0001"
	requireParseError(t, marshalResult(t, oldSig), "signature-ref", aegis.ErrInvalidField)
}

// requireParseError asserts that ParseResult rejects data with an *aegis.Error
// naming field and wrapping sentinel, and returns that error.
func requireParseError(t *testing.T, data []byte, field string, sentinel error) *aegis.Error {
	t.Helper()
	_, err := aegis.ParseResult(data)
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, field, aerr.Field)
	assert.ErrorIs(t, err, sentinel)
	return aerr
}

// marshalResult encodes r without the validation WriteResult applies.
func marshalResult(t *testing.T, r aegis.Result) []byte {
	t.Helper()
	data, err := json.Marshal(r)
	require.NoError(t, err)
	return data
}

func TestLoadResult(t *testing.T) {
	valid := validResult()
	var buf bytes.Buffer
	require.NoError(t, aegis.WriteResult(&buf, valid))

	path := filepath.Join(t.TempDir(), "result.json")
	require.NoError(t, os.WriteFile(path, buf.Bytes(), 0o600))
	res, err := aegis.LoadResult(path)
	require.NoError(t, err)
	assert.Equal(t, valid, *res)

	_, err = aegis.LoadResult(filepath.Join(t.TempDir(), "nonexistent.json"))
	require.Error(t, err)
	var aerr *aegis.Error
	require.ErrorAs(t, err, &aerr)
	assert.Equal(t, "input", aerr.Field)
}
