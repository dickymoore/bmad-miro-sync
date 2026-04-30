# Source-Ledger Implementation Plan

Status as of 2026-04-27:

- phase 1 implemented locally
- source-status ledger implemented locally
- initial phase-2 publish filters implemented locally:
  - `publish-direct --source`
  - `publish-direct --changed-only`
  - `publish-direct --source-status`

## Goal

Shift sync UX from low-level publish operations to BMAD source artifacts:

- publish per BMAD output file
- know which source files are in sync with Miro
- resume safely by source
- keep section-level Miro mapping underneath

## Core Principle

- Source file is the operator unit.
- Section artifact is the execution unit.
- Source-level state is derived from section-level truth plus source hash.

## New Data Model

Add a new repo-local ledger:

- `.bmad-miro-sync/source-status.json`

Shape:

```json
{
  "version": 1,
  "sources": {
    "_bmad-output/planning-artifacts/prd.md": {
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "relative_path": "_bmad-output/planning-artifacts/prd.md",
      "artifact_class": "prd",
      "source_sha256": "...",
      "source_modified_at": "2026-04-27T11:00:00Z",
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

Status enum:

- `not_published`
- `partially_published`
- `published`
- `out_of_date`
- `failed`

## Status Rules

For each `source_artifact_id`:

- `published`
  - all active planned sections for that source exist in manifest
  - all are successfully applied
  - `published_source_sha256 == source_sha256`
- `out_of_date`
  - source exists
  - source hash changed since last full successful publish
- `partially_published`
  - some sections for current source hash published, some pending
- `failed`
  - last attempt for current source hash had one or more failed sections
- `not_published`
  - no successful published sections recorded for current source

Precedence:

- `failed` > `partially_published` > `out_of_date` > `published` > `not_published`

## Source Hash

Use a source-level hash, not file mtime, as the main freshness key.

Definition:

- hash of the full discovered source document content before section splitting
- if raw whole-file content is not already exposed, derive it from concatenating all section artifact content in deterministic order

## Changes By File

### `src/bmad_miro_sync/models.py`

Add:

- `SourceGroup`
- `SourcePublishStatus`
- `SourceStatusLedger`

Also extend `SyncPlan`:

- add `source_groups: list[SourceGroup]`

### `src/bmad_miro_sync/planner.py`

Add source grouping after operations are built:

- group all content artifacts by `source_artifact_id`
- map operations to sources
- create `SourceGroup` list
- attach to `plan.source_groups`

Constraints:

- derive artifact class from `artifact.kind`
- preserve deterministic ordering by first section occurrence
- exclude orientation-only synthetic sources such as `zone:*` and `workstream:*`

### `src/bmad_miro_sync/manifest.py`

Keep section-level state as is.

Add helper APIs only if needed:

- get active items by `source_artifact_id`
- do not merge source ledger into the main manifest yet

### `src/bmad_miro_sync/source_status.py`

Implement:

- `load_source_status(project_root, path=".bmad-miro-sync/source-status.json")`
- `save_source_status(project_root, ledger, path=...)`
- `build_source_groups(plan_dict_or_plan)`
- `build_source_status_ledger(plan_dict, manifest, results=None)`
- `source_status_for_group(...)`

Internal helpers:

- `_source_sha256_for_artifacts(artifacts_for_source)`
- `_group_artifacts_by_source(...)`
- `_group_operations_by_source(...)`
- `_status_from_counts(...)`

### `src/bmad_miro_sync/cli.py`

Add new command:

```bash
python3 -m bmad_miro_sync source-status --project-root . --config .bmad-miro.toml
```

Behavior:

- load config
- build current plan
- load manifest
- load existing source ledger if present
- compute current source statuses
- print JSON to stdout
- persist updated ledger

### `tests/test_planner.py`

Add:

- `test_plan_emits_source_groups_for_real_bmad_sources`
- `test_source_group_uses_deterministic_section_order`
- `test_split_sections_roll_up_under_single_source_group`

### `tests/test_source_status.py`

Add cases:

- source not published
- source fully published
- source partially published
- source out of date after content change
- source failed when a result entry for that source has `execution_status = failed`

### `tests/test_cli.py`

Add:

- `test_source_status_command_outputs_grouped_source_state`
- `test_source_status_command_writes_repo_local_source_ledger`

## CLI Spec

New command:

```bash
python3 -m bmad_miro_sync source-status \
  --project-root . \
  --config .bmad-miro.toml
```

Output:

```json
{
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

## Filtering Semantics

Later source-scoped publish should include:

- all content operations for the selected source
- any required scaffold operations for referenced phase/workstream if not already satisfied in manifest

## Resume Semantics

If a source partially published:

- source ledger marks `partially_published` or `failed`
- resume should target only the incomplete sections for that source
- already successful sections should not be republished unless the source hash changed

## Testing Plan

1. Unit tests for source status computation.
2. Planner tests for source grouping.
3. Manifest and ledger reconciliation tests for partial source publishes.
4. CLI tests for source-status output and ledger persistence.

## Implementation Order

### Phase 1

- add `source_status.py`
- add source grouping in plan
- add `source-status` command

### Phase 2

- add `publish-direct` source filtering
- add `--changed-only`

### Phase 3

- update ledger after publish and apply
- add failed and partial resume behavior

### Phase 4

- patch installed skills and docs
- make source-scoped publish the default sync path

## Acceptance Criteria

- `plan.json` includes source group metadata
- `source-status` shows one entry per BMAD output source file
- source state distinguishes:
  - `not_published`
  - `published`
  - `partially_published`
  - `out_of_date`
  - `failed`
- split oversized sections still map to one logical source file
- no regression in existing plan, export, or apply behavior
