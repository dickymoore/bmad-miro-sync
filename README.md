# bmad-miro-sync

Reusable BMad-to-Miro synchronization tooling.

This repository is intended to provide:

- A host-neutral sync engine that reads BMad outputs and publishes them to Miro
- A CLI for local and CI usage
- A Codex-friendly wrapper first, with room for other hosts such as Claude Code and Gemini CLI

Planning artifacts live in `_bmad-output/planning-artifacts/`.

## Installation

The intended setup path is the installer command. It writes the local repo config, adds the project-local sync skill, creates a short usage doc, and patches BMad skills by default so artifact-producing workflows invoke the sync path automatically.

Install into a target repo:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync install \
  --project-root /path/to/project \
  --board-url https://miro.com/app/board/your-board-id=/
```

By default, this command patches existing BMad skill headers with the sync policy. To opt out:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync install \
  --project-root /path/to/project \
  --board-url https://miro.com/app/board/your-board-id=/ \
  --no-patch-bmad-skills
```

The installer creates:

- `.bmad-miro.toml`
- `.bmad-miro-auth.json` when repo-local REST auth is configured
- `.agents/skills/bmad-miro-sync/SKILL.md`
- `.agents/skills/bmad-miro-ingest/SKILL.md`
- `.agents/skills/bmad-miro-collaboration/SKILL.md`
- `docs/miro-sync.md`
- `.gitignore` entries for `.bmad-miro-sync/` and `.bmad-miro-auth.json`

And, by default, it patches repo-local `bmad-*` skill headers with the sync policy.

## MVP Status

The current MVP provides:

- artifact discovery from `_bmad-output`
- section-level markdown splitting for more navigable Miro publishing
- artifact classification and deterministic sync planning
- inspectable local publish state persistence to avoid duplicate publishing and preserve retryable partial runs
- host-neutral operation export for MCP-capable hosts
- Codex-oriented instruction rendering
- normalized Miro comment ingestion into BMAD review artifacts
- explicit decision-record generation from normalized review bundles plus operator triage
- deterministic implementation-readiness and handoff generation from canonical decision sidecars

The current implementation supports both host-driven publish via MCP tools and direct REST publish from the Python CLI. The direct CLI path is intended for large bootstrap runs where single-item MCP execution is too slow, and it reconciles results back into `.bmad-miro-sync/state.json` using the same exported runtime plan contract.

## Codex Plugin

A repo-local Codex plugin scaffold is included under [plugins/bmad-miro-sync-codex](/home/codexuser/bmad-miro-sync/plugins/bmad-miro-sync-codex/.codex-plugin/plugin.json:1).

The plugin provides a Codex skill that:

- seeds the repo-local collaboration workflow report
- exports the publish bundle for Codex Miro execution
- resumes the workflow through apply, ingest, triage, and readiness stages
- keeps the full collaboration loop inspectable under `.bmad-miro-sync/run/`

## Configuration

Copy the example config:

```bash
cp .bmad-miro.example.toml .bmad-miro.toml
```

Then set `board_url` to the target Miro board.

Discovery defaults to `source_root`, but you can override it with a dedicated `[discovery]` block:

```toml
[discovery]
source_paths = ["_bmad-output/planning-artifacts", "_bmad-output/implementation-artifacts", "_bmad-output/review-artifacts"]
required_artifact_classes = ["prd", "ux_design", "architecture"]
```

`source_paths` are scanned in order. Keep `_bmad-output/review-artifacts` in the override set if later review bundles such as `decision-records.md` should stay publishable. If both a whole markdown file and a sharded `index.md` variant exist for the same artifact, discovery keeps the whole document and records the skipped shard in the exported plan metadata.

Repeat syncs use a single lifecycle policy for content that disappeared from the source set:

```toml
[sync]
removed_item_policy = "archive" # or "remove"
```

`archive` is the default and keeps the last known Miro identity in local state while planning an archival operation for the host. `remove` plans a deletion/removal operation but still retains the last known mapping and metadata in `.bmad-miro-sync/state.json` for traceability.

Degraded-mode object fallback is explicit and inspectable:

```toml
[object_strategies]
phase_zone = "workstream_anchor" # default: "zone"
story_summary = "doc"            # default: "table"
```

The legacy `layout.create_phase_frames` and `publish.stories_table` booleans still load for backward compatibility, but the exported plan, bundle, runtime results, and local state now record preferred versus resolved item types plus fallback warnings through the object-strategy contract.

Direct REST publish layout is now configurable from `.bmad-miro.toml`:

```toml
[layout]
doc_width = 680
table_width = 840
content_start_y = 260
content_gap_y = 120
fragment_indent_x = 140
fragment_gap_y = 90

[layout.phase_y]
analysis = -1800
planning = -600
solutioning = 600
implementation = 1800

[layout.workstream_x]
general = -2400
product = -1200
ux = 0
architecture = 1200
delivery = 2400

[layout.phase_colors]
analysis = "#d5f692"
planning = "#a6ccf5"
solutioning = "#fff9b1"
implementation = "#ffcee0"
```

Those settings control the lane layout for `publish-direct`: phase rows, workstream columns, scaffold colors, card widths, and vertical spacing for new items. Existing mapped items still preserve their prior Miro positions on update.

## Commands

Build a sync plan:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync plan --project-root . --config .bmad-miro.toml
```

Install into another repo:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync install --project-root /path/to/project --board-url https://miro.com/app/board/your-board-id=/
```

Render Codex-oriented execution instructions:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync render-host-instructions --project-root . --config .bmad-miro.toml --host codex
```

Export a full Codex execution bundle:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync export-codex-bundle --project-root . --config .bmad-miro.toml --output-dir .bmad-miro-sync/run
```

Run the combined Codex-first collaboration workflow:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync run-codex-collaboration-workflow --project-root . --config .bmad-miro.toml --stop-after publish
```

Apply host execution results to the manifest/state file:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync apply-results --project-root . --config .bmad-miro.toml --results .bmad-miro-sync/run/results.json
```

Execute the publish plan directly against the Miro REST API and apply the result when it completes cleanly:

```bash
MIRO_API_TOKEN=... \
PYTHONPATH=src python3 -m bmad_miro_sync publish-direct --project-root . --config .bmad-miro.toml --plan .bmad-miro-sync/run/plan.json --results .bmad-miro-sync/run/results.json --apply-results
```

Set up repo-local Miro REST auth interactively:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync setup-miro-rest-auth --project-root .
```

## REST Token Setup

You do not need `MIRO_API_TOKEN` for every sync.

- Use the Codex Miro MCP path when the publish run is small enough to complete comfortably with MCP item calls.
- Use `publish-direct` only when the run is too large for practical MCP-by-MCP execution, such as an empty-board bootstrap with hundreds of creates.
- Running `install` in an interactive terminal now offers to set up repo-local REST auth for you.

Preferred setup path:

1. Run `PYTHONPATH=src python3 -m bmad_miro_sync setup-miro-rest-auth --project-root .`
2. In your Miro app settings, configure a localhost redirect URI for the CLI flow, for example `http://127.0.0.1:8899/callback`.
3. Run the setup command and paste the Miro app install URL when prompted, or enter the client ID and that localhost redirect URI manually.
4. Enter the client secret.
5. Open the generated install URL in a browser and authorize the app.
6. The setup command captures the localhost callback automatically, exchanges the code, and stores the access token in the gitignored repo-local file `.bmad-miro-auth.json`.

After that, `publish-direct` automatically uses the repo-local auth file. `MIRO_API_TOKEN` is still supported and overrides the repo-local file when set.

Manual setup path if you do not use the helper:

When `publish-direct` is needed, `MIRO_API_TOKEN` must contain a Miro OAuth access token.

To get one for testing:

1. In Miro, create or confirm you have a Developer team.
2. In Miro Settings, open `Your apps`.
3. Create a new app in that Developer team.
4. For a simple local test setup, choose a non-expiring user authorization token when creating the app.
5. Configure the app enough to install it to your Developer team.
6. Use the Miro app install flow to authorize the app and get the OAuth access token.
7. Export that token in the shell where you will run `publish-direct`:

```bash
export MIRO_API_TOKEN='your-miro-oauth-access-token'
```

8. Verify it is present:

```bash
printenv MIRO_API_TOKEN
```

Miro’s official setup docs:

- Quickstart: https://developers.miro.com/docs/rest-api-build-your-first-hello-world-app
- OAuth overview: https://developers.miro.com/reference/overview
- Non-expiring token flow: https://developers.miro.com/reference/authorization-flow-for-expiring-access-tokens

Notes:

- Miro REST API auth uses OAuth access tokens, not a separate static API-key product.
- Non-expiring tokens are simpler for local testing.
- Expiring tokens are better for production, but require refresh-token handling.

Ingest normalized Miro comments into a review artifact:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync ingest-comments --project-root . --config .bmad-miro.toml --comments .bmad-miro-sync/run/comments.json
```

Produce decision records from normalized review input plus explicit triage:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync triage-feedback --project-root . --config .bmad-miro.toml --input .bmad-miro-sync/run/review-input.json
```

