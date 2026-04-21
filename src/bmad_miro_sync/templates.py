from __future__ import annotations

from pathlib import Path
import re


SYNC_POLICY_BODY = (
    "If this skill creates or updates `_bmad-output` artifacts or other stakeholder-facing project documentation, "
    "invoke `bmad-miro-auto-sync` before considering the workflow complete unless the user explicitly says not to "
    "sync. If the sync fails, report the blocker clearly."
)

SYNC_POLICY_HEADER = f"""## BMad Miro Sync Policy

{SYNC_POLICY_BODY}
"""

SYNC_POLICY_BLOCK_RE = re.compile(
    r"(?ms)^## (?P<title>.+? Sync Policy)\n\n(?P<body>.+?)(?:\n{2,}|\Z)"
)


def render_config(board_url: str) -> str:
    return f"""board_url = "{board_url}"
source_root = "_bmad-output"
manifest_path = ".bmad-miro-sync/state.json"

# Optional discovery overrides. Leave commented to keep the legacy
# source_root behavior, or enable to restrict discovery to canonical inputs.
#[discovery]
#source_paths = ["_bmad-output/planning-artifacts", "_bmad-output/implementation-artifacts", "_bmad-output/review-artifacts"]
#required_artifact_classes = ["prd", "ux_design", "architecture"]

# Optional object strategy overrides for degraded-mode hosts. Leave
# commented to keep the preferred object types.
#[object_strategies]
#phase_zone = "workstream_anchor"  # default: "zone"
#story_summary = "doc"             # default: "table"

[layout]
create_phase_frames = true

[publish]
analysis = true
planning = true
solutioning = true
implementation = true
stories_table = true

[sync]
removed_item_policy = "archive"
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
- `{runtime_dir}/publish-bundle.json`
- `{runtime_dir}/codex-bundle.json`
- `{runtime_dir}/instructions.md`

3. Execute the plan in order with Codex Miro tools:

- `ensure_zone`
- `ensure_workstream_anchor`
- `create_doc`
- `update_doc`
- `create_table`
- `update_table`
- `skip`

If the exported plan includes `ensure_zone` operations but the available Miro tools cannot create board-level containers, do not ask the user to decide between a partial sync and a clean sync. Instead:

1. update `{config_path}` so `[object_strategies].phase_zone = "workstream_anchor"`
2. re-run the export command above to regenerate the bundle
3. continue from the regenerated plan and treat that new plan as the source of truth for the sync run

Only proceed with a partial results file when the user explicitly wants a partial sync.

4. Write:

- `{runtime_dir}/results.json`

The JSON shape must match the template in:

- `{runtime_dir}/results.template.json`

If only part of the plan executes, set `run_status` to `partial` and write only the executed operation entries. The local state file will keep the remaining operations pending for retry.

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
- Preserve `op_id` exactly
- Preserve existing Miro item positions and manual workflow grouping when updating content
- When an operation exports `degraded = true`, execute `resolved_item_type` and preserve the fallback metadata in `results.json`
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
    review_input_path = f"{runtime_dir}/review-input.json"
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
    }}
  ]
}}
```

Legacy payloads that only include `artifact_id`, `source_artifact_id`, `section_title`, `author`, `created_at`, `body`, and `miro_url` are still accepted, but the preferred shape above preserves stable section and published-object traceability.

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

5. When explicit decision triage is needed, create `{review_input_path}` with the normalized `comments` payload plus a `triage` list:

```json
{{
  "comments": [{{}}],
  "triage": [
    {{
      "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
      "topic": "Acceptance criteria",
      "status": "open",
      "owner": "Awaiting triage",
      "rationale": "Awaiting triage",
      "follow_up_notes": "Optional"
    }}
  ]
}}
```

6. Run:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync triage-feedback \\
  --project-root {project_root} \\
  --config {config_path} \\
  --input {review_input_path}
```

7. Generate readiness and handoff artifacts from the canonical decision sidecar:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync summarize-readiness \\
  --project-root {project_root} \\
  --config {config_path}
```

## Rules

- Do not modify `_bmad-output` source artifacts directly from Miro comments.
- Write comments into the generated review artifact and report the output path.
- Preserve `artifact_id` exactly so comments stay attached to the right markdown section.
- Preserve topic, author, timestamp, and published-object traceability when normalizing comments.
- Keep decision triage explicit and repo-local; do not infer `accepted` or `resolved` from raw comment text.
- Approved triage statuses are `open`, `accepted`, `deferred`, `resolved`, and `blocked`.
- Treat `_bmad-output/review-artifacts/decision-records.json` as the canonical machine-readable decision input for readiness generation.
- Write `_bmad-output/implementation-artifacts/implementation-readiness.md` and `_bmad-output/implementation-artifacts/implementation-handoff.md` without mutating planning artifacts or manifest state.
"""


