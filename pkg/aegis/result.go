// Copyright 2026 Lusoris
package aegis

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"hash"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/cordanaLLM/imago/pkg/reason"
)

// Bounds and names of the result side. Each one is a contract constant
// recorded in ADR-0024.
const (
	// SignatureBundleFile is the required last path segment of signature-ref:
	// the keyless cosign bundle over the SHA256SUMS file published beside it.
	SignatureBundleFile = "SHA256SUMS.bundle"
	// MaxSignatureHostLen bounds the host of signature-ref.
	MaxSignatureHostLen = 253
	// MaxImageBytes bounds the image read by DigestImage (64 GiB).
	MaxImageBytes int64 = 64 << 30
	// MaxChecksumsBytes bounds the SHA256SUMS file ChecksumsList accepts (1 MiB).
	MaxChecksumsBytes = 1 << 20
	// MaxChecksumLines bounds the entries of a SHA256SUMS file.
	MaxChecksumLines = 1024
)

// Artifact names what a finished, signed build hands the emitter.
type Artifact struct {
	ImagePath       string // file whose SHA-256 becomes image-digest
	ChecksumsPath   string // the SHA256SUMS file the signature bundle covers
	SignatureRef    string
	BootEvidenceRef string
}

// imageChunkSize is the read size of the image digest.
const imageChunkSize int64 = 1 << 20

// rejectResult builds the correlated error of the result side. cid is reported
// as given, so callers pass an already reported identifier.
func rejectResult(cid, field, reason string, cause error) error {
	return &Error{CorrelationID: cid, Field: field, Reason: reason, Err: cause}
}

// hashChunk feeds one chunk of r into h. io.ReadFull makes every chunk but the
// last a whole buffer, which is what lets digestReader bound its loop by the
// byte limit whatever sizes the reader returns. ended reports the end of r.
func hashChunk(h hash.Hash, r io.Reader, buf []byte) (n int, ended bool, err error) {
	n, err = io.ReadFull(r, buf)
	if _, werr := h.Write(buf[:n]); werr != nil {
		return n, false, werr
	}
	if errors.Is(err, io.EOF) || errors.Is(err, io.ErrUnexpectedEOF) {
		return n, true, nil
	}
	return n, false, err
}

// digestReader returns the SHA-256 of r as an image digest. It refuses an empty
// input and one above limit bytes, and stops when ctx ends. The loop runs at
// most limit/imageChunkSize+2 times: every iteration but the last adds a whole
// chunk, so an input that has not ended by then is above the limit.
func digestReader(ctx context.Context, cid string, r io.Reader, limit int64) (string, error) {
	rcid := reportedCorrelationID(cid)
	buf := make([]byte, imageChunkSize)
	h := sha256.New()
	var total int64
	ended := false
	for i := int64(0); i <= limit/imageChunkSize+1 && !ended; i++ {
		if err := ctx.Err(); err != nil {
			return "", rejectResult(rcid, "image", reason.Bound("read image: "+err.Error()), fmt.Errorf("read image: %w", err))
		}
		n, end, err := hashChunk(h, r, buf)
		if err != nil {
			return "", rejectResult(rcid, "image", reason.Bound("read image: "+err.Error()), err)
		}
		total += int64(n)
		if total > limit {
			return "", rejectResult(rcid, "image", fmt.Sprintf("exceeds %d bytes", limit), ErrOutOfBounds)
		}
		ended = end
	}
	if !ended {
		return "", rejectResult(rcid, "image", fmt.Sprintf("exceeds %d bytes", limit), ErrOutOfBounds)
	}
	if total == 0 {
		return "", rejectResult(rcid, "image", "is empty", ErrInvalidField)
	}
	return DigestPrefix + hex.EncodeToString(h.Sum(nil)), nil
}

// DigestImage returns the SHA-256 of r as an image digest ("sha256:" and 64
// lowercase hex characters). It refuses an empty input and one above
// MaxImageBytes, and stops when ctx ends.
func DigestImage(ctx context.Context, cid string, r io.Reader) (string, error) {
	return digestReader(ctx, cid, r, MaxImageBytes)
}

// ChecksumsList checks that data is a SHA256SUMS file that lists digest. Every
// non-empty line has the form sha256sum writes; the file is at most
// MaxChecksumsBytes and MaxChecksumLines long. The file name of the line is not
// compared: the digest identifies the image.
func ChecksumsList(cid string, data []byte, digest string) error {
	rcid := reportedCorrelationID(cid)
	if !isDigest(digest) {
		return rejectResult(rcid, "image-digest", fmt.Sprintf("must be %q followed by %d lowercase hex characters", DigestPrefix, DigestHexLen), ErrInvalidField)
	}
	if len(data) > MaxChecksumsBytes {
		return rejectResult(rcid, "checksums", fmt.Sprintf("exceeds %d bytes", MaxChecksumsBytes), ErrOutOfBounds)
	}
	found, err := checksumsContain(rcid, data, digest[len(DigestPrefix):])
	if err != nil {
		return err
	}
	if !found {
		return rejectResult(rcid, "checksums", "does not list the image digest", ErrInvalidField)
	}
	return nil
}

