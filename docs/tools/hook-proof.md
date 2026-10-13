# Hook Refusal Proof

The pre-commit hooks in `lefthook.yml` run the pinned Praetor engine. No CI job installs that engine, so CI cannot show that the hooks refuse anything. `make prove-hooks` shows it on a workstation where the hooks are installed. It covers the three cases of [issue #80](https://github.com/cordanaLLM/imago/issues/80).

## Run it

```bash
make prove-hooks          # same as: python3 -I tools/ci/prove_hooks.py
```

It needs `git`, `lefthook` and the engine wrapper `.config/lefthook/engine.sh`, as `make verify-all` does. It exits 0 only when all three cases behave as below; any other result prints `::error::hook proof failed:` with the reason and exits 1.

## What it does

[`tools/ci/prove_hooks.py`](https://github.com/cordanaLLM/imago/blob/main/tools/ci/prove_hooks.py) clones the committed tree of the checkout into a temporary directory. The clone takes the origin URL and the default branch of the checkout, because the audit reads both, and its push URL is set to `no-push`. Then it runs `lefthook install` in the clone. The checkout it runs from is never changed.

| Case | Action in the clone | Passes when |
| :--- | :--- | :--- |
| Positive | `compile-context --verify` and `audit --offline` | both exit 0 |
| Negative | commit a hand edit to `CLAUDE.md` | the commit fails, HEAD stays put, the output names `CLAUDE.md is out of sync with AGENTS.md` |
| Boundary | commit a new `eval` call appended to `tools/ci/trivy_coverage.py` | the commit fails, HEAD stays put, the output names `[HISS-08] tools/ci/trivy_coverage.py`, and `.standards-baseline.json` has the same SHA-256 afterwards |

The planted call is assembled at run time, so the tool's source holds no infraction.

## How the proof itself is checked

[`tests/test_prove_hooks.py`](https://github.com/cordanaLLM/imago/blob/main/tests/test_prove_hooks.py) replaces every command with a scripted reply and runs in the normal pytest suite. Each failure mode has its own planted case: a failing check, an accepted commit, a moved HEAD, a refusal without its reason, a changed baseline and a failed setup step.

A clone without active hooks fails as well, at the positive case: the audit reports `.git/hooks/pre-commit is missing or inactive`.
