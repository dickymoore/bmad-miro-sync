# Product Brief: bmad-miro-sync

## Summary

`bmad-miro-sync` is a reusable synchronization tool that publishes BMad Method outputs into Miro so non-operator stakeholders can see current project artifacts in a shared visual workspace. The product is designed as a hybrid: a host-neutral sync engine plus host-specific wrappers, with Codex support first and an extension path for other MCP-capable environments such as Claude Code and Gemini CLI.

The core problem is visibility. BMad artifacts are structured and useful, but they normally live inside local repo folders such as `_bmad-output/planning-artifacts` and `_bmad-output/implementation-artifacts`. That is workable for the operator driving the workflow, but weak for stakeholders who need lightweight access, visual organization, and a persistent shared surface for review. Miro already serves that collaboration role. `bmad-miro-sync` bridges the gap by making BMad outputs continuously publishable into a well-structured Miro board.

## Problem

Teams using BMad often need to share evolving artifacts with people who are not working directly inside the repository or agent host. Today that usually means ad hoc copy-paste, screenshots, or manual exports. Those approaches fail because they are inconsistent, drift quickly, and do not preserve a reliable mapping between the canonical artifact and what stakeholders are reviewing.

The result is predictable:

- stakeholders read outdated documents
- architecture and story planning lose traceability
- implementation status is harder to understand
- review feedback happens in parallel surfaces without a clean sync loop

## Users

Primary users:

- operators running BMad workflows in Codex, and later other host environments
- product and delivery leads who want planning and implementation artifacts visible in Miro
- technical stakeholders who want architecture, stories, and status represented in a readable board

Secondary users:

- maintainers who want a reusable publishing tool for multiple BMad repos
- teams who want CI-friendly publishing for shared project boards

## Product Goal

Create a reusable tool that reads BMad artifacts from a repository and publishes them into a deterministic Miro board structure with stable item identity, low duplication, and safe repeatable updates.

## Non-Goals For MVP

- editing Miro content and automatically writing those edits back into BMad artifacts
- full workflow orchestration for every agent host on day one
- support for arbitrary non-BMad documentation formats
- a complex multi-board program management layer

## MVP Scope

The MVP should support:

- local configuration via a repo file such as `.bmad-miro.yaml`
- reading `_bmad-output/planning-artifacts` and `_bmad-output/implementation-artifacts`
- publishing key artifact classes to Miro:
  - product brief
  - PRD
  - UX design
  - architecture
  - epics and stories
  - readiness and validation reports
  - sprint status
  - individual story files
- deterministic Miro layout by phase
- idempotent updates using a local sync manifest that stores Miro item IDs
- a CLI entrypoint usable from local development or CI
- a Codex-friendly wrapper or instructions for direct use inside Codex sessions

## Product Shape

The product should be hybrid by design:

- a core sync engine that knows how to discover artifacts, classify them, transform them, and publish them
- a CLI wrapper for normal shell usage and automation
- thin host adapters for agent environments that can invoke the CLI or the shared library

This keeps the system usable even in hosts that do not expose identical tool APIs while still allowing first-class support where MCP-backed Miro actions are available.

## Success Criteria

The MVP is successful if:

- a BMad repo can be configured in minutes
- running the sync repeatedly updates the same Miro items instead of duplicating them
- a stakeholder can open one board and understand the current project state
- Codex users can adopt it immediately
- later host support can be added without redesigning the core sync engine

## Risks

- Miro markdown and structured document capabilities may not map perfectly to all BMad artifact formats
- some hosts may not offer equivalent integration affordances, so wrappers must degrade gracefully
- board structure can become noisy if artifact-to-item rules are not opinionated enough
- bi-directional sync pressure may appear early even though it should be explicitly deferred

## Initial Direction

Codex should be the first supported host because it already works with Miro MCP in the current environment. The architecture should still remain host-neutral so the sync engine can later be wrapped for Claude Code, Gemini CLI, or plain shell usage without reworking the core publishing model.
