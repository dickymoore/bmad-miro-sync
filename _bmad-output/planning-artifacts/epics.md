---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/implementation-readiness-report-2026-04-17.md
  - _bmad-output/planning-artifacts/solutioning-readiness.md
---

# bmad-miro-sync - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for bmad-miro-sync, decomposing the requirements from the PRD, UX Design, Architecture, and implementation-readiness assessment into implementable stories. `fluidscan` remains validation evidence only; it does not define product scope.

## Requirements Inventory

### Functional Requirements

FR1: The system must discover BMAD planning artifacts from configured paths.
FR2: The system must split markdown artifacts into stable reviewable sections.
FR3: The system must generate deterministic Miro object plans for those sections.
FR4: The system must preserve artifact identity across repeated syncs.
FR5: The system must organize Miro content by BMAD phase.
FR6: The system must support grouping by workstream such as product, UX, architecture, and delivery.
FR7: The system must preserve existing manual placement when updating known objects.
FR8: The system must ingest normalized Miro comments into BMAD review artifacts.
FR9: The system must preserve artifact and section references for each ingested signal.
FR10: The system should support grouping feedback by artifact, section, and topic.
FR11: The product must support a tracked status for review items or decisions.
FR12: The product must generate or support readiness summaries for planning and solutioning outcomes.
FR13: The product should highlight unresolved blockers and deferred items.
FR14: The MVP must support Codex as the first execution environment.
FR15: The architecture should allow later host adapters to reuse the same core model.

### NonFunctional Requirements

NFR1: Repeated syncs should be idempotent from the board's perspective.
NFR2: Local state must be durable and human-inspectable.
NFR3: The product should remain usable even if some Miro object types are unavailable.
NFR4: Artifact and decision outputs should be understandable by non-technical participants.
NFR5: A stakeholder must be able to orient themselves quickly on the board.
NFR6: The board should separate artifact content from review and readiness signals.
NFR7: The system should avoid visual noise and redundant duplication.
NFR8: Review state labels should be easy to scan.

### Additional Requirements

- BMAD artifacts in `_bmad-output` remain the canonical source, and Miro must not become the source of truth.
- Artifact discovery must handle the current planning-artifact set and support whole-document versus sharded-document selection rules.
- Section normalization must preserve parent-child relationships and stable section identifiers across syncs.
- Deterministic board planning must encode phase zones, workstream grouping, and collaboration-intent object selection.
- Local manifest/state must preserve content fingerprints, Miro object identity, placement metadata, and sync timestamps in a repo-local format that humans can inspect.
- Update behavior must preserve manual board curation for already-known objects.
- Review outputs must route normalized feedback into decisions, grouped review bundles, and readiness summaries before implementation handoff.
- Codex is the first operating path; host-specific Miro execution must remain a thin adapter over shared core planning logic.
- `fluidscan` is validation evidence for collaboration behavior and degraded-mode scenarios only, not a product requirement source.

### UX Design Requirements

UX-DR1: Create persistent board zones for Analysis, Planning, Solutioning, Implementation Readiness, and Delivery Feedback.
UX-DR2: Group published artifacts by workstream anchors so product, UX, architecture, and delivery stakeholders can scan the board quickly.
UX-DR3: Publish section-level artifacts instead of full-document dumps so reviewers can comment on focused content.
UX-DR4: Preserve visual continuity of existing objects across updates, including manual curation and placement.
UX-DR5: Distinguish anchor artifacts from review objects, decision markers, and readiness summaries so review noise does not overwhelm source content.
UX-DR6: Support role-aware scanning through clear labels, summaries, and readiness markers without requiring separate apps.
UX-DR7: Make unresolved issues, blockers, and deferred items obvious within the board and in exported summaries.
UX-DR8: Ensure labels and summaries are plain-language, scan-friendly, and not color-dependent.

### FR Coverage Map

FR1: Epic 1 - Discover configured planning artifacts and classify them for publishing.
FR2: Epic 1 - Split markdown artifacts into stable, reviewable sections with persistent section IDs.
FR3: Epic 1 - Generate deterministic board plans by phase, workstream, and collaboration object type.
FR4: Epic 2 - Match repeat syncs to manifest-backed artifact identities.
FR5: Epic 1 - Publish content into BMAD phase zones.
FR6: Epic 1 - Group content by workstream anchors and collaboration intent.
FR7: Epic 2 - Preserve manual placement when updating known objects.
FR8: Epic 3 - Ingest normalized Miro comments into BMAD review artifacts.
FR9: Epic 3 - Preserve artifact and section references on every ingested signal.
FR10: Epic 3 - Group feedback by artifact, section, and topic.
FR11: Epic 3 - Track decision and review statuses across triage outputs.
FR12: Epic 3 - Produce readiness summaries for planning and solutioning handoff.
FR13: Epic 3 - Surface unresolved blockers and deferred topics in outputs.
FR14: Epic 4 - Provide a Codex-first operating path for publish, ingest, and handoff.
FR15: Epic 4 - Keep core planning logic reusable through host-neutral adapter boundaries.

