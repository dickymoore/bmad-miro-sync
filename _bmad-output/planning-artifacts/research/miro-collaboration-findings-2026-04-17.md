# Miro Collaboration Findings

Date: 2026-04-17
Source: `fluidscan` validation runs in `../fluidscan`

## Objective

Extract product and UX lessons from the `fluidscan` Miro testbed so `bmad-miro-sync` can be reframed as a BMAD collaboration product rather than a file publishing utility.

## Evidence Reviewed

- `../fluidscan/docs/miro-sync.md`
- `../fluidscan/.bmad-miro-sync/run/plan.json`
- `../fluidscan/.bmad-miro-sync/run/results.json`
- `../fluidscan/.bmad-miro-sync/state.json`
- `../fluidscan/_bmad-output/planning-artifacts/*`

## Observed Facts

- The testbed successfully exported many artifact sections into separate Miro docs with stable IDs.
- The generated artifacts were organized at section granularity rather than as a single monolithic document.
- The host workflow already includes comment ingest back into BMAD review artifacts.
- The operating instructions emphasize preserving positions and manual organization when updating existing board objects.
- The workflow already treats Miro as a collaboration surface adjacent to BMAD, not as the source of truth.

## What Worked

### 1. Section-Level Publishing

Section granularity is good for review. It lets stakeholders comment on a specific area such as product intent, scope signals, or UX details without hunting through a whole document.

### 2. Stable Identity

Stable `artifact_id`, `target_key`, and manifest mappings preserve continuity. This is essential for repeat sync, comment reuse, and stakeholder trust.

### 3. Host-Assisted Loop

The Codex-first operating path is practical. One environment can generate artifacts, sync them into Miro, and bring comments back.

### 4. Manual Board Stewardship

Preserving existing positions is correct. People inevitably refine boards by hand, and the product should not fight that.

## What Did Not Yet Solve The Core Problem

### 1. Publishing Without Facilitation

The board can be populated, but not yet meaningfully facilitated. Users still need cues for what to review, what changed, and what is blocking progress.

### 2. Comments Without Triage

Comment ingest creates a review transcript, but not a decision system. There is no first-class notion of open decisions, accepted changes, deferrals, or unresolved blockers.

### 3. Visibility Without Role Framing

The same artifact set serves product, UX, and delivery audiences differently. The current model does not yet expose role-aware views or summary layers.

### 4. Sync-Centric Positioning

The current product story overstates the sync engine and understates the collaboration jobs users are actually trying to complete.

## Product Implications

- The product should be positioned as a BMAD collaboration layer in Miro.
- Sync should be treated as enabling infrastructure, not the core promise.
- Review states, decision tracking, and readiness summaries are MVP concerns.
- UX must optimize for non-CLI comprehension first.
- The testbed pattern in `fluidscan` should continue to validate board IA, review loops, and handoff design.

## UX Implications

- The board needs clearer phase zoning and workstream grouping.
- Stakeholders need “what changed,” “what needs input,” and “what is blocked” views.
- UX should support both deep artifact review and quick orientation.
- Comment-to-decision flow should be visible and low ambiguity.

## Architecture Implications

- The domain model needs review signals, decision records, and readiness summaries.
- Artifact mapping should be based on collaboration intent, not only document type.
- State needs to preserve traceability for both artifact content and review metadata.

## Recommended Product Direction

Define `bmad-miro-sync` as a collaboration system for BMAD planning and solutioning in Miro, validated through `fluidscan`, with the following MVP pillars:

1. structured artifact publishing
2. stakeholder review flows
3. decision and readiness tracking
4. traceable feedback return into BMAD
