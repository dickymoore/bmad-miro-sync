# Source-Ledger Implementation Handoff

Date: 2026-04-27

## Purpose

This note is the implementation handoff for the source-ledger work so it survives context compaction.

It captures:

- the problem being solved
- the approved design
- the exact files to change
- the current implementation state
- the next concrete implementation steps
- the test plan

## Current Status

Phase 1 and the first phase-2 publish filters are now implemented locally and verified with targeted tests.

Completed local changes:

- `src/bmad_miro_sync/models.py`
  - added `SourceGroup`
  - added `SourcePublishStatus`
  - added `SourceStatusLedger`
  - extended `SyncPlan` with `source_groups`
- `src/bmad_miro_sync/planner.py`
  - now emits `plan.source_groups`
  - computes deterministic source-level hashes from ordered section artifacts
- `src/bmad_miro_sync/source_status.py`
  - new source ledger/status module
- `src/bmad_miro_sync/cli.py`
  - new `source-status` command
  - new `publish-direct` source filters:
    - `--source`
    - `--changed-only`
    - `--source-status`
- `src/bmad_miro_sync/installer.py`
  - now writes BMAD-native workflow overrides under `_bmad/custom/`
  - no longer relies on patching generated BMAD skill markdown
- `src/bmad_miro_sync/templates.py`
  - now renders BMAD workflow customization overrides
  - docs updated to describe BMAD-native integration
- `tests/test_planner.py`
  - source-group coverage added
- `tests/test_source_status.py`
  - new source-status coverage
- `tests/test_cli.py`
  - new CLI coverage for `source-status`
  - new CLI coverage for source-scoped publish
- `tests/test_installer.py`
  - installer coverage updated for `_bmad/custom/*.toml`

Verification already run:

```bash
python3 -m py_compile src/bmad_miro_sync/models.py src/bmad_miro_sync/planner.py src/bmad_miro_sync/source_status.py src/bmad_miro_sync/cli.py tests/test_planner.py tests/test_source_status.py tests/test_cli.py
PYTHONPATH=src python3 -m unittest tests.test_planner tests.test_source_status tests.test_cli
PYTHONPATH=src python3 -m unittest tests.test_installer
```

Result:

- `84` tests passed

## Problem Statement

The current sync system is execution-centric:

- operators see low-level publish operations
- MCP-limited runs are hard to resume safely
- the system does not answer "which BMAD output files are in sync with Miro?"

The desired model is source-centric:

- treat each BMAD output file as the operator unit
- keep section-level publish under the hood
- track whether a source file is published, failed, partially published, or out of date

## Approved Design

### Operator Unit

- `source_artifact_id` is the operator unit
- this maps to one BMAD output file
- one source file can still expand into many section artifacts

### Execution Unit

- section artifact remains the execution unit
- one Miro item per exported markdown section stays unchanged

### New Repo-Local Ledger

Create:

- `.bmad-miro-sync/source-status.json`

This is separate from:

- `.bmad-miro-sync/state.json`

Reason:

- `state.json` remains the canonical section-level manifest
- `source-status.json` is a higher-level derived ledger for operator UX

### Source Status Values

- `not_published`
- `partially_published`
- `published`
- `out_of_date`
- `failed`

Precedence:

- `failed` > `partially_published` > `out_of_date` > `published` > `not_published`

### Source Hash

Use a source-level content hash as the freshness key.

For phase 1, derive it from:

- all section artifact `sha256` values for the same `source_artifact_id`
- concatenated in deterministic section order
- then hashed again

Do not use file mtime as the primary freshness mechanism.

## Data Model To Add

In `src/bmad_miro_sync/models.py`:

- `SourceGroup`
- `SourcePublishStatus`
- `SourceStatusLedger`

Also extend `SyncPlan`:

- add `source_groups: list[SourceGroup]`

## Files To Change

### 1. `src/bmad_miro_sync/models.py`

Status:

- done locally

### 2. `src/bmad_miro_sync/planner.py`

Status:

- done locally

Implementation shape:

- group artifacts by `source_artifact_id`
- collect:
  - `relative_path`
  - `artifact.kind` as `artifact_class`
  - unique `phase_zones`
  - unique `workstreams`
  - `section_artifact_ids`
  - matching operation ids
  - source hash
  - pending operation count

### 3. `src/bmad_miro_sync/source_status.py`

Status:

- done locally

Implemented:

- `load_source_status(...)`
- `save_source_status(...)`
- `build_source_groups(...)`
- `build_source_status_ledger(...)`
- `source_status_for_group(...)`

Helpers:

- `_source_sha256_for_artifacts(...)`
- `_group_artifacts_by_source(...)`
- `_group_operations_by_source(...)`
- `_status_from_counts(...)`

