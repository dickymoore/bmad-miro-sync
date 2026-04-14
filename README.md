# bmad-miro-sync

Reusable BMad-to-Miro synchronization tooling.

This repository is intended to provide:

- A host-neutral sync engine that reads BMad outputs and publishes them to Miro
- A CLI for local and CI usage
- A Codex-friendly wrapper first, with room for other hosts such as Claude Code and Gemini CLI

Planning artifacts live in `_bmad-output/planning-artifacts/`.

## MVP Status

The current MVP provides:

- artifact discovery from `_bmad-output`
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

1. Run `plan` to export operations for docs, frames, and tables.
2. Execute those operations in a host with Miro MCP access.
3. Save execution results as JSON.
4. Run `apply-results` to update `.bmad-miro-sync/state.json`.

This flow is designed for Codex first, but the same plan and results handshake can be used by Claude Code, Gemini CLI, or other environments that can execute Miro MCP operations.
