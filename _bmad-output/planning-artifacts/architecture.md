# Architecture: bmad-miro-sync

## 1. Purpose

`bmad-miro-sync` provides a reusable synchronization layer between BMad artifacts in a local repository and a structured Miro board. The design must support immediate use from Codex while remaining independent enough to work from other agent hosts or standard CLI execution.

## 2. Architectural Drivers

- BMad artifacts in `_bmad-output` remain the source of truth
- publishing must be idempotent and update existing Miro items
- host-specific logic must stay thin
- local configuration must be simple and portable across repos
- the MVP should support docs and tables first, with diagram support where practical

## 3. High-Level Design

The system is split into three layers:

1. Core sync engine
2. Delivery interfaces
3. State and configuration

### 3.1 Core Sync Engine

The core engine is host-neutral and owns the synchronization logic:

- artifact discovery
- artifact classification
- board layout planning
- content transformation
- Miro publish and update decisions
- sync manifest persistence

This layer should not depend on Codex-specific abstractions.

### 3.2 Delivery Interfaces

Delivery interfaces call the core engine:

- CLI interface
- Codex adapter
- future adapters for Claude Code, Gemini CLI, or CI runners

The CLI is the primary public entrypoint. Host adapters should call the same internal application service to avoid divergence.

### 3.3 State and Configuration

Each adopting repo supplies local configuration, for example `.bmad-miro.yaml`, and keeps a local sync manifest such as `.bmad-miro-sync/state.json`.

Configuration should include:

- Miro board URL
- source paths
- enabled artifact classes
- layout preferences
- naming overrides

The sync manifest should include:

- artifact identity
- content hash or change fingerprint
- mapped Miro item URL or ID
- item type
- last sync timestamp

## 4. Core Domain Model

Proposed internal concepts:

- `ArtifactSource`: locates candidate files in BMad output directories
- `ArtifactRecord`: normalized representation of one source artifact
- `ArtifactClassifier`: maps files to logical artifact types
- `BoardPlan`: intended Miro structure for this sync run
- `PublishOperation`: create, update, skip, or warn action for a target item
- `SyncManifestStore`: reads and writes local sync state
- `MiroPublisher`: executes Miro operations behind a narrow interface

## 5. Artifact Mapping Strategy

Initial artifact mapping:

- markdown narrative artifacts -> Miro docs
- sprint and status artifacts -> Miro tables or docs, depending on available structure
- architecture diagrams -> generated Miro diagrams where source structure is explicit enough, otherwise docs
- story collections -> Miro table rows or per-story docs

The MVP should prefer reliable readability over ambitious transformation. If a source file cannot be transformed confidently into a richer visual type, publish it as a doc first.

## 6. Board Layout Convention

Default board layout should create phase frames:

- Analysis
- Planning
- Solutioning
- Implementation

Within each frame, create stable sections for:

- core artifacts
- validation and review outputs
- active implementation status

The layout must be deterministic so repeated syncs do not drift across the board.

## 7. Miro Integration Boundary

The Miro boundary should be encapsulated behind a publisher interface. The first implementation can target environments where Miro MCP tools are available. The engine should not assume that every caller can directly invoke those tools.

Two execution modes should be anticipated:

1. In-process host mode
   A host adapter can call Miro tools directly and pass results back into the engine.

2. External driver mode
   A wrapper or automation layer executes sync actions and passes normalized results into the engine.

This design protects the core from coupling to a single agent runtime.

## 8. Packaging Recommendation

Use a small Python project:

- core library package
- CLI executable
- optional host adapter modules

Python is a reasonable fit because the repo logic is file-heavy, manifest-heavy, and orchestration-heavy rather than UI-heavy. It is also straightforward to package for local shell usage and CI.

## 9. Operational Flow

1. Load config
2. Discover artifacts
3. Classify and normalize content
4. Read sync manifest
5. Compute desired board layout and publish plan
6. Create or update Miro items
7. Persist updated manifest
8. Report results

## 10. MVP Decisions

- Source of truth is always local BMad artifacts
- Sync is one-way from repo to Miro
- CLI is the primary stable interface
- Codex is the first supported host
- Host adapters remain thin wrappers around shared application logic
- Docs and tables come before advanced diagram generation

## 11. Open Decisions

- exact config schema and defaults
- story representation choice: one table versus one doc per story
- whether status artifacts should always become tables or stay as docs unless explicitly configured
- how to support hosts that cannot directly access Miro tooling but can still invoke the CLI

## 12. Recommended Implementation Order

1. scaffold core package and CLI
2. define config schema and manifest schema
3. implement artifact discovery and classification
4. implement doc publishing
5. implement table publishing for sprint and story status
6. add Codex-focused usage path
7. add additional host adapters once the core model is stable
