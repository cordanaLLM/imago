# cordanaLLM/imago fleet migration Roadmap

Status: draft proposal; structurally valid; review required. Source provenance is caller-asserted and unverified.

- Plan: `plan-imago-fleet-migration`
- Project: `project-cordanallm-imago`
- Digest: `b2701894e9166d9953da00dd7276d4e20399b21a8126938443eaad4650d0b524`
- Canonical data: [plan.json](plan.json)

Unsupported in this proposal:

- existing-ledger compare-and-swap apply
- source-adapter byte verification
- step execution and completion evidence

## Requirements

- `req-aegis-contract` (`proposed`): Imago consumes the Aegis product input manifest and returns image digest, signature reference and boot\-evidence fields; malformed manifests are rejected with a correlated error and retries are bounded.
  - Caller-asserted unverified source `source-aegis-roadmap` sha256 `938fdabd137d1f76598646b782f14ce31f1fa70f4d0cfac5a1aa0df431e726c6`: The M18 schemas are proposed to cordanaLLM/imago and cordanaLLM/nucleus; acceptance is recorded only when each producer consumes the payload, not a fixed symbol list
- `req-app-hardening` (`proposed`): Application defects and legacy HISS infractions surfaced by the governance gates are fixed once lefthook and make verify\-all run green.
  - Caller-asserted unverified source `source-operator-decisions` sha256 `a4c0b06c2a0bdf0391e236d9f88eb7a3be2295d045fea64808524136a2431f2c`: Application defects surfaced by the governance gates are fixed after lefthook and \`make verify\-all\` run green.
- `req-golusoris-core` (`proposed`): Go code composes golusoris core capabilities \(clikit, log, clock, mcp\) instead of duplicating them, and declares its remaining demand against the framework capability contract.
  - Caller-asserted unverified source `source-golusoris-adr-0019` sha256 `86224ec6144c6197564cbee7621cb0acf0b0c018f3207d1a66b39b8854f517ca`: Every Go repository in the fleet is meant to deduplicate onto golusoris
  - Caller-asserted unverified source `source-golusoris-capabilities` sha256 `60afffcc7d2f2c38ca680acab3194603022be36f7873810d11fb4e6a04b176c5`: Downstream governance \(cordanallm/praetor: needs scan \| report \| migrate\) resolves .needs.yaml demands against this file
- `req-identity` (`proposed`): The repository is addressable as cordanaLLM/imago, the reusable image builder the Aegis\-OS connected stack contract names.
  - Caller-asserted unverified source `source-aegis-stack` sha256 `8d40bdc6886cac60cc253fe1b08c0593aa56ef47896b95ae2f7ade375c652c7d`: Reusable image construction, kernel consumption, image artifact production
  - Caller-asserted unverified source `source-operator-decisions` sha256 `a4c0b06c2a0bdf0391e236d9f88eb7a3be2295d045fea64808524136a2431f2c`: The repository targets the identity \`cordanaLLM/imago\`.
- `req-nucleus-contract` (`proposed`): Kernel artifacts are consumed from cordanaLLM/nucleus \(today lusoris/lusoris\-kernel\-forge\) through a pinned kernel requirement and artifact contract.
  - Caller-asserted unverified source `source-aegis-stack` sha256 `8d40bdc6886cac60cc253fe1b08c0593aa56ef47896b95ae2f7ade375c652c7d`: Kernel configuration, patch selection, kernel artifact production
- `req-os-image-archetype` (`proposed`): An os\-image praetor archetype describes OS image forges; until praetor ships it the repository declares the interim gitops\-infra profile.
  - Caller-asserted unverified source `source-operator-decisions` sha256 `a4c0b06c2a0bdf0391e236d9f88eb7a3be2295d045fea64808524136a2431f2c`: Praetor governance is adopted now with the interim profile \`gitops\-infra\`; an \`os\-image\` archetype is drafted here and proposed upstream, and the manifest switches to it once praetor ships it.
- `req-praetor-governance` (`proposed`): The repository is praetor\-governed: declarative .standards.yaml, HISS\-16 harness compiled from one AGENTS.md, lefthook gates, a .needs.yaml demand declaration, and participation in fleet demand sweeps.
  - Caller-asserted unverified source `source-praetor-adr-0003` sha256 `87d821c526a4a4804baa6f8ae3b0d52344bd2989da6ea82f03988a2ae5d58d09`: Praetor serves as the universal governance engine and repository\-as\-code standard for the Cordana ecosystem.
  - Caller-asserted unverified source `source-praetor-adr-0007` sha256 `9ad3affade5960f65eb5d37ceb067af41ad54daf7bab893192ce73f38fbf3414`: Requires downstream repositories to define \`.needs.yaml\` and participate in periodic fleet demand sweeps.
- `req-routed-graph` (`proposed`): Migration work is tracked as a typed dependency graph compiled by praetor and routed by unblock value per cost, with the ready set available to the CLI and to agents over MCP.
  - Caller-asserted unverified source `source-aegis-roadmap` sha256 `938fdabd137d1f76598646b782f14ce31f1fa70f4d0cfac5a1aa0df431e726c6`: Cross\-repository contract pin: one local request/result pair
  - Caller-asserted unverified source `source-operator-decisions` sha256 `a4c0b06c2a0bdf0391e236d9f88eb7a3be2295d045fea64808524136a2431f2c`: The migration is tracked as a typed dependency graph under \`planning/\`, compiled with praetor&\#39;s planning compiler and routed by \`imago plan route\`.

<a id="roadmap-726f61646d61702d72656e616d652d6d6f64756c65"></a>
## roadmap\-rename\-module

Step `step-rename-module`; TODO [`todo-rename-module`](TODO.md#todo-746f646f2d72656e616d652d6d6f64756c65); milestone [`ms-identity`](MILESTONES.md#milestone-6d732d6964656e74697479).

Move the module path to github.com/cordanaLLM/imago and the command to cmd/imago; rename the binary in Makefile, CI, .gitignore and Python tests.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Rewrite import paths across cmd and pkg.
2. Rename build targets, workflow steps and test binary paths.

### Expected outputs

- `output-module-rename`: go.mod, cmd/imago and every import compile under the new path.

### Acceptance proposal

- Positive:
  - go build ./... succeeds.

- Negative:
  - grep finds no github.com/lusoris/lusoris\-cloud\-images import.

- Boundary:
  - The Go version directive follows golusoris core \(1.27.1\).

<a id="roadmap-726f61646d61702d72656e616d652d646f6373"></a>
## roadmap\-rename\-docs

Step `step-rename-docs`; TODO [`todo-rename-docs`](TODO.md#todo-746f646f2d72656e616d652d646f6373); milestone [`ms-identity`](MILESTONES.md#milestone-6d732d6964656e74697479).

Update the CLI reference, principles, standards, maintainers and README diagram to the imago name and identity.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Replace lusoris\-forge in docs/tools/cli\-mcp.md and related pages.
2. Add the target identity notice to README.md and docs/index.md.

### Expected outputs

- `output-docs-rename`: Documentation names imago and cordanaLLM/imago consistently.

### Acceptance proposal

- Positive:
  - pytest tests/test\_docs.py passes.

- Negative:
  - No user\-facing page instructs running lusoris\-forge.

- Boundary:
  - CHANGELOG history entries are untouched.

<a id="roadmap-726f61646d61702d636f72652d636c692d6c6f67"></a>
## roadmap\-core\-cli\-log

Step `step-core-cli-log`; TODO [`todo-core-cli-log`](TODO.md#todo-746f646f2d636f72652d636c692d6c6f67); milestone [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973).

Build the root command with golusoris clikit and replace the tint handler with core/log.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Replace the cobra root with clikit.New and clikit.Command.
2. Set the default slog logger from core/log.New.

### Expected outputs

- `output-cli-core`: cmd/imago/main.go imports clikit and core/log and no longer imports tint.

### Acceptance proposal

- Positive:
  - imago \-\-help lists every command.

- Negative:
  - tint is not a direct import of any production file.

- Boundary:
  - Command help text is unchanged for existing commands.

<a id="roadmap-726f61646d61702d636f72652d636c6f636b"></a>
## roadmap\-core\-clock

Step `step-core-clock`; TODO [`todo-core-clock`](TODO.md#todo-746f646f2d636f72652d636c6f636b); milestone [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973).

Thread an injected clock through builder.Request and the two\-phase Stager so time is testable and time.Now is not called in production code.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Add a Clock field to builder.Request and reject requests without one.
2. Construct the Stager with a clock and drive TTL tests with a fake clock.

### Expected outputs

- `output-clock`: No time.Now\(\) call remains outside tests.

### Acceptance proposal

- Positive:
  - Builder and staging tests pass with clock.NewFake\(\).

- Negative:
  - Dispatch without a clock returns an error.

- Boundary:
  - Advancing the fake clock exactly past the TTL prunes the staged action.

<a id="roadmap-726f61646d61702d636f72652d6d6370"></a>
## roadmap\-core\-mcp

Step `step-core-mcp`; TODO [`todo-core-mcp`](TODO.md#todo-746f646f2d636f72652d6d6370); milestone [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973).

Register imago tools on the golusoris core/mcp server through fx and delete the duplicated stdout\-purity guard and transport runner.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Expose RegisterTools\(server, deps\) and wire it with fx.Invoke under coremcp.Module.
2. Remove pkg/mcp/stdout.go and RunStdio; add the http transport flag.

### Expected outputs

- `output-core-mcp`: pkg/mcp imports only core/mcp in production code; tests drive in\-memory transports.

### Acceptance proposal

- Positive:
  - The protocol test lists 14 tools and executes them over an in\-memory transport.

- Negative:
  - RegisterTools with a nil stager or clock returns an error.

- Boundary:
  - Client disconnect on stdio ends the process through fx.Shutdowner.

<a id="roadmap-726f61646d61702d6e656564732d6d616e6966657374"></a>
## roadmap\-needs\-manifest

Step `step-needs-manifest`; TODO [`todo-needs-manifest`](TODO.md#todo-746f646f2d6e656564732d6d616e6966657374); milestone [`ms-golusoris`](MILESTONES.md#milestone-6d732d676f6c75736f726973).

Generate .needs.yaml with praetorctl needs scan against the golusoris capability contract and declare testify as a retained non\-goal.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Run praetorctl needs scan \-\-write on the migrated module.
2. Record the testify retention note referencing praetor issue \#34.

### Expected outputs

- `output-needs`: .needs.yaml lists every third\-party dependency with its capability and replacement.

### Acceptance proposal

- Positive:
  - praetorctl needs report shows 100% mapping availability.

- Negative:
  - A dependency without a capability key fails the scan.

- Boundary:
  - Standard\-library slog stays excluded from third\-party counts.

<a id="roadmap-726f61646d61702d706c616e2d6772617068"></a>
## roadmap\-plan\-graph

Step `step-plan-graph`; TODO [`todo-plan-graph`](TODO.md#todo-746f646f2d706c616e2d6772617068); milestone [`ms-planning`](MILESTONES.md#milestone-6d732d706c616e6e696e67).

Write planning/plan.json as a praetor schema\-1 draft citing the fleet sources, compile it with praetorctl planning prepare, and commit the projections.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Cite each source by SHA\-256 and quote it verbatim.
2. Compile into a new directory and copy plan.json, TODO.md, ROADMAP.md and MILESTONES.md back.

### Expected outputs

- `output-plan-graph`: planning/ holds the canonical draft and three cross\-linked projections with one digest.

### Acceptance proposal

- Positive:
  - A second compile produces the same digest.

- Negative:
  - An unknown requirement reference is rejected by the compiler.

- Boundary:
  - Every step names between 1 and 32 requirements.

<a id="roadmap-726f61646d61702d706c616e2d726f75746572"></a>
## roadmap\-plan\-router

Step `step-plan-router`; TODO [`todo-plan-router`](TODO.md#todo-746f646f2d706c616e2d726f75746572); milestone [`ms-planning`](MILESTONES.md#milestone-6d732d706c616e6e696e67).

Implement pkg/planning with DAG validation, a routing overlay, and ranking by \(1 \+ transitive unblocks\) / cost; expose imago plan route and the route\_plan MCP tool.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Load and validate plan.json and routing.json with bounded reads.
2. Rank ready local work first and expose the result through CLI and MCP.

### Expected outputs

- `output-plan-router`: imago plan route prints the ranked table; route\_plan returns the same JSON.

### Acceptance proposal

- Positive:
  - The ready set is ordered by score with deterministic tie breaks.

- Negative:
  - A cycle, an unknown cost or a missing overlay entry fails validation.

- Boundary:
  - A plan over 512 KiB is rejected before decoding.

<a id="roadmap-726f61646d61702d65706963732d70726f6a656374696f6e"></a>
## roadmap\-epics\-projection

Step `step-epics-projection`; TODO [`todo-epics-projection`](TODO.md#todo-746f646f2d65706963732d70726f6a656374696f6e); milestone [`ms-planning`](MILESTONES.md#milestone-6d732d706c616e6e696e67).

Keep .github/epics.json for recurring cadence work and document how one\-off graph steps relate to epics and milestones.

Kind: `manual`; status: `proposed`. Actions are inert instructions.

### Actions

1. Review each epic for overlap with graph steps.
2. Record the division of authority in docs/tools/planning\-graph.md.

### Expected outputs

- `output-epics-projection`: Epics and the graph have documented, non\-overlapping authority.

### Acceptance proposal

- Positive:
  - imago lint validates epics.json and imago plan validate validates the graph.

- Negative:
  - No epic duplicates a graph step.

- Boundary:
  - Milestones referenced by PR metadata remain valid.

<a id="roadmap-726f61646d61702d70726165746f722d77696e646f77732d646566656374"></a>
## roadmap\-praetor\-windows\-defect

Step `step-praetor-windows-defect`; TODO [`todo-praetor-windows-defect`](TODO.md#todo-746f646f2d70726165746f722d77696e646f77732d646566656374); milestone [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72).

File the adopt failure \(catalog artifact path compared against a slash\-separated constant in internal/config/catalog\_projection.go\) upstream with the reproduction.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Open the issue in cordanallm/praetor with the failing command and the one\-line fix.
2. Link the issue from this plan&\#39;s routing evidence.

### Expected outputs

- `output-windows-issue`: An upstream issue tracks the defect.

### Acceptance proposal

- Positive:
  - praetorctl adopt \-\-dry\-run succeeds on Windows after the upstream fix.

- Negative:
  - The defect is not patched by a local fork.

- Boundary:
  - Both the profiles and facets directories are compared with slash normalisation.

<a id="roadmap-726f61646d61702d707974686f6e2d67617465"></a>
## roadmap\-python\-gate

Step `step-python-gate`; TODO [`todo-python-gate`](TODO.md#todo-746f646f2d707974686f6e2d67617465); milestone [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72).

Move pytest configuration to pytest.ini so praetor&\#39;s project verification identifies the runnable Python gate.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Create pytest.ini with the former pyproject options.
2. Remove the duplicate section from pyproject.toml.

### Expected outputs

- `output-pytest-ini`: pytest.ini is the single pytest configuration.

### Acceptance proposal

- Positive:
  - pytest tests/ passes with the moved configuration.

- Negative:
  - praetorctl adopt no longer warns that project verification is unavailable.

- Boundary:
  - Strict marker enforcement is preserved.

<a id="roadmap-726f61646d61702d61646f70742d70726165746f72"></a>
## roadmap\-adopt\-praetor

Step `step-adopt-praetor`; TODO [`todo-adopt-praetor`](TODO.md#todo-746f646f2d61646f70742d70726165746f72); milestone [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72).

Run praetorctl adopt with profile gitops\-infra and facets security:high, agent:sandboxed, docs:seo\-portal; set the repository identity to cordanaLLM/imago; record the HISS baseline.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Apply the adoption from a reviewed praetor source bundle and review every reconciled file.
2. Merge the harness into AGENTS.md and compile the vendor context.

### Expected outputs

- `output-adoption`: .standards.yaml, .standards.lock, .standards\-baseline.json, lefthook.yml and compiled vendor context are committed.

### Acceptance proposal

- Positive:
  - praetorctl audit passes against the recorded baseline.

- Negative:
  - compile\-context \-\-verify fails on a hand\-edited CLAUDE.md.

- Boundary:
  - The baseline records exactly the infractions the dry run reported.

<a id="roadmap-726f61646d61702d6c656674686f6f6b2d766572696679"></a>
## roadmap\-lefthook\-verify

Step `step-lefthook-verify`; TODO [`todo-lefthook-verify`](TODO.md#todo-746f646f2d6c656674686f6f6b2d766572696679); milestone [`ms-praetor`](MILESTONES.md#milestone-6d732d70726165746f72).

Install lefthook on a Linux workstation or the generated devcontainer and run the pre\-commit and pre\-push jobs plus make verify\-all on a clean checkout.

Kind: `manual`; status: `proposed`. Actions are inert instructions.

### Actions

1. Run lefthook install and lefthook run pre\-commit.
2. Run make verify\-all and retain the output as evidence.

### Expected outputs

- `output-gates-green`: Retained gate output showing every job executed and passed.

### Acceptance proposal

- Positive:
  - All lefthook jobs and make verify\-all exit 0.

- Negative:
  - A \-\-no\-verify commit is blocked by the anti\-evasion hook.

- Boundary:
  - A docs\-only change skips the heavy suites through the diff\-aware filter.

<a id="roadmap-726f61646d61702d6170702d68617264656e696e67"></a>
## roadmap\-app\-hardening

Step `step-app-hardening`; TODO [`todo-app-hardening`](TODO.md#todo-746f646f2d6170702d68617264656e696e67); milestone [`ms-app`](MILESTONES.md#milestone-6d732d617070).

Resolve the recorded HISS\-02, HISS\-04 and HISS\-07 infractions and any application defects the lefthook gates or verify\-all surface.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Refactor each baselined function below the complexity bound and wrap unchecked errors.
2. Re\-record the baseline only downward.

### Expected outputs

- `output-hardening`: The baseline reaches zero recorded infractions.

### Acceptance proposal

- Positive:
  - praetorctl audit reports zero infractions.

- Negative:
  - A touched legacy file with a remaining infraction fails the gate.

- Boundary:
  - A function at exactly 60 lines passes.

<a id="roadmap-726f61646d61702d6172636865747970652d6472616674"></a>
## roadmap\-archetype\-draft

Step `step-archetype-draft`; TODO [`todo-archetype-draft`](TODO.md#todo-746f646f2d6172636865747970652d6472616674); milestone [`ms-archetype`](MILESTONES.md#milestone-6d732d617263686574797065).

Write planning/archetypes/os\-image.yaml following praetor&\#39;s archetype authoring guide with the image\-forge linters and the 60\-line complexity bound.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Define id, runtime, complexity, supply chain, linters and devcontainer features.
2. Document why gitops\-infra is the interim profile.

### Expected outputs

- `output-archetype-draft`: A complete archetype YAML ready for an upstream pull request.

### Acceptance proposal

- Positive:
  - The YAML parses with praetor&\#39;s profile schema.

- Negative:
  - No container\-image\-only linter is declared.

- Boundary:
  - max\_func\_loc is exactly 60.

<a id="roadmap-726f61646d61702d6172636865747970652d757073747265616d"></a>
## roadmap\-archetype\-upstream

Step `step-archetype-upstream`; TODO [`todo-archetype-upstream`](TODO.md#todo-746f646f2d6172636865747970652d757073747265616d); milestone [`ms-archetype`](MILESTONES.md#milestone-6d732d617263686574797065).

Open the praetor issue and pull request adding .config/archetypes/os\-image.yaml and a flavor detection rule for Packer and mkosi repositories.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. File the archetype request with the drafted YAML and the flavor misdetection evidence.
2. Submit the pull request once praetor maintainers accept the request.

### Expected outputs

- `output-archetype-upstream`: An upstream issue and pull request exist for the archetype.

### Acceptance proposal

- Positive:
  - praetor main contains .config/archetypes/os\-image.yaml.

- Negative:
  - A Packer repository is no longer detected as python\-ml.

- Boundary:
  - The archetype passes praetor&\#39;s own catalog tests.

<a id="roadmap-726f61646d61702d6172636865747970652d737769746368"></a>
## roadmap\-archetype\-switch

Step `step-archetype-switch`; TODO [`todo-archetype-switch`](TODO.md#todo-746f646f2d6172636865747970652d737769746368); milestone [`ms-archetype`](MILESTONES.md#milestone-6d732d617263686574797065).

Once praetor ships the archetype, change .standards.yaml from gitops\-infra to os\-image, regenerate the lock and baseline, and drop unused linter declarations.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Run praetorctl adopt \-\-profile os\-image with the updated source bundle.
2. Re\-record the baseline and verify the gates.

### Expected outputs

- `output-archetype-switch`: .standards.yaml declares os\-image with a matching lock.

### Acceptance proposal

- Positive:
  - praetorctl audit passes under os\-image.

- Negative:
  - The lock rejects a profile that is not in the pinned catalog.

- Boundary:
  - Baseline count does not increase across the switch.

<a id="roadmap-726f61646d61702d6372656174652d7265706f"></a>
## roadmap\-create\-repo

Step `step-create-repo`; TODO [`todo-create-repo`](TODO.md#todo-746f646f2d6372656174652d7265706f); milestone [`ms-transfer`](MILESTONES.md#milestone-6d732d7472616e73666572).

Transfer or mirror the repository to cordanaLLM/imago, then list it under the os\-image archetype in the operational fork&\#39;s .config/fleet\-topology.yaml.

Kind: `manual`; status: `proposed`. Actions are inert instructions.

### Actions

1. Transfer the GitHub repository to the cordanaLLM organisation as imago.
2. Add the repository to the fleet topology in lusoris/praetor and run praetorctl harvest.

### Expected outputs

- `output-repo`: https://github.com/cordanaLLM/imago resolves and the fleet topology lists it.

### Acceptance proposal

- Positive:
  - git ls\-remote \-\-heads returns main for the new identity.

- Negative:
  - The old identity is a redirect, not a second live repository.

- Boundary:
  - Branch rulesets from .github/rulesets apply on the transferred repository.

<a id="roadmap-726f61646d61702d726564697265637473"></a>
## roadmap\-redirects

Step `step-redirects`; TODO [`todo-redirects`](TODO.md#todo-746f646f2d726564697265637473); milestone [`ms-transfer`](MILESTONES.md#milestone-6d732d7472616e73666572).

Update remotes, badges, release\-please configuration, documentation portal URL, Renovate and the kernel\-forge dispatch target to the new identity.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Replace lusoris/lusoris\-cloud\-images URLs in badges, mkdocs site\_url and workflows.
2. Update the lusoris\-kernel\-forge repository\_dispatch target.

### Expected outputs

- `output-redirects`: Automation and links reference cordanaLLM/imago directly.

### Acceptance proposal

- Positive:
  - release\-please opens its next PR against cordanaLLM/imago.

- Negative:
  - No workflow dispatches to the old identity.

- Boundary:
  - Historical CHANGELOG links are left as redirects.

<a id="roadmap-726f61646d61702d61656769732d736368656d612d70696e"></a>
## roadmap\-aegis\-schema\-pin

Step `step-aegis-schema-pin`; TODO [`todo-aegis-schema-pin`](TODO.md#todo-746f646f2d61656769732d736368656d612d70696e); milestone [`ms-aegis`](MILESTONES.md#milestone-6d732d6165676973).

Implement acceptance of aegis.p01.product\-input.v1 \(distribution snapshot, repart, sysupdate and mkosi definitions, correlation id, exact revision, bounded retries\) as an imago build request.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Add a typed decoder for the manifest with strict unknown\-field rejection.
2. Map the manifest to a build request and return a correlated error for malformed input.

### Expected outputs

- `output-aegis-schema`: imago validates the Aegis manifest and reports correlated errors.

### Acceptance proposal

- Positive:
  - The Aegis build/product\-input.json fixture is accepted.

- Negative:
  - A manifest without a correlation id is rejected.

- Boundary:
  - A retry count at the bound is accepted; one above is refused.

<a id="roadmap-726f61646d61702d61656769732d70616972"></a>
## roadmap\-aegis\-pair

Step `step-aegis-pair`; TODO [`todo-aegis-pair`](TODO.md#todo-746f646f2d61656769732d70616972); milestone [`ms-aegis`](MILESTONES.md#milestone-6d732d6165676973).

Execute the Aegis M09 request/result pair against pinned local checkouts and retain positive, negative and boundary results with image digest, signature reference and boot\-evidence fields.

Kind: `manual`; status: `proposed`. Actions are inert instructions.

### Actions

1. Run the pair with the Aegis fixtures and record the correlation ids and revisions.
2. Hand the result schema back to Aegis for its M09 evidence.

### Expected outputs

- `output-aegis-pair`: Retained request/result evidence referenced by both repositories.

### Acceptance proposal

- Positive:
  - The result carries digest, signature reference and boot\-evidence fields.

- Negative:
  - Simulated output is refused as a result.

- Boundary:
  - An empty requirement list is rejected explicitly.

<a id="roadmap-726f61646d61702d6e75636c6575732d636f6e7472616374"></a>
## roadmap\-nucleus\-contract

Step `step-nucleus-contract`; TODO [`todo-nucleus-contract`](TODO.md#todo-746f646f2d6e75636c6575732d636f6e7472616374); milestone [`ms-nucleus`](MILESTONES.md#milestone-6d732d6e75636c657573).

Replace the repository\_dispatch kernel sync with a pinned contract: kernel version, config digest, artifact digest and provenance verified before an image build consumes the artifact.

Kind: `implementation`; status: `proposed`. Actions are inert instructions.

### Actions

1. Define the kernel artifact manifest imago consumes and verify its digest and provenance.
2. Consume the Aegis kernel\-requirement payload shape rather than a fixed symbol list.

### Expected outputs

- `output-nucleus-contract`: Kernel artifacts enter image builds only through the verified manifest.

### Acceptance proposal

- Positive:
  - A pinned artifact with a valid digest is consumed.

- Negative:
  - A tampered artifact digest is rejected.

- Boundary:
  - An empty kernel requirement list is rejected explicitly.

