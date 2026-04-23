---
name: bmad-miro-collaboration
description: Run the full Miro collaboration loop across publish, apply, ingest, triage, and readiness stages.
---

# BMad Miro Collaboration

Use this skill when the operator wants one ordered path for the full collaboration loop.

## Preconditions

- The target repo contains `.bmad-miro.toml`
- Codex has access to Miro tools for publish and comment collection stages
- The repo has the Python package available locally

## Workflow

1. Seed the publish stage and repo-local run report:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync run-codex-collaboration-workflow \
  --project-root <repo-root> \
  --config <repo-root>/.bmad-miro.toml \
  --runtime-dir <repo-root>/.bmad-miro-sync/run \
  --stop-after publish
```

2. Read:
   - `<repo-root>/.bmad-miro-sync/run/plan.json`
   - `<repo-root>/.bmad-miro-sync/run/publish-bundle.json`
   - `<repo-root>/.bmad-miro-sync/run/codex-bundle.json`
   - `<repo-root>/.bmad-miro-sync/run/instructions.md`
   - `<repo-root>/.bmad-miro-sync/run/results.template.json`
   - `<repo-root>/.bmad-miro-sync/run/collaboration-run.json`

`publish-bundle.json` is the host-neutral contract. `codex-bundle.json` is a backward-compatible alias with the same payload for the Codex-first path.

3. Execute the exported Miro plan with Codex tools and write `<repo-root>/.bmad-miro-sync/run/results.json`.

If the exported plan includes `ensure_zone` operations but the available Miro tools cannot create board-level containers, do not ask the user whether to do a partial sync. Instead:

1. update `<repo-root>/.bmad-miro.toml` so `[object_strategies].phase_zone = "workstream_anchor"`
2. rerun the publish-stage command above
3. continue from the regenerated plan

This workflow requires a complete publish pass. If you cannot execute every publish operation after regenerating the plan, stop and report blocked. Do not write a partial `results.json`, and do not resume from `apply-results` with a partial publish.

4. Fetch and normalize Miro comments into `<repo-root>/.bmad-miro-sync/run/comments.json`.

5. Add explicit triage metadata to `<repo-root>/.bmad-miro-sync/run/review-input.json`.

6. Resume the single workflow entrypoint:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync run-codex-collaboration-workflow \
  --project-root <repo-root> \
  --config <repo-root>/.bmad-miro.toml \
  --runtime-dir <repo-root>/.bmad-miro-sync/run \
  --start-at apply-results
```

7. Inspect the repo-local outputs:
   - `<repo-root>/.bmad-miro-sync/state.json`
   - `<repo-root>/_bmad-output/review-artifacts/miro-comments.md`
   - `<repo-root>/_bmad-output/review-artifacts/decision-records.md`
   - `<repo-root>/_bmad-output/review-artifacts/decision-records.json`
   - `<repo-root>/_bmad-output/implementation-artifacts/implementation-readiness.md`
   - `<repo-root>/_bmad-output/implementation-artifacts/implementation-handoff.md`
   - `<repo-root>/.bmad-miro-sync/run/collaboration-run.json`

## Rules

- Keep `_bmad-output` as the canonical source of truth.
- Keep all collaboration state repo-local and inspectable.
- Resume from the failing stage instead of rerunning everything blindly.
- Do not fabricate later-stage success if a required repo-local input is missing.
- Preserve the degraded fallback decision automatically with `workstream_anchor` when phase-zone containers are unavailable.