## Epic List

### Epic 1: Publish A Review-Ready BMAD Workspace
BMAD operators can discover planning artifacts, split them into stable sections, and publish a deterministic phase-and-workstream board that non-CLI stakeholders can review immediately.
**FRs covered:** FR1, FR2, FR3, FR5, FR6

### Epic 2: Keep Board Continuity Across Repeated Syncs
BMAD operators can resync updated artifacts without duplicating content, breaking references, or overwriting manual board curation, even when Miro object options are constrained.
**FRs covered:** FR4, FR7

### Epic 3: Turn Review Activity Into Decisions And Readiness Signals
Product, UX, and delivery stakeholders can move from comments to grouped decisions, blockers, and readiness summaries that trace back to the right artifact sections.
**FRs covered:** FR8, FR9, FR10, FR11, FR12, FR13

### Epic 4: Run The Collaboration Loop Through A Codex-First Path
BMAD operators can execute the collaboration workflow in Codex today while preserving a clean boundary for future host adapters to reuse the same core model.
**FRs covered:** FR14, FR15

## Epic 1: Publish A Review-Ready BMAD Workspace

Establish the initial publish path so stakeholders receive a structured, section-aware Miro workspace instead of a document dump.

### Story 1.1: Discover configured planning artifacts

As a BMAD operator,
I want the sync process to find the right planning artifacts from configured paths,
So that the publish run starts from the correct canonical inputs without manual file hunting.

**Covers:** FR1, NFR2

**Acceptance Criteria:**

- **Given** a repo configuration with one or more planning-artifact source paths
  **When** artifact discovery runs
  **Then** it returns the matching canonical planning files in a deterministic order
  **And** it records which files were selected in the local state output.
- **Given** both a whole markdown document and a sharded `index.md` variant for the same artifact class
  **When** discovery evaluates candidates
  **Then** it selects the whole-document source
  **And** it records why the sharded source was skipped.
- **Given** a configured source path contains no matching artifact for a required class
  **When** discovery completes
  **Then** the run reports the missing class as a structured warning
  **And** it does not silently substitute unrelated files.

### Story 1.2: Split markdown into stable reviewable sections

As a non-CLI stakeholder,
I want long BMAD artifacts split into focused sections with stable identities,
So that I can review and comment on a specific topic without losing continuity on later syncs.

**Covers:** FR2, UX-DR3, NFR4

**Acceptance Criteria:**

- **Given** a markdown planning artifact with headings and nested content
  **When** section normalization runs
  **Then** it emits reviewable sections with stable section identifiers derived from the document structure
  **And** it preserves parent-child relationships for later board planning.
- **Given** the same markdown content is normalized on two separate runs
  **When** the section structure has not changed
  **Then** the same section identifiers are produced
  **And** unchanged sections do not receive new identities.
- **Given** a section heading is renamed or moved
  **When** normalization runs again
  **Then** the output highlights the changed section identity and lineage in local state
  **And** unaffected sibling sections keep their existing identifiers.

### Story 1.3: Generate a deterministic board plan

As a stakeholder reviewing the board,
I want artifacts placed by phase, workstream, and collaboration intent,
So that I can orient quickly and see the difference between source content, review activity, and readiness signals.

**Covers:** FR3, FR5, FR6, UX-DR1, UX-DR2, UX-DR5, UX-DR6, NFR5, NFR6, NFR7, NFR8

**Acceptance Criteria:**

- **Given** a normalized set of artifact sections with artifact classes and workstream metadata
  **When** board planning runs
  **Then** it assigns each object to a deterministic BMAD phase zone
  **And** it groups each object under the appropriate workstream anchor.
- **Given** an artifact type that can be represented as either a doc or a summary table
  **When** the planner chooses an object strategy
  **Then** it uses collaboration intent rules rather than file extension alone
  **And** it emits the chosen object type in the plan output.
