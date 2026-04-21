---
name: sync-bmad-to-miro
description: Export a section-based bmad-miro-sync plan bundle, execute it against Miro with Codex MCP tools, and persist sync results back into the repo manifest.
---

# Sync BMad To Miro

Use this skill when the user wants Codex to publish a BMad repo into Miro using `bmad-miro-sync`.

## Preconditions

- The target repo contains `.bmad-miro.toml` or another TOML config for `bmad-miro-sync`
- Codex has access to Miro MCP tools in the current session
- The repo has the Python package available locally

## Workflow

1. Confirm the target repo root and config path.
2. Export a Codex bundle:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync export-codex-bundle \
  --project-root <repo-root> \
  --config <repo-root>/.bmad-miro.toml \
  --output-dir <repo-root>/.bmad-miro-sync/run
```

3. Read:
   - `<repo-root>/.bmad-miro-sync/run/plan.json`
   - `<repo-root>/.bmad-miro-sync/run/publish-bundle.json`
   - `<repo-root>/.bmad-miro-sync/run/codex-bundle.json`
   - `<repo-root>/.bmad-miro-sync/run/instructions.md`

`publish-bundle.json` is the host-neutral publish contract. `codex-bundle.json` is a backward-compatible alias for the Codex workflow.

4. Execute the operations in order using Codex Miro tools:
   - `ensure_zone` -> ensure the phase-zone container exists or create the best available board-level equivalent
   - `ensure_workstream_anchor` -> ensure the workstream anchor/container exists inside its phase zone
   - `create_doc` / `update_doc` -> create or update one Miro doc per exported markdown section
   - `create_table` / `update_table` -> create or update a Miro table using the supplied columns and rows
   - `skip` -> do nothing

If the exported plan includes `ensure_zone` operations but the current Miro tools cannot create board-level containers, do not ask the user whether to do a partial sync. Instead:

1. update `<repo-root>/.bmad-miro.toml` so `[object_strategies].phase_zone = "workstream_anchor"`
2. rerun the export command
3. continue from the regenerated plan

Only use a partial sync when the user explicitly asks for one.

5. Record the Miro execution results in `<repo-root>/.bmad-miro-sync/run/results.json` using this shape:

```json
{
  "run_status": "complete",
  "executed_at": "2026-04-17T22:40:00Z",
  "items": [
    {
      "op_id": "doc:_bmad-output/planning-artifacts/prd.md#overview",
      "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
      "artifact_sha256": "<sha256 from plan artifact; null for zone/workstream scaffolding>",
      "item_type": "doc",
      "item_id": "<miro item id>",
      "miro_url": "<full miro item url>",
      "title": "PRD / Overview",
      "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#overview",
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "phase_zone": "planning",
      "workstream": "product",
      "collaboration_intent": "anchor",
      "container_target_key": "workstream:planning:product",
      "heading_level": 0,
      "parent_artifact_id": null,
      "section_path": ["overview"],
      "section_title_path": ["Overview"],
      "section_slug": "overview",
      "section_sibling_index": 1,
      "lineage_key": "<stable lineage key>",
      "lineage_status": "new",
      "previous_artifact_id": null,
      "previous_parent_artifact_id": null,
      "execution_status": "created",
      "error": null,
      "updated_at": "2026-04-14T15:00:00Z"
    }
  ]
}
```

If only part of the plan executes, set `"run_status": "partial"` and include only the operations that actually ran. `apply-results` will keep the rest marked pending in `.bmad-miro-sync/state.json`.

6. Apply the results:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync apply-results \
  --project-root <repo-root> \
  --config <repo-root>/.bmad-miro.toml \
  --results <repo-root>/.bmad-miro-sync/run/results.json
```

## Rules

- Treat local BMad artifacts as source of truth
- Preserve manual Miro positioning and workflow grouping when updating existing section items
- Do not duplicate Miro items when an existing mapping is available
- Preserve `target_key` exactly as emitted by the plan
- When an operation exports `degraded = true`, execute `resolved_item_type` and preserve the fallback metadata in the result entry
- If an operation cannot be performed cleanly, stop and report the blocker instead of fabricating a result
