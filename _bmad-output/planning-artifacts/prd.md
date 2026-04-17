# PRD: bmad-miro-sync

## 1. Overview

`bmad-miro-sync` enables BMAD teams to collaborate in Miro across product, UX, architecture, and delivery planning without requiring every stakeholder to operate in the CLI. The product uses sync and traceability infrastructure to publish BMAD artifacts into Miro, preserve their identity, capture structured feedback, and return collaboration outcomes into BMAD artifacts.

## 2. Problem Statement

BMAD planning quality depends on cross-functional review, but many required participants do not work in terminals or agent hosts. Current collaboration relies on screenshots, copy-paste, or ad hoc operator mediation. That creates drift, weak traceability, poor review visibility, and a fragile handoff from planning into implementation.

## 3. Goals

- enable non-CLI stakeholders to review BMAD planning artifacts in Miro
- support collaboration across product, UX, architecture, and delivery roles
- preserve stable traceability between BMAD source artifacts and Miro collaboration objects
- capture review feedback and route it back into BMAD in a structured form
- produce readiness signals that show whether solutioning is complete enough for implementation planning

## 4. Target Users

### Primary Users

- business analysts
- product owners and product managers
- scrum masters and delivery leads
- UX and design stakeholders
- BMAD operators coordinating planning output

### Secondary Users

- architects and engineering leads
- executive or sponsor reviewers who need visibility without editing source artifacts

## 5. Product Principles

- BMAD artifacts remain canonical
- collaboration beats document dumping
- Miro should lower participation friction for non-CLI users
- updates must preserve context and continuity
- feedback must lead to decisions, not just accumulate

## 6. User Jobs To Be Done

- As a product stakeholder, I want to understand the current BMAD plan in Miro so I can give useful feedback without asking for a walkthrough.
- As a UX stakeholder, I want to review flows, requirements, and assumptions in one shared space so I can spot gaps early.
- As a delivery lead, I want to see what is decided, unresolved, or blocked so I can judge readiness.
- As a BMAD operator, I want feedback to come back into BMAD with traceability so the source artifacts stay coherent.

## 7. MVP Scope

### In Scope

- publish BMAD planning artifacts and sections into Miro
- deterministic board organization by phase and workstream
- stable artifact IDs and manifest-backed update behavior
- comment ingest into BMAD review artifacts
- review states and decision-tracking outputs
- readiness summaries for planning and solutioning handoff
- Codex-first operating path

### Out Of Scope

- direct rich-text editing in Miro that writes back into BMAD source documents
- multi-project portfolio management
- fully automated decision resolution without operator review
- implementation execution from within Miro

## 8. Core Workflows

### Workflow A: Publish For Review

1. BMAD workflow generates or updates artifacts in `_bmad-output`.
2. `bmad-miro-sync` exports section-aware operations.
3. The host executes Miro operations.
4. Miro reflects updated artifacts without breaking stable identity.

### Workflow B: Stakeholder Review

1. Stakeholders open phase and workstream areas in Miro.
2. They review artifacts and leave comments or structured review notes.
3. The operator ingests those signals back into BMAD review artifacts.

### Workflow C: Triage And Readiness

1. Review signals are grouped by artifact and topic.
2. Decisions are marked as open, accepted, deferred, resolved, or blocked.
3. Readiness summaries identify remaining gaps before implementation planning.

## 9. Functional Requirements

### Artifact Publishing

- The system must discover BMAD planning artifacts from configured paths.
- The system must split markdown artifacts into stable reviewable sections.
- The system must generate deterministic Miro object plans for those sections.
- The system must preserve artifact identity across repeated syncs.

### Collaboration Structure

- The system must organize Miro content by BMAD phase.
- The system must support grouping by workstream such as product, UX, architecture, and delivery.
- The system must preserve existing manual placement when updating known objects.

### Review Ingest

- The system must ingest normalized Miro comments into BMAD review artifacts.
- The system must preserve artifact and section references for each ingested signal.
- The system should support grouping feedback by artifact, section, and topic.

### Decision And Readiness Outputs

- The product must support a tracked status for review items or decisions.
- The product must generate or support readiness summaries for planning and solutioning outcomes.
- The product should highlight unresolved blockers and deferred items.

### Operating Path

- The MVP must support Codex as the first execution environment.
- The architecture should allow later host adapters to reuse the same core model.

## 10. Non-Functional Requirements

- repeated syncs should be idempotent from the board’s perspective
- local state must be durable and human-inspectable
- the product should remain usable even if some Miro object types are unavailable
- artifact and decision outputs should be understandable by non-technical participants

## 11. UX Requirements

- a stakeholder must be able to orient themselves quickly on the board
- the board should separate artifact content from review and readiness signals
- the system should avoid visual noise and redundant duplication
- review state labels should be easy to scan

## 12. Success Metrics

- time to orient a non-CLI stakeholder to current planning status
- percentage of review feedback that returns to BMAD with artifact traceability
- reduction in duplicate or outdated stakeholder review surfaces
- number of planning artifacts that reach explicit solutioning readiness in the shared workspace

## 13. Risks And Mitigations

- Risk: Miro clutter makes review harder.
  Mitigation: phase zoning, workstream grouping, and opinionated defaults.

- Risk: feedback becomes an unstructured comment dump.
  Mitigation: decision states and grouped review artifacts.

- Risk: users treat Miro as the source of truth.
  Mitigation: explicit canonical-source rules and artifact traceability.

## 14. Open Questions

- What is the best default visual representation for epics and stories?
- How much decision-state metadata should be surfaced directly in Miro?
- Which readiness summary views are most helpful to delivery leads versus product stakeholders?
