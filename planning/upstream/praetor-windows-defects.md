# Upstream report: praetor adoption and planning writers fail on Windows

Target: `cordanallm/praetor` (main, `89c56ec3`). Observed on Windows 11 with Go 1.27.0 on 2026-09-15 while adopting `cordanaLLM/imago` (then `lusoris/lusoris-cloud-images`).

## Defect 1: catalog artifact path validation compares platform separators against a slash constant

`internal/config/catalog_projection.go` `validateCatalogPath` computes `filepath.Dir(rel)` (backslashes on Windows) and compares it with the constant `archetypeDirName` (`.config/archetypes`, forward slashes). Every artifact fails with:

```text
x catalog artifact must be directly inside the profiles or facets directory
Error: adopt repository failed: catalog artifact must be directly inside the profiles or facets directory
```

Reproduction:

```bash
standardsctl adopt --dry-run --path <any repo> --lock-source-root <praetor checkout> --profile gitops-infra --facets security:high
```

Fix that removed the failure locally:

```go
dir := filepath.ToSlash(filepath.Dir(rel))
if dir != filepath.ToSlash(archetypeDirName) && dir != filepath.ToSlash(filepath.Join(archetypeDirName, facetDirName)) {
```

## Defect 2: directory fsync is refused on Windows, aborting adoption and planning writes after the files exist

`internal/contextopt/replace.go` `SyncDirectory` opens the directory and calls `Sync()`. Windows returns `Zugriff verweigert` (access denied) for directory handles, so:

- `standardsctl adopt` writes `.standards.yaml` and `.standards.lock`, then aborts with `sync <repo>\.config\archetypes\.: Zugriff verweigert`, leaving a partial adoption.
- `standardsctl planning prepare` writes all four artifacts, then reports `write planning artifacts: sync <output-dir>\.: Zugriff verweigert` and exits non-zero although the output is complete.

Fix that removed the failure locally (file contents are still synced individually):

```go
if runtime.GOOS == "windows" {
    return dir.Close()
}
return errors.Join(dir.Sync(), dir.Close())
```

## Expected

Adoption and planning preparation behave the same on Windows workstations as on Linux, or the Windows limitation is documented and reported as a warning rather than a failed adoption.