Generate readiness summary and handoff outputs from canonical decision data:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync summarize-readiness --project-root . --config .bmad-miro.toml
```

## Host Workflow

1. Run the installed `bmad-miro-collaboration` skill, or run `run-codex-collaboration-workflow --stop-after publish`, to export `plan.json`, `publish-bundle.json`, the backward-compatible `codex-bundle.json` alias, `instructions.md`, `results.template.json`, and `.bmad-miro-sync/run/collaboration-run.json`.
2. Execute the publish plan in a host with Miro MCP access, or use `publish-direct` when `MIRO_API_TOKEN` is available and the run is too large for practical MCP-by-MCP creation.
3. Save execution results as `.bmad-miro-sync/run/results.json` with `run_status`, `executed_at`, optional `warnings` and `object_strategies`, and one item entry per executed operation.
4. Fetch and normalize comments into `.bmad-miro-sync/run/comments.json`.
5. Add triage metadata in `.bmad-miro-sync/run/review-input.json`.
6. Resume `run-codex-collaboration-workflow --start-at apply-results`, typically via the installed `bmad-miro-collaboration` skill, to update `.bmad-miro-sync/state.json`, ingest comments, generate decision records, and generate readiness outputs.

`apply-results` now reads `.bmad-miro-sync/run/plan.json` by default so missing result entries are persisted as explicit pending operations instead of disappearing silently.

The state file keeps:

- `items`: current Miro mappings for created or updated objects
- `operations`: the last reconciled plan with `execution_status` per operation, including archive/remove lifecycle transitions
- `last_run`: the last applied run status, timestamp, pending/executed counts, degraded-mode warnings, and resolved object strategies

Removed or archived content entries stay in `items` with their last known `item_id`, `miro_url`, `content_fingerprint`, and `lifecycle_state` so repeat sync history remains inspectable.

For feedback ingest:

1. Read `.bmad-miro-sync/state.json` to identify synced section items.
2. Fetch and normalize comments from Miro into `comments.json`.
   Preferred normalized comment shape:
   - `artifact_id`: canonical section artifact id from the manifest
   - `section_id`: same stable section identifier as `artifact_id`
   - `source_artifact_id`: parent markdown artifact path
   - `section_title`: human-readable section title
   - `topic`: explicit grouping label; if omitted, ingest falls back to `General feedback`
   - `author`, `created_at`, `body`
   - `published_object_id`, `published_object_type`, `published_object_reference`, `miro_url`
3. Run `ingest-comments` to write `_bmad-output/review-artifacts/miro-comments.md`.
4. The generated review artifact groups feedback by source artifact, section, and topic, while unmatched comments are written to an explicit unresolved-input section instead of being merged silently.
5. Add explicit triage metadata in `.bmad-miro-sync/run/review-input.json` and run `triage-feedback` to write `_bmad-output/review-artifacts/decision-records.md` plus the canonical sidecar `_bmad-output/review-artifacts/decision-records.json`.
   Preferred triage shape:
   - `section_id`, `topic`, `status`, `owner`, and `rationale`
   - optional `source_artifact_id` and `follow_up_notes`
   - approved statuses are `open`, `accepted`, `deferred`, `resolved`, and `blocked`
6. Run `summarize-readiness` to generate `_bmad-output/implementation-artifacts/implementation-readiness.md` and `_bmad-output/implementation-artifacts/implementation-handoff.md`.
7. The generated decision artifact keeps untriaged bundles open by default, preserves unresolved manifest misses as open or blocked only, and renders plain-language status labels for non-technical review.
8. The readiness outputs stay repo-local and auditable: blockers, deferred items, open questions, workstream coverage gaps, and handoff actions are rendered from canonical decision data instead of reparsed markdown transcripts.

Legacy payloads that only provide `artifact_id`, `source_artifact_id`, `section_title`, `author`, `created_at`, `body`, and `miro_url` remain supported for backward compatibility.

The normalized publish contract is host-neutral:

- `plan.json`: canonical sync plan and operation ordering
- `publish-bundle.json`: canonical artifact/discovery/object-strategy export for any host adapter
- `codex-bundle.json`: Codex-compatible alias that mirrors `publish-bundle.json`
- `instructions.md`: host-specific execution guidance rendered on top of the shared plan/bundle
- `results.template.json`: normalized execution-results contract consumed by `apply-results`

This flow is designed for Codex first, but the same plan, bundle, and results handshake can be used by Claude Code, Gemini CLI, or other environments that can execute Miro MCP operations without reimplementing the core planning rules.
