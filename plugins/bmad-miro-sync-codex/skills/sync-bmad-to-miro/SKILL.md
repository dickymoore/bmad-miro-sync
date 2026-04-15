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
   - `<repo-root>/.bmad-miro-sync/run/codex-bundle.json`
   - `<repo-root>/.bmad-miro-sync/run/instructions.md`

4. Execute the operations in order using Codex Miro tools:
   - `ensure_frame` -> ensure the phase frame exists or create a suitable frame container
   - `create_doc` / `update_doc` -> create or update one Miro doc per exported markdown section
   - `create_table` / `update_table` -> create or update a Miro table using the supplied columns and rows
   - `skip` -> do nothing

5. Record the Miro execution results in `<repo-root>/.bmad-miro-sync/run/results.json` using this shape:

```json
{
  "items": [
    {
      "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
      "artifact_sha256": "<sha256 from plan artifact>",
      "item_type": "doc",
      "item_id": "<miro item id>",
      "miro_url": "<full miro item url>",
      "title": "PRD / Overview",
      "target_key": "section:_bmad-output/planning-artifacts/prd.md#overview",
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "heading_level": 0,
      "parent_artifact_id": null,
      "updated_at": "2026-04-14T15:00:00Z"
    }
  ]
}
```

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
- If an operation cannot be performed cleanly, stop and report the blocker instead of fabricating a result