// checksumsContain reports whether a line of the SHA256SUMS file data carries
// the hex digest want. It refuses a malformed line and a file of more than
// MaxChecksumLines non-empty lines, also after the digest was found.
func checksumsContain(rcid string, data []byte, want string) (bool, error) {
	lineCount, found := 0, false
	for lineIdx, raw := range strings.Split(string(data), "\n") {
		line := strings.TrimSuffix(raw, "\r")
		if line == "" {
			continue
		}
		lineCount++
		if lineCount > MaxChecksumLines {
			return false, rejectResult(rcid, "checksums", fmt.Sprintf("exceeds %d lines", MaxChecksumLines), ErrOutOfBounds)
		}
		got, ok := checksumLineHex(line)
		if !ok {
			return false, rejectResult(rcid, "checksums", fmt.Sprintf("line %d is not '<sha256>  <name>'", lineIdx+1), ErrInvalidField)
		}
		found = found || got == want
	}
	return found, nil
}

// checksumLineHex returns the digest of one SHA256SUMS line in the form
// sha256sum writes: 64 lowercase hex characters, two spaces (text mode) or a
// space and an asterisk (binary mode), and a file name.
func checksumLineHex(line string) (string, bool) {
	const nameAt = DigestHexLen + 2
	if len(line) <= nameAt || !isLowerHex(line[:DigestHexLen], DigestHexLen) {
		return "", false
	}
	if sep := line[DigestHexLen:nameAt]; sep != "  " && sep != " *" {
		return "", false
	}
	if hasControlOrBackslash(line[nameAt:]) {
		return "", false
	}
	return line[:DigestHexLen], true
}

// NewResult builds the result for req and validates it, so a caller never
// holds a result that Result.Validate refuses.
func NewResult(req BuildRequest, imageDigest, signatureRef, bootEvidenceRef string) (Result, error) {
	r := Result{
		Schema:          ResultSchema,
		CorrelationID:   req.CorrelationID,
		ImageDigest:     imageDigest,
		SignatureRef:    signatureRef,
		BootEvidenceRef: bootEvidenceRef,
	}
	if err := r.Validate(); err != nil {
		return Result{}, err
	}
	return r, nil
}

// Emit builds the result for an accepted request and a built image: it digests
// the image file, requires that the checksum file lists that digest, and
// carries the request's correlation id. It does not sign, does not run cosign
// and does not contact the network (ADR-0024).
func Emit(ctx context.Context, req BuildRequest, a Artifact) (Result, error) {
	digest, err := readImageFileDigest(ctx, req.CorrelationID, a.ImagePath)
	if err != nil {
		return Result{}, err
	}
	data, err := readChecksumsFile(req.CorrelationID, a.ChecksumsPath)
	if err != nil {
		return Result{}, err
	}
	if err := ChecksumsList(req.CorrelationID, data, digest); err != nil {
		return Result{}, err
	}
	return NewResult(req, digest, a.SignatureRef, a.BootEvidenceRef)
}

// readImageFileDigest digests the image file at path under the bounds of
// DigestImage.
func readImageFileDigest(ctx context.Context, cid, path string) (string, error) {
	rcid := reportedCorrelationID(cid)
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return "", rejectResult(rcid, "image", reason.Bound("open image: "+err.Error()), err)
	}
	digest, err := DigestImage(ctx, cid, f)
	cerr := f.Close()
	if err != nil {
		return "", err
	}
	if cerr != nil {
		return "", rejectResult(rcid, "image", reason.Bound("close image: "+cerr.Error()), cerr)
	}
	return digest, nil
}

// readChecksumsFile reads at most MaxChecksumsBytes+1 bytes of the checksum
// file at path, so ChecksumsList can refuse a longer file without reading it
// whole.
func readChecksumsFile(cid, path string) ([]byte, error) {
	rcid := reportedCorrelationID(cid)
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, rejectResult(rcid, "checksums", reason.Bound("open checksums: "+err.Error()), err)
	}
	data, err := io.ReadAll(io.LimitReader(f, MaxChecksumsBytes+1))
	cerr := f.Close()
	if err != nil {
		return nil, rejectResult(rcid, "checksums", reason.Bound("read checksums: "+err.Error()), err)
	}
	if cerr != nil {
		return nil, rejectResult(rcid, "checksums", reason.Bound("close checksums: "+cerr.Error()), cerr)
	}
	return data, nil
}

