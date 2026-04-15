from __future__ import annotations

from pathlib import Path


SYNC_POLICY_HEADER = """## BMad Miro Sync Policy

If this skill creates or updates `_bmad-output` artifacts or other stakeholder-facing project documentation, invoke `bmad-miro-auto-sync` before considering the workflow complete unless the user explicitly says not to sync. If the sync fails, report the blocker clearly.
"""


def render_config(board_url: str) -> str:
    return f"""board_url = "{board_url}"
source_root = "_bmad-output"
manifest_path = ".bmad-miro-sync/state.json"

[layout]
create_phase_frames = true

[publish]
analysis = true
planning = true
solutioning = true
implementation = true
stories_table = true
"""


def render_skill(project_root: str, sync_src: str, config_path: str, runtime_dir: str, project_name: str) -> str:
    return f"""---
name: bmad-miro-auto-sync
description: Export the {project_name} BMad-to-Miro bundle, execute section-level sync with Codex Miro tools, and apply the results back into the local sync manifest.
---

# BMad Miro Auto Sync

Use this skill whenever {project_name} BMad artifacts should be pushed into the shared Miro board.

## Purpose

This skill is the project-local automation wrapper for the external `bmad-miro-sync` repo. It is intended to be used:

- after any BMad step that writes or changes `_bmad-output`
- when the user says to sync BMad outputs to Miro
- when stakeholders need the latest project state reflected in Miro

## Repo-Specific Settings

- Project root: `{project_root}`
- Sync package source: `{sync_src}`
- Sync config: `{config_path}`
- Runtime directory: `{runtime_dir}`

## Workflow

1. Export the Codex bundle:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync export-codex-bundle \\
  --project-root {project_root} \\
  --config {config_path} \\
  --output-dir {runtime_dir}
```

2. Read:

- `{runtime_dir}/plan.json`
- `{runtime_dir}/codex-bundle.json`
- `{runtime_dir}/instructions.md`

3. Execute the plan in order with Codex Miro tools:

- `ensure_frame`
- `create_doc`
- `update_doc`
- `create_table`
- `update_table`
- `skip`

4. Write:

- `{runtime_dir}/results.json`

The JSON shape must match the template in:

- `{runtime_dir}/results.template.json`

5. Apply the results:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync apply-results \\
  --project-root {project_root} \\
  --config {config_path} \\
  --results {runtime_dir}/results.json
```

## Rules

- Treat `_bmad-output` as the source of truth
- Sync one Miro item per exported markdown section rather than one item per source file
- Preserve `target_key` exactly
- Preserve existing Miro item positions and manual workflow grouping when updating content
- Do not fabricate successful results if a Miro operation fails
- Prefer updating an existing mapped item over creating a duplicate
- At the end, report which Miro items were created or updated

## Expected Use

The intended operating pattern is:

1. Run a BMad artifact-producing skill
2. Immediately run `bmad-miro-auto-sync`

For {project_name}, this is the practical automatic sync path inside Codex because Codex can both execute the local bundle and call the Miro MCP tools in the same session.
"""


def render_comment_ingest_skill(project_root: str, sync_src: str, config_path: str, runtime_dir: str, project_name: str) -> str:
    comments_path = f"{runtime_dir}/comments.json"
    return f"""---
name: bmad-ingest-miro-comments
description: Fetch normalized Miro comments for synced {project_name} sections and write them into a BMAD review artifact.
---

# BMad Ingest Miro Comments

Use this skill when stakeholders have added comments in Miro and those comments should be brought back into the repo as review input.

## Repo-Specific Settings

- Project root: `{project_root}`
- Sync package source: `{sync_src}`
- Sync config: `{config_path}`
- Runtime directory: `{runtime_dir}`

## Expected Input

Create `{comments_path}` with this JSON shape:

```json
{{
  "comments": [
    {{
      "artifact_id": "_bmad-output/planning-artifacts/prd.md#goals",
      "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
      "section_title": "PRD / Goals",
      "author": "Jane Doe",
      "created_at": "2026-04-15T11:00:00Z",
      "body": "Please expand the acceptance criteria.",
      "miro_url": "https://miro.com/app/board/..."
    }}
  ]
}}
```

## Workflow

1. Read `.bmad-miro-sync/state.json` to identify synced section items.
2. Use Codex Miro tools to fetch comments for the mapped section items the user cares about.
3. Normalize those comments into `{comments_path}` using the JSON shape above.
4. Run:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync ingest-comments \\
  --project-root {project_root} \\
  --config {config_path} \\
  --comments {comments_path}
```

## Rules

- Do not modify `_bmad-output` source artifacts directly from Miro comments.
- Write comments into the generated review artifact and report the output path.
- Preserve `artifact_id` exactly so comments stay attached to the right markdown section.
"""


def render_doc(project_root: str, sync_src: str, config_path: str, runtime_dir: str, board_url: str) -> str:
    return f"""# Miro Sync

This repo is configured to use the external `bmad-miro-sync` project via:

- `{sync_src}`

The local sync config for this repo is:

- `{config_path}`

It points at the current Miro board:

- `{board_url}`

## Export A Codex Bundle

From the repo root:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync export-codex-bundle \\
  --project-root {project_root} \\
  --config {config_path} \\
  --output-dir {runtime_dir}
```

This writes:

- `.bmad-miro-sync/run/plan.json`
- `.bmad-miro-sync/run/codex-bundle.json`
- `.bmad-miro-sync/run/instructions.md`
- `.bmad-miro-sync/run/results.template.json`

## Apply Results

After Codex executes the plan with Miro tools and writes `results.json`:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync apply-results \\
  --project-root {project_root} \\
  --config {config_path} \\
  --results {runtime_dir}/results.json
```

## Notes

- Local BMad artifacts remain the source of truth.
- Miro item mappings are stored in `.bmad-miro-sync/state.json`.
- Runtime sync files are ignored by git.

## Codex Workflow

For normal use inside Codex, use the local skill:

- `bmad-miro-auto-sync`
- `bmad-ingest-miro-comments`

That skill wraps the full project-specific flow:

1. export the section-level sync bundle
2. execute the Miro operations with Codex MCP tools
3. write `results.json`
4. apply the results back into the local manifest

The intended project workflow is:

1. run a BMad step that updates `_bmad-output`
2. immediately run `bmad-miro-auto-sync`

To bring stakeholder comments back in as review material:

1. fetch and normalize Miro comments for synced section items
2. run `bmad-ingest-miro-comments`
"""


def ensure_gitignore_entries(existing: str) -> str:
    lines = existing.splitlines()
    required = [".bmad-miro-sync/"]
    changed = False
    for entry in required:
        if entry not in lines:
            lines.append(entry)
            changed = True
    output = "\n".join(lines).rstrip() + "\n"
    return output if changed or existing else output


def insert_sync_policy(content: str) -> str:
    if "## BMad Miro Sync Policy" in content:
        return content
    frontmatter_end = content.find("---\n", 4)
    if content.startswith("---\n") and frontmatter_end != -1:
        insert_at = frontmatter_end + 4
        return content[:insert_at] + "\n" + SYNC_POLICY_HEADER + "\n" + content[insert_at:]
    return SYNC_POLICY_HEADER + "\n" + content


def skill_files(root: Path) -> list[Path]:
    skills_root = root / ".agents" / "skills"
    if not skills_root.exists():
        return []
    return sorted(
        path
        for path in skills_root.glob("*/SKILL.md")
        if path.name == "SKILL.md" and path.parent.name not in {"bmad-miro-auto-sync", "bmad-ingest-miro-comments"}
    )