def render_collaboration_skill(
    project_root: str,
    sync_src: str,
    config_path: str,
    runtime_dir: str,
    project_name: str,
) -> str:
    return f"""---
name: run-codex-collaboration-workflow
description: Run the full Codex-first collaboration loop for {project_name} across publish, apply, ingest, triage, and readiness stages.
---

# Run Codex Collaboration Workflow

Use this skill when the operator wants one ordered Codex-first path for the full collaboration loop.

## Repo-Specific Settings

- Project root: `{project_root}`
- Sync package source: `{sync_src}`
- Sync config: `{config_path}`
- Runtime directory: `{runtime_dir}`

## Workflow

1. Seed the publish stage and repo-local run report:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync run-codex-collaboration-workflow \\
  --project-root {project_root} \\
  --config {config_path} \\
  --runtime-dir {runtime_dir} \\
  --stop-after publish
```

2. Read the publish outputs:

- `{runtime_dir}/plan.json`
- `{runtime_dir}/publish-bundle.json`
- `{runtime_dir}/codex-bundle.json`
- `{runtime_dir}/instructions.md`
- `{runtime_dir}/results.template.json`
- `{runtime_dir}/collaboration-run.json`

3. Execute the exported Miro plan with Codex tools and write `{runtime_dir}/results.json`.

If the exported plan includes `ensure_zone` operations but the current Miro tools cannot create board-level containers, do not ask the user to choose between a partial sync and a clean sync. Instead:

1. update `{config_path}` so `[object_strategies].phase_zone = "workstream_anchor"`
2. rerun the workflow command above with `--stop-after publish`
3. continue from the regenerated plan and treat that new plan as the source of truth

4. Fetch and normalize Miro comments into `{runtime_dir}/comments.json`.

5. Add explicit triage data in `{runtime_dir}/review-input.json`.

6. Resume the workflow from repo-local stage inputs:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync run-codex-collaboration-workflow \\
  --project-root {project_root} \\
  --config {config_path} \\
  --runtime-dir {runtime_dir} \\
  --start-at apply-results
```

7. Inspect the repo-local outputs:

- `.bmad-miro-sync/state.json`
- `_bmad-output/review-artifacts/miro-comments.md`
- `_bmad-output/review-artifacts/decision-records.md`
- `_bmad-output/review-artifacts/decision-records.json`
- `_bmad-output/implementation-artifacts/implementation-readiness.md`
- `_bmad-output/implementation-artifacts/implementation-handoff.md`
- `{runtime_dir}/collaboration-run.json`

## Rules

- Keep `_bmad-output` as the canonical source of truth.
- Keep all collaboration state repo-local and inspectable.
- Resume from the failing stage instead of rerunning the whole flow blindly.
- Do not fabricate later-stage success if a required repo-local input is missing.
- Preserve the degraded fallback decision automatically with `workstream_anchor` when phase-zone containers are unavailable.
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
- `.bmad-miro-sync/run/publish-bundle.json`
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

## Run The Codex Collaboration Workflow

For the full collaboration loop, use the single project-local skill:

- `run-codex-collaboration-workflow`

Or use the CLI entrypoint directly:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync run-codex-collaboration-workflow \\
  --project-root {project_root} \\
  --config {config_path} \\
  --runtime-dir {runtime_dir} \\
  --stop-after publish
```

That publish-stage run writes the repo-local bundle, instructions, and `collaboration-run.json`. After Codex writes `{runtime_dir}/results.json`, `{runtime_dir}/comments.json`, and `{runtime_dir}/review-input.json`, resume the same workflow entrypoint:

```bash
PYTHONPATH={sync_src} \\
python3 -m bmad_miro_sync run-codex-collaboration-workflow \\
  --project-root {project_root} \\
  --config {config_path} \\
  --runtime-dir {runtime_dir} \\
  --start-at apply-results
```

If the exported publish plan requires phase-zone containers that the current Miro tools cannot create, set `[object_strategies].phase_zone = "workstream_anchor"`, rerun the publish stage, and continue from the regenerated plan.

## Notes

- Local BMad artifacts remain the source of truth.
- Miro item mappings are stored in `.bmad-miro-sync/state.json`.
- `.bmad-miro-sync/state.json` also keeps the last reconciled operation statuses and partial-run summary.
- Runtime sync files are ignored by git.
- If the current Miro tool surface cannot create phase-zone containers, set `[object_strategies].phase_zone = "workstream_anchor"`, regenerate the bundle, and continue from the new plan rather than asking the user to choose a partial run.

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
2. run `run-codex-collaboration-workflow`

To bring stakeholder comments back in as review material:

1. fetch and normalize Miro comments for synced section items
2. write `.bmad-miro-sync/run/comments.json`
3. add triage in `.bmad-miro-sync/run/review-input.json`
4. resume `run-codex-collaboration-workflow` from `apply-results`
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
    content = _dedupe_sync_policy_blocks(content)
    if SYNC_POLICY_BODY in content:
        return content
    frontmatter_end = content.find("---\n", 4)
    if content.startswith("---\n") and frontmatter_end != -1:
        insert_at = frontmatter_end + 4
        return content[:insert_at] + "\n" + SYNC_POLICY_HEADER + "\n" + content[insert_at:]
    return SYNC_POLICY_HEADER + "\n" + content


def _dedupe_sync_policy_blocks(content: str) -> str:
    seen_matching_policy = False
    parts: list[str] = []
    last_index = 0
    for match in SYNC_POLICY_BLOCK_RE.finditer(content):
        body = match.group("body").strip()
        if body != SYNC_POLICY_BODY:
            continue
        parts.append(content[last_index:match.start()])
        if not seen_matching_policy:
            parts.append(match.group(0).rstrip() + "\n\n")
            seen_matching_policy = True
        last_index = match.end()
    if not seen_matching_policy:
        return content
    parts.append(content[last_index:])
    return "".join(parts).rstrip() + "\n"


def skill_files(root: Path) -> list[Path]:
    skills_root = root / ".agents" / "skills"
    if not skills_root.exists():
        return []
    return sorted(
        path
        for path in skills_root.glob("*/SKILL.md")
        if path.name == "SKILL.md"
        and path.parent.name
        not in {"bmad-miro-auto-sync", "bmad-ingest-miro-comments", "run-codex-collaboration-workflow"}
    )