// WriteResult validates r and writes it to w as indented JSON. An invalid
// result writes nothing.
func WriteResult(w io.Writer, r Result) error {
	if err := r.Validate(); err != nil {
		return err
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	if err := enc.Encode(r); err != nil {
		return fmt.Errorf("write result: %w", err)
	}
	if _, err := w.Write(buf.Bytes()); err != nil {
		return fmt.Errorf("write result: %w", err)
	}
	return nil
}

// ParseResult strictly decodes and validates one result held in memory, under
// the rules Parse applies to a request: unknown fields, trailing content, and
// inputs above MaxInputBytes are rejected.
func ParseResult(data []byte) (*Result, error) {
	var r Result
	if err := strictDecode(data, "result", &r); err != nil {
		return nil, err
	}
	if err := r.Validate(); err != nil {
		return nil, err
	}
	return &r, nil
}

// DecodeResult reads at most MaxInputBytes from r and parses one result.
func DecodeResult(r io.Reader) (*Result, error) {
	data, err := io.ReadAll(io.LimitReader(r, MaxInputBytes+1))
	if err != nil {
		return nil, rejectResult(MissingCorrelationID, "input", reason.Bound("read result: "+err.Error()), err)
	}
	return ParseResult(data)
}

// LoadResult opens a result file and returns the validated result. The read is
// bounded by MaxInputBytes.
func LoadResult(path string) (*Result, error) {
	f, err := os.Open(filepath.Clean(path))
	if err != nil {
		return nil, rejectResult(MissingCorrelationID, "input", reason.Bound("open result: "+err.Error()), err)
	}
	r, err := DecodeResult(f)
	cerr := f.Close()
	if err != nil {
		return nil, err
	}
	if cerr != nil {
		return nil, rejectResult(r.CorrelationID, "input", reason.Bound("close result: "+cerr.Error()), cerr)
	}
	return r, nil
}

// rejectSignature refuses signature-ref with a fixed reason. The reason names
// the rule and never repeats the value, which may be attacker-supplied.
func rejectSignature(cid, reason string) error {
	return rejectResult(cid, "signature-ref", reason, ErrInvalidField)
}

// validateSignatureRef admits the one form of signature-ref (ADR-0024): the
// HTTPS URL of a keyless cosign bundle named SignatureBundleFile. The check is
// an allow-list over bytes, without a regular expression or a URL parser, so a
// consumer can mirror it exactly. The generic reference bounds (required,
// MaxReferenceLen, no control character, no backslash) apply first.
func validateSignatureRef(cid, value string) error {
	if err := validateReference(cid, "signature-ref", value); err != nil {
		return err
	}
	const scheme = "https://"
	if !strings.HasPrefix(value, scheme) {
		return rejectSignature(cid, "must start with "+scheme)
	}
	rest := value[len(scheme):]
	slash := strings.IndexByte(rest, '/')
	if slash < 0 {
		return rejectSignature(cid, "must contain a path starting with /")
	}
	if err := validateSignatureHost(cid, rest[:slash]); err != nil {
		return err
	}
	return validateSignaturePath(cid, rest[slash:])
}

// isHostByte reports whether c may appear in the host of signature-ref. A
// colon and an at sign are absent, so a port and a user part are refused.
func isHostByte(c byte) bool {
	return isAlnum(c) || c == '.' || c == '-'
}

// validateSignatureHost checks the host of signature-ref: 1..MaxSignatureHostLen
// bytes of the host alphabet that begin and end alphanumeric.
func validateSignatureHost(cid, host string) error {
	if len(host) < 1 || len(host) > MaxSignatureHostLen {
		return rejectSignature(cid, fmt.Sprintf("host must be 1..%d characters", MaxSignatureHostLen))
	}
	if !isAlnum(host[0]) || !isAlnum(host[len(host)-1]) {
		return rejectSignature(cid, "host must begin and end with an alphanumeric character")
	}
	for i := 0; i < len(host); i++ {
		if !isHostByte(host[i]) {
			return rejectSignature(cid, "host contains invalid characters")
		}
	}
	return nil
}

// isPathByte reports whether c may appear in the path of signature-ref. A
// question mark, a hash sign and a percent sign are absent, so a query, a
// fragment and percent-encoding are refused.
func isPathByte(c byte) bool {
	return isAlnum(c) || c == '.' || c == '_' || c == '~' || c == '/' || c == '-'
}

// validateSignaturePath checks the path of signature-ref, which begins with a
// slash: path alphabet only, no empty segment, no dot segment, and the last
// segment is SignatureBundleFile. The loop is bounded by MaxReferenceLen.
func validateSignaturePath(cid, path string) error {
	for i := 0; i < len(path); i++ {
		if !isPathByte(path[i]) {
			return rejectSignature(cid, "path contains invalid characters")
		}
	}
	segs := strings.Split(path[1:], "/")
	for _, seg := range segs {
		if seg == "" {
			return rejectSignature(cid, "path contains empty segments")
		}
		if seg == "." || seg == ".." {
			return rejectSignature(cid, "path contains dot segments")
		}
	}
	if segs[len(segs)-1] != SignatureBundleFile {
		return rejectSignature(cid, "last path segment must be "+SignatureBundleFile)
	}
	return nil
}
