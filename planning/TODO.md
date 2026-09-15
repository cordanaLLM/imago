# cordanaLLM/imago fleet migration TODO

Status: draft proposal; structurally valid; review required. Source provenance is caller-asserted and unverified.

- Plan: `plan-imago-fleet-migration`
- Project: `project-cordanallm-imago`
- Digest: `b2701894e9166d9953da00dd7276d4e20399b21a8126938443eaad4650d0b524`
- Canonical data: [plan.json](plan.json)

Unsupported in this proposal:

- existing-ledger compare-and-swap apply
- source-adapter byte verification
- step execution and completion evidence

<a id="todo-746f646f2d72656e616d652d6d6f64756c65"></a>
- [ ] `todo-rename-module` — **Rename the Go module and CLI to imago** (`step-rename-module`)
  - Roadmap: [`roadmap-rename-module`](ROADMAP.md#roadmap-726f61646d61702d72656e616d652d6d6f64756c65); milestone: [`ms-identity`](MILESTONES.md#milestone-6d732d6964656e74697479)
  - Requirements: `req-identity`; dependencies: none
<a id="todo-746f646f2d72656e616d652d646f6373"></a>
- [ ] `todo-rename-docs` — **Rename the CLI in documentation and governance text** (`step-rename-docs`)
  - Roadmap: [`roadmap-rename-docs`](ROADMAP.md#roadmap-726f61646d61702d72656e616d652d646f6373); milestone: [`ms-identity`](MILESTONES.md#milestone-6d732d6964656e74697479)
  - Requirements: `req-identity`; dependencies: `step-rename-module`
<a id="todo-746f646f2d636f72652d636c692d6c6f67"></a>
- [ ] `todo-core-cli-log` — **Compose the CLI with clikit and core/log** (`step-core-cli-log`)
  - Roadmap: [`roadmap-core-cli-log`](ROADMAP.md#roadmap-726f61646d61702d636f72652d636c692d6c6f67); milestone: [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973)
  - Requirements: `req-golusoris-core`; dependencies: `step-rename-module`
<a id="todo-746f646f2d636f72652d636c6f636b"></a>
- [ ] `todo-core-clock` — **Inject core/clock into the builder and staging guard** (`step-core-clock`)
  - Roadmap: [`roadmap-core-clock`](ROADMAP.md#roadmap-726f61646d61702d636f72652d636c6f636b); milestone: [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973)
  - Requirements: `req-golusoris-core`; dependencies: `step-rename-module`
<a id="todo-746f646f2d636f72652d6d6370"></a>
- [ ] `todo-core-mcp` — **Run the MCP server on core/mcp** (`step-core-mcp`)
  - Roadmap: [`roadmap-core-mcp`](ROADMAP.md#roadmap-726f61646d61702d636f72652d6d6370); milestone: [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973)
  - Requirements: `req-golusoris-core`; dependencies: `step-core-cli-log`, `step-core-clock`
<a id="todo-746f646f2d6e656564732d6d616e6966657374"></a>
- [ ] `todo-needs-manifest` — **Declare framework demand in .needs.yaml** (`step-needs-manifest`)
  - Roadmap: [`roadmap-needs-manifest`](ROADMAP.md#roadmap-726f61646d61702d6e656564732d6d616e6966657374); milestone: [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973)
  - Requirements: `req-golusoris-core`, `req-praetor-governance`; dependencies: `step-core-mcp`
<a id="todo-746f646f2d706c616e2d6772617068"></a>
- [ ] `todo-plan-graph` — **Author and compile the planning graph** (`step-plan-graph`)
  - Roadmap: [`roadmap-plan-graph`](ROADMAP.md#roadmap-726f61646d61702d706c616e2d6772617068); milestone: [`ms-planning`](MILESTONES.md#milestone-6d732d706c616e6e696e67)
  - Requirements: `req-routed-graph`; dependencies: none
<a id="todo-746f646f2d706c616e2d726f75746572"></a>
- [ ] `todo-plan-router` — **Route the graph from the CLI and MCP** (`step-plan-router`)
  - Roadmap: [`roadmap-plan-router`](ROADMAP.md#roadmap-726f61646d61702d706c616e2d726f75746572); milestone: [`ms-planning`](MILESTONES.md#milestone-6d732d706c616e6e696e67)
  - Requirements: `req-routed-graph`; dependencies: none
<a id="todo-746f646f2d65706963732d70726f6a656374696f6e"></a>
- [ ] `todo-epics-projection` — **Reconcile cadence epics with the graph** (`step-epics-projection`)
  - Roadmap: [`roadmap-epics-projection`](ROADMAP.md#roadmap-726f61646d61702d65706963732d70726f6a656374696f6e); milestone: [`ms-planning`](MILESTONES.md#milestone-6d732d706c616e6e696e67)
  - Requirements: `req-routed-graph`; dependencies: `step-plan-router`
<a id="todo-746f646f2d70726165746f722d77696e646f77732d646566656374"></a>
- [ ] `todo-praetor-windows-defect` — **Report the praetor Windows path\-separator defect** (`step-praetor-windows-defect`)
  - Roadmap: [`roadmap-praetor-windows-defect`](ROADMAP.md#roadmap-726f61646d61702d70726165746f722d77696e646f77732d646566656374); milestone: [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72)
  - Requirements: `req-praetor-governance`; dependencies: none
<a id="todo-746f646f2d707974686f6e2d67617465"></a>
- [ ] `todo-python-gate` — **Select the Python test gate explicitly** (`step-python-gate`)
  - Roadmap: [`roadmap-python-gate`](ROADMAP.md#roadmap-726f61646d61702d707974686f6e2d67617465); milestone: [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72)
  - Requirements: `req-praetor-governance`; dependencies: none
<a id="todo-746f646f2d61646f70742d70726165746f72"></a>
- [ ] `todo-adopt-praetor` — **Apply praetor adoption with the interim profile** (`step-adopt-praetor`)
  - Roadmap: [`roadmap-adopt-praetor`](ROADMAP.md#roadmap-726f61646d61702d61646f70742d70726165746f72); milestone: [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72)
  - Requirements: `req-os-image-archetype`, `req-praetor-governance`; dependencies: `step-python-gate`, `step-rename-docs`
<a id="todo-746f646f2d6c656674686f6f6b2d766572696679"></a>
- [ ] `todo-lefthook-verify` — **Prove the lefthook and verify\-all gates** (`step-lefthook-verify`)
  - Roadmap: [`roadmap-lefthook-verify`](ROADMAP.md#roadmap-726f61646d61702d6c656674686f6f6b2d766572696679); milestone: [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72)
  - Requirements: `req-praetor-governance`; dependencies: `step-adopt-praetor`
<a id="todo-746f646f2d6170702d68617264656e696e67"></a>
- [ ] `todo-app-hardening` — **Fix defects surfaced by the gates and ratchet the baseline** (`step-app-hardening`)
  - Roadmap: [`roadmap-app-hardening`](ROADMAP.md#roadmap-726f61646d61702d6170702d68617264656e696e67); milestone: [`ms-app`](MILESTONES.md#milestone-6d732d617070)
  - Requirements: `req-app-hardening`; dependencies: `step-lefthook-verify`
<a id="todo-746f646f2d6172636865747970652d6472616674"></a>
- [ ] `todo-archetype-draft` — **Draft the os\-image archetype** (`step-archetype-draft`)
  - Roadmap: [`roadmap-archetype-draft`](ROADMAP.md#roadmap-726f61646d61702d6172636865747970652d6472616674); milestone: [`ms-archetype`](MILESTONES.md#milestone-6d732d617263686574797065)
  - Requirements: `req-os-image-archetype`; dependencies: none
<a id="todo-746f646f2d6172636865747970652d757073747265616d"></a>
- [ ] `todo-archetype-upstream` — **Propose the os\-image archetype upstream** (`step-archetype-upstream`)
  - Roadmap: [`roadmap-archetype-upstream`](ROADMAP.md#roadmap-726f61646d61702d6172636865747970652d757073747265616d); milestone: [`ms-archetype`](MILESTONES.md#milestone-6d732d617263686574797065)
  - Requirements: `req-os-image-archetype`; dependencies: `step-archetype-draft`
<a id="todo-746f646f2d6172636865747970652d737769746368"></a>
- [ ] `todo-archetype-switch` — **Switch the manifest to os\-image** (`step-archetype-switch`)
  - Roadmap: [`roadmap-archetype-switch`](ROADMAP.md#roadmap-726f61646d61702d6172636865747970652d737769746368); milestone: [`ms-archetype`](MILESTONES.md#milestone-6d732d617263686574797065)
  - Requirements: `req-os-image-archetype`; dependencies: `step-adopt-praetor`, `step-archetype-upstream`
<a id="todo-746f646f2d6372656174652d7265706f"></a>
- [ ] `todo-create-repo` — **Create cordanaLLM/imago and enrol it in the fleet** (`step-create-repo`)
  - Roadmap: [`roadmap-create-repo`](ROADMAP.md#roadmap-726f61646d61702d6372656174652d7265706f); milestone: [`ms-transfer`](MILESTONES.md#milestone-6d732d7472616e73666572)
  - Requirements: `req-identity`, `req-praetor-governance`; dependencies: `step-adopt-praetor`, `step-core-mcp`
<a id="todo-746f646f2d726564697265637473"></a>
- [ ] `todo-redirects` — **Repoint automation and links after transfer** (`step-redirects`)
  - Roadmap: [`roadmap-redirects`](ROADMAP.md#roadmap-726f61646d61702d726564697265637473); milestone: [`ms-transfer`](MILESTONES.md#milestone-6d732d7472616e73666572)
  - Requirements: `req-identity`; dependencies: `step-create-repo`
<a id="todo-746f646f2d61656769732d736368656d612d70696e"></a>
- [ ] `todo-aegis-schema-pin` — **Accept the Aegis product\-input schema** (`step-aegis-schema-pin`)
  - Roadmap: [`roadmap-aegis-schema-pin`](ROADMAP.md#roadmap-726f61646d61702d61656769732d736368656d612d70696e); milestone: [`ms-aegis`](MILESTONES.md#milestone-6d732d6165676973)
  - Requirements: `req-aegis-contract`; dependencies: `step-create-repo`
<a id="todo-746f646f2d61656769732d70616972"></a>
- [ ] `todo-aegis-pair` — **Retain one local request/result pair with Aegis** (`step-aegis-pair`)
  - Roadmap: [`roadmap-aegis-pair`](ROADMAP.md#roadmap-726f61646d61702d61656769732d70616972); milestone: [`ms-aegis`](MILESTONES.md#milestone-6d732d6165676973)
  - Requirements: `req-aegis-contract`; dependencies: `step-aegis-schema-pin`
<a id="todo-746f646f2d6e75636c6575732d636f6e7472616374"></a>
- [ ] `todo-nucleus-contract` — **Pin the kernel artifact contract with nucleus** (`step-nucleus-contract`)
  - Roadmap: [`roadmap-nucleus-contract`](ROADMAP.md#roadmap-726f61646d61702d6e75636c6575732d636f6e7472616374); milestone: [`ms-nucleus`](MILESTONES.md#milestone-6d732d6e75636c657573)
  - Requirements: `req-nucleus-contract`; dependencies: `step-create-repo`
