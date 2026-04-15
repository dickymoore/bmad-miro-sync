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
- `.agents/skills/bmad-miro-auto-sync/SKILL.md`
- `docs/miro-sync.md`
- `.gitignore` entry for `.bmad-miro-sync/`

And, by default, it patches repo-local `bmad-*` skill headers with the sync policy.

## MVP Status

The current MVP provides:

- artifact discovery from `_bmad-output`
- section-level markdown splitting for more navigable Miro publishing
- artifact classification and deterministic sync planning
- local manifest persistence to avoid duplicate publishing
- host-neutral operation export for MCP-capable hosts
- Codex-oriented instruction rendering

The current implementation does not directly call Miro from the Python CLI. Instead it exports a sync plan that a host such as Codex can execute using its Miro MCP tools, then records the results back into the local manifest.

## Codex Plugin

A repo-local Codex plugin scaffold is included under [plugins/bmad-miro-sync-codex](/home/codexuser/bmad-miro-sync/plugins/bmad-miro-sync-codex/.codex-plugin/plugin.json:1).

The plugin provides a Codex skill that:

- exports a sync bundle
- executes the plan with Codex Miro tools
- writes `results.json`
- applies the results back into `.bmad-miro-sync/state.json`

## Configuration

Copy the example config:

```bash
cp .bmad-miro.example.toml .bmad-miro.toml
```

Then set `board_url` to the target Miro board.

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

Apply host execution results to the manifest:

```bash
PYTHONPATH=src python3 -m bmad_miro_sync apply-results --project-root . --config .bmad-miro.toml --results results.json
```

## Host Workflow

1. Run `plan` to export operations for section docs, frames, and tables.
2. Execute those operations in a host with Miro MCP access.
3. Save execution results as JSON.
4. Run `apply-results` to update `.bmad-miro-sync/state.json`.

This flow is designed for Codex first, but the same plan and results handshake can be used by Claude Code, Gemini CLI, or other environments that can execute Miro MCP operations.