### 4. `src/bmad_miro_sync/cli.py`

Status:

- done locally

Added command:

```bash
python3 -m bmad_miro_sync source-status --project-root . --config .bmad-miro.toml
```

Behavior:

- load config
- build current plan
- load manifest
- load existing source ledger if present
- compute current source statuses
- write `.bmad-miro-sync/source-status.json`
- print JSON to stdout

### 5. `tests/test_planner.py`

Status:

- done locally

Added:

- source groups emitted for real BMAD source files
- split sections roll up under one source group
- source group ordering is deterministic

### 6. `tests/test_source_status.py`

Status:

- done locally

Added tests for:

- `not_published`
- `published`
- `partially_published`
- `out_of_date`
- `failed`

### 7. `tests/test_cli.py`

Status:

- done locally

Added:

- `source-status` command output test
- ledger write test

## Current Local Repo State

Current local uncommitted changes are:

- `src/bmad_miro_sync/cli.py`
- `src/bmad_miro_sync/models.py`
- `src/bmad_miro_sync/planner.py`
- `src/bmad_miro_sync/source_status.py`
- `tests/test_cli.py`
- `tests/test_planner.py`
- `tests/test_source_status.py`
- `_bmad-output/planning-artifacts/source-ledger-implementation-plan.md`
- this handoff file

Nothing has been committed yet for this phase.

## Exact Next Steps

1. Review and commit the phase 1 source-ledger changes
2. Start phase 2:
   - `publish-direct --source`
   - `publish-direct --changed-only`
   - source-level resume semantics
3. Reinstall and validate the BMAD-native override flow in a real target repo such as `fluidscan`
4. Consider source-level resume affordances beyond raw status filtering

Current verification command:

```bash
PYTHONPATH=src python3 -m unittest tests.test_planner tests.test_source_status tests.test_cli
```

## Phase 1 Rules

- Do not replace section-level manifest behavior
- Do not add source-scoped publish filtering yet
- Do not add `--changed-only` yet
- Do not patch BMAD skills yet
- Do not infer source success from file existence alone

Phase 1 remains read-model and status only.

## Source Status Computation Rules

For a current plan source group:

- `derived_section_count`
  - number of section artifacts in the group
- `published_section_count`
  - number of matching active manifest items for the current section artifact ids
- `failed_section_count`
  - number of results entries for this source with `execution_status == "failed"`
- `pending_section_count`
  - derived minus published minus failed, bounded at zero

Status:

- if any failed result for the source in the current run:
  - `failed`
- else if all sections published and stored published hash matches current source hash:
  - `published`
- else if some sections published and some pending:
  - `partially_published`
- else if stored published hash exists and differs from current source hash:
  - `out_of_date`
- else:
  - `not_published`

## Output Shape For `source-status`

Suggested stdout shape:

```json
{
  "version": 1,
  "sources": [
    {
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "status": "out_of_date",
      "derived_section_count": 12,
      "published_section_count": 10,
      "pending_section_count": 2,
      "last_successful_publish_at": "2026-04-26T18:00:00Z"
    }
  ]
}
```

Suggested ledger-on-disk shape:

```json
{
  "version": 1,
  "sources": {
    "_bmad-output/planning-artifacts/prd.md": {
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "relative_path": "_bmad-output/planning-artifacts/prd.md",
      "artifact_class": "prd",
      "source_sha256": "...",
      "published_source_sha256": "...",
      "status": "published",
      "derived_section_count": 12,
      "published_section_count": 12,
      "failed_section_count": 0,
      "pending_section_count": 0,
      "section_artifact_ids": [
        "_bmad-output/planning-artifacts/prd.md#prd",
        "_bmad-output/planning-artifacts/prd.md#prd/goals"
      ],
      "last_successful_publish_at": "2026-04-27T11:05:00Z",
      "last_attempted_publish_at": "2026-04-27T11:05:00Z",
      "last_failed_publish_at": null,
      "last_error": null
    }
  }
}
```

## Relevant Existing Files

These are the most relevant existing files for phase 1:

- `src/bmad_miro_sync/models.py`
- `src/bmad_miro_sync/planner.py`
- `src/bmad_miro_sync/cli.py`
- `src/bmad_miro_sync/manifest.py`
- `tests/test_planner.py`
- `tests/test_cli.py`

Useful context files:

- `src/bmad_miro_sync/config.py`
- `src/bmad_miro_sync/host_exports.py`

## Phase 2 Preview

After phase 1 lands, phase 2 should add:

- `publish-direct --source <source_artifact_id>`
- `publish-direct --changed-only`
- resume by failed or partial source

That work should consume the same `source_groups` and `source-status.json` introduced in phase 1.
