# Product Brief: bmad-miro-sync

## Summary

`bmad-miro-sync` is a collaboration layer that makes BMAD planning and solutioning usable inside Miro for teams that include non-CLI participants. The product is not a generic file publisher. It is a structured shared workspace for business analysts, product owners, scrum masters, UX and design stakeholders, and delivery leads to review, comment on, organize, and progress BMAD artifacts without needing to work in a terminal session.

The sync engine remains important, but only as enabling infrastructure. Its job is to keep BMAD artifacts and Miro views aligned so collaboration can happen around stable, reviewable representations of the work. The product value is the collaboration loop: publish into Miro, orient stakeholders, capture structured feedback, route decisions back into BMAD, and keep planning artifacts moving toward implementation readiness.

## Problem

BMAD workflows work well for operators and agent-driven planning, but the surrounding product and delivery team often lives outside the CLI. In practice, those stakeholders need to:

- understand the current state of a product brief, PRD, UX direction, architecture, and story plan
- add feedback in a shared visual workspace
- see which decisions are open, accepted, rejected, or unresolved
- collaborate across design and delivery perspectives without asking one operator to manually relay every update

The Miro tests in `fluidscan` validated that raw artifact export is helpful but insufficient on its own. Section-level docs, stable identities, and repeatable sync reduced drift, but they did not yet provide enough support for review workflows, stakeholder orientation, decision capture, or backlog shaping. A file dump into Miro improves visibility. It does not solve collaboration.

## Users

Primary users:

- business analysts shaping requirements and acceptance criteria
- product owners and product managers driving scope and prioritization
- scrum masters and delivery leads coordinating readiness and handoff
- UX and design stakeholders reviewing flows, artifacts, and decisions
- BMAD operators who need a reliable collaboration surface for non-CLI teammates

Secondary users:

- architects and engineering leads validating technical direction
- sponsors and reviewers who need structured visibility into planning progress

## Product Goal

Create a Miro-based BMAD collaboration layer that enables design-focused and delivery-focused stakeholders to participate in planning and solutioning work through shared, structured, traceable workflows.

## Non-Goals For MVP

- a full bidirectional rich-text editor for every BMAD artifact
- replacing BMAD as the source of truth
- turning Miro into a generic document management system
- broad program portfolio management across many boards
- implementation orchestration inside Miro

## MVP Scope

The MVP should support:

- publishing BMAD planning artifacts into a deterministic Miro collaboration space
- stable artifact and section identity so updates preserve context and comments
- board structure that separates analysis, planning, solutioning, and implementation-readiness views
- role-aware views for product, UX, and delivery collaboration
- structured review loops:
  - comment capture
  - decision triage
  - status markers for open, resolved, deferred, and blocked items
- import of normalized Miro feedback back into BMAD review artifacts
- lightweight facilitation affordances such as review queues, readiness markers, and handoff summaries
- a Codex-first operating path with room for other hosts later

## Product Shape

The product has three visible layers:

1. Collaboration workspace model
2. Sync and traceability engine
3. Host-specific operating path

The collaboration workspace model defines how artifacts appear in Miro, how stakeholders review them, and how decisions move forward. The sync and traceability engine keeps local BMAD outputs and Miro representations aligned. The host-specific operating path lets a BMAD operator execute the loop from Codex first, then other hosts later.

## Success Criteria

The MVP is successful if:

- a non-CLI stakeholder can understand the current BMAD state from Miro without operator translation
- product, UX, and delivery feedback can be captured and routed back into BMAD with low ambiguity
- repeated syncs preserve artifact identity, comments, and board organization
- teams can move from product brief through solutioning with clear readiness signals
- the collaboration model works in a live testbed repo such as `fluidscan` and generalizes to other BMAD projects

## Risks

- Miro can become a cluttered artifact graveyard if collaboration states and review flows are not opinionated
- if comments are ingested without triage structure, review noise will overwhelm planning artifacts
- teams may assume Miro is the source of truth unless traceability rules are explicit
- delivery stakeholders and design stakeholders may need different information density on the same board
- host-specific limitations may constrain how much workflow automation can happen in a single run

## Initial Direction

Codex remains the first supported operating path because it can run BMAD workflows and Miro actions in one environment. `fluidscan` remains a separate testbed repo used to validate collaboration patterns, board structure, feedback ingest, and readiness workflows before those patterns are formalized in `bmad-miro-sync`.
