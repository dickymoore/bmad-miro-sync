# Architecture: bmad-miro-sync

## 1. Purpose

`bmad-miro-sync` provides a collaboration architecture for BMAD in Miro. The system must support publication, review, decision capture, and handoff across planning and solutioning while preserving BMAD artifacts in the repository as the canonical source.

## 2. Architectural Drivers

- BMAD artifacts in `_bmad-output` remain the source of truth
- collaboration must be structured, not just visible
- repeated syncs must preserve stable identity for sections and review context
- Miro must support different stakeholder lenses without fragmenting the truth
- feedback must be routable back into BMAD review artifacts and readiness outputs
- host-specific logic must stay thin

## 3. Lessons From The `fluidscan` Miro Testbed

The `fluidscan` validation runs produced four architecture-level lessons:

1. Section-level export is necessary because whole-document dumps are too coarse for focused review.
2. Stable IDs and repeatable updates are necessary because duplicated artifacts destroy review continuity.
3. Pure publishing is insufficient because stakeholders still need orientation, review states, and decision pathways.
4. Comment ingest is valuable, but without triage and routing the output remains a passive transcript rather than collaboration progress.

These lessons shift the product from "sync engine with wrappers" to "collaboration system powered by sync and traceability."

## 4. High-Level Design

The system is split into four layers:

1. Artifact and sync core
2. Collaboration model
3. Review and decision pipeline
4. Delivery interfaces

### 4.1 Artifact And Sync Core

This layer remains host-neutral and owns:

- artifact discovery
- section normalization
- artifact classification
- content hashing and stable identity
- manifest persistence
- Miro operation planning

### 4.2 Collaboration Model

This layer defines how BMAD artifacts become collaborative objects in Miro:

- board zones by BMAD phase
- artifact collections by workstream
- review metadata
- readiness markers
- stakeholder-specific views and labels

It is the product-defining layer.

### 4.3 Review And Decision Pipeline

This layer turns passive comments into actionable planning input:

- inbound comment capture
- normalized review bundles
- issue grouping by artifact, section, and topic
- decision status lifecycle:
  - open
  - accepted
  - deferred
  - resolved
  - blocked
- outbound handoff summaries for PM, UX, architect, and developer workflows

### 4.4 Delivery Interfaces

Delivery interfaces call the same shared application services:

- CLI interface
- Codex adapter
- future adapters for Claude Code, Gemini CLI, or CI runners

## 5. Core Domain Model

Proposed internal concepts:

- `ArtifactSource`: locates candidate BMAD files
- `ArtifactRecord`: normalized representation of one source artifact or section
- `ArtifactClassifier`: maps artifacts to BMAD and collaboration types
- `BoardPlan`: intended board structure and object placement
- `CollaborationObject`: reviewable Miro object with state metadata
- `ReviewSignal`: normalized stakeholder feedback tied to an artifact or section
- `DecisionRecord`: tracked outcome for a review item
- `ReadinessSummary`: aggregated planning status for a workflow stage
- `SyncManifestStore`: persistent mapping between source artifacts and Miro objects
- `MiroPublisher`: narrow execution boundary for Miro actions

## 6. Collaboration Workspace Model

The default board model should create durable collaboration zones:

- Analysis
- Planning
- Solutioning
- Implementation Readiness
- Delivery Feedback

Within each zone, the workspace should support:

- anchor artifacts such as brief, PRD, UX, architecture, and epics
- review clusters for stakeholder comments and issues
- decision markers and summary tables
- readiness indicators for unresolved gaps and blocked handoffs

The model must preserve manual board organization where users improve local readability.

## 7. Artifact Mapping Strategy

Initial mapping should favor clarity and reviewability:

- product brief, PRD, architecture, research, and UX sections -> Miro docs
- epics and story summaries -> docs or tables depending on density
- decision registers and readiness summaries -> tables
- review bundles -> docs grouped by artifact and topic

The system should map artifacts according to collaboration intent, not only file type.

## 8. Review Lifecycle

The review lifecycle should be explicit:

1. publish or update artifact sections
2. orient stakeholders with phase and workstream structure
3. capture comments or structured review items
4. normalize signals back into BMAD review artifacts
5. triage into decisions, follow-ups, or unresolved questions
6. emit readiness and handoff summaries

This lifecycle is a first-class architectural concern, not an optional add-on.

## 9. State And Configuration

Each adopting repo supplies local configuration, for example `.bmad-miro.toml`, and keeps local state such as `.bmad-miro-sync/state.json`.

Configuration should include:

- Miro board URL
- source paths
- enabled artifact classes
- board layout preferences
- collaboration modes to enable
- review and readiness output preferences

State should include:

- artifact identity and content fingerprint
- mapped Miro item ID and URL
- parent-child relationships between sections
- review metadata references where available
- last sync timestamp

## 10. Miro Integration Boundary

The Miro boundary stays encapsulated. The core should prepare normalized operations and interpret results, while the host path executes actual Miro actions. This preserves portability and keeps collaboration logic independent from one runtime.

## 11. MVP Decisions

- repository artifacts remain canonical
- sync is primarily repo-to-Miro, with structured feedback returning as review artifacts rather than direct in-place edits
- collaboration states are part of the product
- Codex is the first operating path
- `fluidscan` is the primary validation repo for collaboration behavior
- readiness outputs are required before implementation handoff

## 12. Open Decisions

- best default representation for story planning: section docs, table summaries, or a hybrid
- whether decision status should live in a dedicated table, inline labels, or both
- how much facilitation metadata should be authored automatically versus manually
- how to support multi-board programs without breaking single-board clarity

## 13. Recommended Solutioning Sequence

1. validate collaboration jobs and stakeholder roles
2. define board information architecture and UX flows
3. finalize artifact and review object schemas
4. define decision and readiness data model
5. refine sync planning and host execution around the collaboration model
6. only then move to implementation planning
