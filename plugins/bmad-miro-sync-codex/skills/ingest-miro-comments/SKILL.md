---
name: ingest-miro-comments
description: Fetch normalized comments for synced Miro sections and write them into a BMAD review artifact.
---

# Ingest Miro Comments

Use this skill when stakeholders have commented on synced Miro section items and the feedback should be brought back into the repo.

## Preconditions

- The target repo contains `.bmad-miro.toml`
- The repo has a populated `.bmad-miro-sync/state.json`
- Codex has access to Miro MCP tools in the current session

## Workflow

1. Read the repo manifest at `<repo-root>/.bmad-miro-sync/state.json`.
2. Identify the mapped section items relevant to the user's request.
3. Fetch comments for those mapped Miro items with Codex Miro tools.
4. Normalize the results into `<repo-root>/.bmad-miro-sync/run/comments.json` using:

```json
{
  "comments": [
    {
      "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
      "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "section_title": "PRD / Goals",
      "topic": "Acceptance criteria",
      "author": "Jane Doe",
      "created_at": "2026-04-15T11:00:00Z",
      "body": "Please expand the acceptance criteria.",
      "published_object_id": "doc-123",
      "published_object_type": "doc",
      "published_object_reference": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
      "miro_url": "https://miro.com/app/board/.../?moveToWidget=doc-123"
    }
  ]
}
```

Legacy payloads that only include `artifact_id`, `source_artifact_id`, `section_title`, `author`, `created_at`, `body`, and `miro_url` still work, but the preferred shape above keeps section and published-object traceability intact.

5. Run:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync ingest-comments \
  --project-root <repo-root> \
  --config <repo-root>/.bmad-miro.toml \
  --comments <repo-root>/.bmad-miro-sync/run/comments.json
```

6. When the workflow needs explicit decision records, create `<repo-root>/.bmad-miro-sync/run/review-input.json` with the normalized `comments` payload plus a `triage` list. Each triage entry must include:

- `section_id`
- `topic`
- `status`
- `owner`
- `rationale`

Approved statuses are `open`, `accepted`, `deferred`, `resolved`, and `blocked`.

7. Run:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync triage-feedback \
  --project-root <repo-root> \
  --config <repo-root>/.bmad-miro.toml \
  --input <repo-root>/.bmad-miro-sync/run/review-input.json
```

## Rules

- Do not edit source artifacts directly from comment text.
- Preserve `artifact_id` exactly so comments stay attached to the right markdown section.
- Preserve topic, author, timestamp, and published-object traceability when normalizing comments.
- Keep untriaged bundles visibly open; do not infer accepted or resolved states from raw comment prose.
- Report the generated markdown review artifact path at the end.