- **Given** the same artifact set and the same planning rules
  **When** the board plan is generated on repeated runs
  **Then** the ordered list of planned objects is identical
  **And** any change in the plan is attributable to a source-content or configuration change.

### Story 1.4: Publish initial objects and persist inspectable local state

As a BMAD operator,
I want the first publish run to create review-ready Miro objects and save a readable manifest,
So that future updates can reuse those identities and humans can inspect what happened locally.

**Covers:** FR3, NFR2, NFR4

**Acceptance Criteria:**

- **Given** a deterministic board plan for a first-time publish
  **When** the host executes the planned create operations
  **Then** each created object is captured in local state with artifact ID, section ID, target key, object type, and Miro object reference
  **And** the state file is readable as plain text in the repository.
- **Given** the publish run completes successfully
  **When** a human inspects local state
  **Then** they can trace each Miro object back to its source artifact and section
  **And** they can see the timestamp and content fingerprint used for that sync.
- **Given** a publish run fails after creating only part of the planned objects
  **When** the run exits
  **Then** local state records which objects were created and which remain pending
  **And** the partial state remains usable for a follow-up retry.

## Epic 2: Keep Board Continuity Across Repeated Syncs

Make repeated sync behavior trustworthy so the board stays stable, idempotent, and respectful of manual stewardship.

### Story 2.1: Reuse stable identities on repeat syncs

As a BMAD operator,
I want updated artifacts to match the same Miro objects on later runs,
So that comment history and traceability survive content changes.

**Covers:** FR4, NFR1, NFR2

**Acceptance Criteria:**

- **Given** local state contains a previously published artifact-section mapping
  **When** a new sync runs for unchanged content
  **Then** the planner matches the existing Miro object identity
  **And** it schedules an update only if the content fingerprint has changed.
- **Given** a source section still exists but its content changed
  **When** the sync planner compares fingerprints
  **Then** it targets the existing Miro object for update rather than create
  **And** it preserves the stable artifact and section identity in local state.
- **Given** a section was removed from the source artifact
  **When** repeat sync planning runs
  **Then** the plan marks the corresponding Miro object as removed or archived according to configured policy
  **And** the manifest records that transition instead of dropping history.

### Story 2.2: Preserve manual placement during updates

As a board steward,
I want known objects to stay where people placed them,
So that repeated syncs do not undo the board curation that helps humans navigate the workspace.

**Covers:** FR7, UX-DR4, NFR1, NFR5, NFR7

**Acceptance Criteria:**

- **Given** an existing Miro object has been manually moved after the initial publish
  **When** a repeat sync updates that object
  **Then** the update plan changes content and metadata only
  **And** it does not reset the object's stored position unless the object is new.
- **Given** a known object is resized or regrouped manually on the board
  **When** the next sync runs
  **Then** the sync preserves those manual layout choices for the existing object
  **And** it keeps the manifest mapping aligned to the same Miro object reference.
- **Given** a new section is introduced beside existing manually curated content
  **When** the board plan adds the new object
  **Then** only the new object receives automatic placement
  **And** neighboring existing objects keep their current placement.

### Story 2.3: Degrade gracefully when preferred Miro object types are unavailable

As a BMAD operator,
I want the sync to stay usable even when some Miro object types cannot be created,
So that collaboration can continue without blocking the entire publish or update run.

**Covers:** NFR3, NFR4

**Acceptance Criteria:**

- **Given** the board plan requests a preferred object type that the current Miro environment cannot create
  **When** the planner resolves publish operations
  **Then** it falls back to a supported representation defined by object-strategy rules
  **And** it records the fallback in local state and run output.
- **Given** a fallback object strategy is used for an artifact
  **When** stakeholders review the board
  **Then** the artifact remains readable and traceable
  **And** its labels still distinguish anchor content from review or readiness objects.
- **Given** a run encounters both supported and unsupported object types
  **When** publish or update completes
  **Then** supported objects are still processed successfully
  **And** the degraded-mode warnings are specific enough for the operator to review later.

## Epic 3: Turn Review Activity Into Decisions And Readiness Signals

Convert board activity into structured outputs that support triage and implementation handoff.

### Story 3.1: Ingest normalized comments with artifact and section traceability

As a BMAD operator,
I want Miro comments normalized into review artifacts with source references,
So that feedback can be acted on without losing the section context where it originated.

**Covers:** FR8, FR9, FR10

**Acceptance Criteria:**

- **Given** a set of Miro comments tied to published objects
  **When** comment ingest runs
  **Then** it outputs normalized review records with artifact ID, section ID, author, timestamp, topic, and body
  **And** every record points back to the originating published object.
