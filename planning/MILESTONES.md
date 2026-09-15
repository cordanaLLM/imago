# cordanaLLM/imago fleet migration Milestones

Status: draft proposal; structurally valid; review required. Source provenance is caller-asserted and unverified.

- Plan: `plan-imago-fleet-migration`
- Project: `project-cordanallm-imago`
- Digest: `33f52c838ab10089395ed1fb191ba964684403ef4f1bfa3c69c31caed1d8166d`
- Canonical data: [plan.json](plan.json)

Unsupported in this proposal:

- existing-ledger compare-and-swap apply
- source-adapter byte verification
- step execution and completion evidence

<a id="milestone-6d732d6964656e74697479"></a>
## ms\-identity

**Identity and module path** — The Go module, CLI, MCP server, documentation, tests and CI refer to cordanaLLM/imago and the imago binary.

Dependencies: none

### Acceptance proposal

- Positive:
  - go build ./... and go test ./... pass under the module path github.com/cordanaLLM/imago.

- Negative:
  - No production file references the lusoris\-forge binary or the old module path.

- Boundary:
  - Historical CHANGELOG entries keep the old names verbatim.

Linked steps:

- [`step-rename-module`](ROADMAP.md#roadmap-726f61646d61702d72656e616d652d6d6f64756c65) / TODO [`todo-rename-module`](TODO.md#todo-746f646f2d72656e616d652d6d6f64756c65)
- [`step-rename-docs`](ROADMAP.md#roadmap-726f61646d61702d72656e616d652d646f6373) / TODO [`todo-rename-docs`](TODO.md#todo-746f646f2d72656e616d652d646f6373)

<a id="milestone-6d732d676f6c75736f726973"></a>
## ms\-golusoris

**Golusoris core composition** — The CLI, logger, clock and MCP transport are provided by golusoris core and the remaining demand is declared in .needs.yaml.

Dependencies: `ms-identity`

### Acceptance proposal

- Positive:
  - praetorctl needs report shows every third\-party dependency covered or declared as a retained non\-goal.

- Negative:
  - No production Go file imports the raw MCP SDK, tint, or calls time.Now\(\).

- Boundary:
  - Tests may import the SDK to drive in\-memory transports.

Linked steps:

- [`step-core-cli-log`](ROADMAP.md#roadmap-726f61646d61702d636f72652d636c692d6c6f67) / TODO [`todo-core-cli-log`](TODO.md#todo-746f646f2d636f72652d636c692d6c6f67)
- [`step-core-clock`](ROADMAP.md#roadmap-726f61646d61702d636f72652d636c6f636b) / TODO [`todo-core-clock`](TODO.md#todo-746f646f2d636f72652d636c6f636b)
- [`step-core-mcp`](ROADMAP.md#roadmap-726f61646d61702d636f72652d6d6370) / TODO [`todo-core-mcp`](TODO.md#todo-746f646f2d636f72652d6d6370)
- [`step-needs-manifest`](ROADMAP.md#roadmap-726f61646d61702d6e656564732d6d616e6966657374) / TODO [`todo-needs-manifest`](TODO.md#todo-746f646f2d6e656564732d6d616e6966657374)

<a id="milestone-6d732d706c616e6e696e67"></a>
## ms\-planning

**Routed planning graph** — planning/ holds the compiled praetor draft, the routing overlay, and imago plan route returns the ranked ready set.

Dependencies: none

### Acceptance proposal

- Positive:
  - praetorctl planning prepare recompiles plan.json to the committed digest.

- Negative:
  - A dependency cycle or an overlay that omits a step fails imago plan validate.

- Boundary:
  - A plan at the 512\-step limit routes; one step over is rejected.

Linked steps:

- [`step-plan-graph`](ROADMAP.md#roadmap-726f61646d61702d706c616e2d6772617068) / TODO [`todo-plan-graph`](TODO.md#todo-746f646f2d706c616e2d6772617068)
- [`step-plan-router`](ROADMAP.md#roadmap-726f61646d61702d706c616e2d726f75746572) / TODO [`todo-plan-router`](TODO.md#todo-746f646f2d706c616e2d726f75746572)
- [`step-epics-projection`](ROADMAP.md#roadmap-726f61646d61702d65706963732d70726f6a656374696f6e) / TODO [`todo-epics-projection`](TODO.md#todo-746f646f2d65706963732d70726f6a656374696f6e)

<a id="milestone-6d732d70726165746f72"></a>
## ms\-praetor

**Praetor governance adopted** — The repository carries .standards.yaml, .standards.lock, a recorded HISS baseline, compiled vendor context, lefthook gates and make verify\-all.

Dependencies: `ms-identity`

### Acceptance proposal

- Positive:
  - praetorctl audit and compile\-context \-\-verify pass on a fresh checkout.

- Negative:
  - A hand edit to CLAUDE.md fails the pre\-commit gate.

- Boundary:
  - The recorded baseline never grows; touched legacy files must be clean.

Linked steps:

- [`step-praetor-windows-defect`](ROADMAP.md#roadmap-726f61646d61702d70726165746f722d77696e646f77732d646566656374) / TODO [`todo-praetor-windows-defect`](TODO.md#todo-746f646f2d70726165746f722d77696e646f77732d646566656374)
- [`step-python-gate`](ROADMAP.md#roadmap-726f61646d61702d707974686f6e2d67617465) / TODO [`todo-python-gate`](TODO.md#todo-746f646f2d707974686f6e2d67617465)
- [`step-adopt-praetor`](ROADMAP.md#roadmap-726f61646d61702d61646f70742d70726165746f72) / TODO [`todo-adopt-praetor`](TODO.md#todo-746f646f2d61646f70742d70726165746f72)
- [`step-lefthook-verify`](ROADMAP.md#roadmap-726f61646d61702d6c656674686f6f6b2d766572696679) / TODO [`todo-lefthook-verify`](TODO.md#todo-746f646f2d6c656674686f6f6b2d766572696679)

<a id="milestone-6d732d617070"></a>
## ms\-app

**Application hardening after gates** — Legacy HISS infractions and defects surfaced by the gates are fixed and the baseline ratchets to zero.

Dependencies: `ms-praetor`

### Acceptance proposal

- Positive:
  - praetorctl audit reports zero baseline infractions.

- Negative:
  - A new infraction fails the gate instead of being baselined.

- Boundary:
  - Functions at exactly 60 lines pass; 61 fail.

Linked steps:

- [`step-app-hardening`](ROADMAP.md#roadmap-726f61646d61702d6170702d68617264656e696e67) / TODO [`todo-app-hardening`](TODO.md#todo-746f646f2d6170702d68617264656e696e67)

<a id="milestone-6d732d617263686574797065"></a>
## ms\-archetype

**os\-image archetype upstream** — praetor ships an os\-image archetype and this repository declares it instead of gitops\-infra.

Dependencies: `ms-praetor`

### Acceptance proposal

- Positive:
  - praetorctl adopt \-\-profile os\-image resolves the pinned catalog without overrides.

- Negative:
  - gitops\-infra\-only linters \(kubeconform, tflint\) are no longer declared.

- Boundary:
  - The complexity bound stays at 60 lines per function.

Linked steps:

- [`step-archetype-draft`](ROADMAP.md#roadmap-726f61646d61702d6172636865747970652d6472616674) / TODO [`todo-archetype-draft`](TODO.md#todo-746f646f2d6172636865747970652d6472616674)
- [`step-archetype-upstream`](ROADMAP.md#roadmap-726f61646d61702d6172636865747970652d757073747265616d) / TODO [`todo-archetype-upstream`](TODO.md#todo-746f646f2d6172636865747970652d757073747265616d)
- [`step-archetype-switch`](ROADMAP.md#roadmap-726f61646d61702d6172636865747970652d737769746368) / TODO [`todo-archetype-switch`](TODO.md#todo-746f646f2d6172636865747970652d737769746368)

<a id="milestone-6d732d7472616e73666572"></a>
## ms\-transfer

**Repository transferred to cordanaLLM/imago** — github.com/cordanaLLM/imago resolves, mirrors and release automation point at it, and the fleet topology lists it.

Dependencies: `ms-golusoris`, `ms-praetor`

### Acceptance proposal

- Positive:
  - git ls\-remote \-\-heads https://github.com/cordanaLLM/imago.git returns main.

- Negative:
  - release\-please and Renovate do not open PRs against the old identity.

- Boundary:
  - Old links redirect; none are rewritten in historical records.

Linked steps:

- [`step-create-repo`](ROADMAP.md#roadmap-726f61646d61702d6372656174652d7265706f) / TODO [`todo-create-repo`](TODO.md#todo-746f646f2d6372656174652d7265706f)
- [`step-redirects`](ROADMAP.md#roadmap-726f61646d61702d726564697265637473) / TODO [`todo-redirects`](TODO.md#todo-746f646f2d726564697265637473)

<a id="milestone-6d732d6165676973"></a>
## ms\-aegis

**Aegis product\-input contract pinned** — One local request/result pair against the Aegis M18 schema is retained with positive, negative and boundary results.

Dependencies: `ms-transfer`

### Acceptance proposal

- Positive:
  - An accepted aegis.p01.product\-input.v1 request returns image digest, signature reference and boot\-evidence fields.

- Negative:
  - A malformed manifest is rejected with a correlated error.

- Boundary:
  - A retry at the declared bound is recorded; one above is refused.

Linked steps:

- [`step-aegis-schema-pin`](ROADMAP.md#roadmap-726f61646d61702d61656769732d736368656d612d70696e) / TODO [`todo-aegis-schema-pin`](TODO.md#todo-746f646f2d61656769732d736368656d612d70696e)
- [`step-aegis-pair`](ROADMAP.md#roadmap-726f61646d61702d61656769732d70616972) / TODO [`todo-aegis-pair`](TODO.md#todo-746f646f2d61656769732d70616972)

<a id="milestone-6d732d6e75636c657573"></a>
## ms\-nucleus

**Nucleus kernel contract** — Kernel artifacts from lusoris\-kernel\-forge \(future cordanaLLM/nucleus\) are consumed through a pinned requirement and artifact digest contract.

Dependencies: `ms-transfer`

### Acceptance proposal

- Positive:
  - A pinned kernel artifact digest is verified before an image build consumes it.

- Negative:
  - An unsatisfiable kernel feature requirement is rejected with a correlated error.

- Boundary:
  - An empty requirement list is rejected explicitly.

Linked steps:

- [`step-nucleus-contract`](ROADMAP.md#roadmap-726f61646d61702d6e75636c6575732d636f6e7472616374) / TODO [`todo-nucleus-contract`](TODO.md#todo-746f646f2d6e75636c6575732d636f6e7472616374)

