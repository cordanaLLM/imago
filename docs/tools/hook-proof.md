# Hook Refusal Proof

The Git hooks in `lefthook.yml` run the pinned Praetor engine. No CI job installs that engine, so CI cannot show that the hooks refuse anything. `make prove-hooks` shows it on a workstation where the hooks are installed. It covers the three cases of [issue #80](https://github.com/cordanaLLM/imago/issues/80) and plants one defect for every other pre-commit and pre-push job. The post-commit jobs (`state-sync`, `dedupe-cadence`) only record state and refuse nothing, so they have no case.

## Run it

```bash
make prove-hooks          # same as: python3 -I tools/ci/prove_hooks.py
python3 -I tools/ci/prove_hooks.py --skip-gate   # without the two gate cases
```

It needs `git`, `lefthook`, `go`, `gofmt`, `govulncheck`, `reuse` 6.x and the engine wrapper `.config/lefthook/engine.sh`, as `make verify-all` does. The security case fetches an old module version, so it needs network access, and the gate cases need the engine's devcontainer (Docker). `--skip-gate` leaves the gate cases out and prints `pre-push gate: skipped (--skip-gate), not proven`. A job that skips because its tool is missing exits 0, so its planted case fails rather than passing silently. The run exits 0 only when every case behaves as below; any other result prints `::error::hook proof failed:` with the reason and exits 1. A full run takes a few minutes; the gate cases take most of it.

## What it does

[`tools/ci/prove_hooks.py`](https://github.com/cordanaLLM/imago/blob/main/tools/ci/prove_hooks.py) clones the committed tree of the checkout into a temporary directory. The clone takes the origin URL and the default branch of the checkout, because the audit reads both, and its push URL is set to `no-push`. Then it runs `lefthook install` in the clone. The checkout it runs from is never changed.

| Case | Action in the clone | Passes when |
| :--- | :--- | :--- |
| Positive | `compile-context --verify` and `audit --offline` | both exit 0 |
| Negative | commit a hand edit to `CLAUDE.md` | the commit fails, HEAD stays put, the output names `CLAUDE.md is out of sync with AGENTS.md` |
| Boundary | commit a new `eval` call appended to `tools/ci/trivy_coverage.py` | the commit fails, HEAD stays put, the output names `[HISS-08] tools/ci/trivy_coverage.py`, and `.standards-baseline.json` has the same SHA-256 afterwards |
| `govet` | commit `pkg/reason/planted_vet.go` with `fmt.Sprintf("%d", "text")` | the commit fails, HEAD stays put, the output names the vet printf finding |
| `reuse-lint` | commit `tools/ci/planted_licence.txt` declaring `0BSD`, which `LICENSES/` does not hold | the commit fails, HEAD stays put, the output names `'0BSD' found in:` |
| `gofmt` | commit an unformatted `pkg/reason/planted_format.go` | the commit goes through and the committed file is in gofmt form: this job repairs, it does not refuse |
| Pre-push positive | `lefthook run pre-push --force --command <job>` for `security`, `flavor-audit`, `audit`, `gate` | each exits 0 on the clean clone |
| `flavor-audit` | delete `.yamllint.yml` | the job fails and names it under `Missing Templates:` |
| `audit` | append the `eval` call without committing it | the job fails and names `[HISS-08] tools/ci/trivy_coverage.py` |
| `security` | `go get gopkg.in/yaml.v2@v2.2.2` and call `yaml.Unmarshal` | the job fails and names `GO-2020-0036: gopkg.in/yaml.v2.Unmarshal is called` |
| `gate` | commit a test that calls `t.Fatal` | the job fails and names `--- FAIL: TestPlantedFailure`; a gate that fails for another reason, such as a broken devcontainer, does not count |

Each pre-push case runs one job with `--force`, because lefthook otherwise skips jobs when no push is in progress. After every case the clone is reset to its starting commit. Commands run with `LC_ALL=C` and `NO_COLOR=1` so that the reasons match on every host locale. Planted texts that would trip a check of this repository (the `eval` call, the licence tag) are assembled at run time, so the tool's source holds no infraction.

## How the proof itself is checked

[`tests/test_prove_hooks.py`](https://github.com/cordanaLLM/imago/blob/main/tests/test_prove_hooks.py) replaces every command with a scripted reply and runs in the normal pytest suite. Each failure mode has its own planted case for every job: a failing check on the clean clone, an accepted plant, a moved HEAD, a refusal without its reason, a gate refused by a broken devcontainer, a changed baseline, a refused or unformatted gofmt commit and a failed setup step.

A clone without active hooks fails as well, at the positive case: the audit reports `.git/hooks/pre-commit is missing or inactive`.