- **Given** multiple comments refer to the same artifact section and topic
  **When** review artifacts are generated
  **Then** those comments are grouped under a shared review topic
  **And** individual comment provenance is retained.
- **Given** a comment is attached to an object whose manifest entry is missing
  **When** ingest runs
  **Then** the comment is reported as unresolved input
  **And** it is not silently merged into the wrong artifact bundle.

### Story 3.2: Triage feedback into decision records

As a product owner or architect,
I want grouped review signals converted into explicit decision states,
So that the team can tell what is open, accepted, deferred, resolved, or blocked.

**Covers:** FR10, FR11, UX-DR7, NFR8

**Acceptance Criteria:**

- **Given** a normalized review bundle grouped by artifact and topic
  **When** triage is performed
  **Then** each bundle is assigned a decision status from the approved vocabulary
  **And** the output records the rationale and owner for follow-up.
- **Given** a review topic remains unresolved
  **When** decision records are produced
  **Then** the topic stays marked as open or blocked
  **And** it is not collapsed into a resolved state without an explicit decision.
- **Given** decision outputs are viewed by non-technical participants
  **When** they scan the status labels
  **Then** labels are plain-language and distinguishable without color alone
  **And** deferred items are visibly different from accepted changes.

### Story 3.3: Generate readiness summaries and handoff outputs

As a delivery lead,
I want readiness summaries that roll up review outcomes across workstreams,
So that I can judge whether planning and solutioning are ready to hand off into implementation planning.

**Covers:** FR12, FR13, UX-DR5, UX-DR6, UX-DR7, NFR4, NFR6

**Acceptance Criteria:**

- **Given** decision records exist across product, UX, architecture, and delivery workstreams
  **When** readiness summaries are generated
  **Then** the output summarizes completeness, blockers, deferred items, and open questions by artifact and workstream
  **And** it identifies whether the handoff is ready, at risk, or blocked.
- **Given** unresolved blockers remain in one or more workstreams
  **When** the readiness summary is produced
  **Then** those blockers are listed explicitly in both board-facing and BMAD-facing outputs
  **And** they are not buried inside raw comment transcripts.
- **Given** a stakeholder needs a quick orientation view
  **When** they open the readiness output
  **Then** they can distinguish source artifacts, review activity, and readiness status without opening every detailed object
  **And** the summary remains understandable to non-CLI participants.

## Epic 4: Run The Collaboration Loop Through A Codex-First Path

Provide the operating path and boundaries that let teams use the collaboration system now without locking it to one host forever.

### Story 4.1: Configure and run a Codex-first collaboration workflow

As a BMAD operator,
I want one Codex-first workflow for publish, resync, ingest, and readiness generation,
So that I can operate the collaboration loop without inventing extra local process.

**Covers:** FR14, NFR2

**Acceptance Criteria:**

- **Given** repo-local configuration for source paths, board target, and enabled collaboration outputs
  **When** the Codex-first workflow runs
  **Then** it executes publish, update, ingest, and readiness steps in a documented order
  **And** each step reads and writes only repo-local artifacts and state.
- **Given** the operator completes a full collaboration cycle
  **When** they inspect the resulting outputs
  **Then** they can see which artifacts were published, what feedback was ingested, and which readiness outputs were generated
  **And** the workflow preserves BMAD as the canonical source of truth.
- **Given** one stage of the workflow cannot complete
  **When** the run stops
  **Then** the failure is isolated to that stage with actionable output
  **And** prior successful stages remain inspectable for recovery.

### Story 4.2: Expose host-neutral sync and publish boundaries

As an architect,
I want the core planning model separated from host-specific Miro execution,
So that future adapters can reuse the same artifact, planning, and review logic.

**Covers:** FR15, NFR1

**Acceptance Criteria:**

- **Given** the collaboration core produces discovery results, section models, board plans, and review outputs
  **When** a host adapter consumes those outputs
  **Then** the adapter only needs to execute host-specific I/O and return normalized results
  **And** it does not reimplement core planning rules.
- **Given** a future host runtime needs to publish the same artifact set
  **When** it uses the shared core interfaces
  **Then** it can reuse the same manifest, identity, and planning model
  **And** it preserves idempotent sync behavior.
- **Given** Codex remains the first operating path
  **When** the architecture is reviewed
  **Then** no core model assumes Codex-only data structures
  **And** host-neutral boundaries remain explicit in the backlog slice.
