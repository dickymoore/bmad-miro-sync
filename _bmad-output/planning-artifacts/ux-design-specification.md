# UX Design Specification: bmad-miro-sync

## 1. UX Objective

Design a Miro collaboration experience that makes BMAD planning and solutioning understandable and actionable for non-CLI stakeholders while preserving a clear path back to BMAD source artifacts.

## 2. Primary Personas

### Business Analyst / Product Owner

Needs to review scope, assumptions, and stories; compare requirements across artifacts; and capture structured decisions.

### UX / Design Stakeholder

Needs to review flows, user-facing implications, open questions, and trade-offs without reading source files locally.

### Scrum Master / Delivery Lead

Needs to assess readiness, blockers, sequencing, and handoff completeness.

### BMAD Operator

Needs to publish updates, preserve board continuity, ingest feedback, and keep BMAD authoritative.

## 3. UX Principles

- orient first, detail second
- separate artifacts from review noise
- preserve continuity across updates
- support both design-focused and delivery-focused scanning
- make unresolved issues impossible to hide

## 4. Information Architecture

The board should be structured into persistent zones:

### Analysis

- brainstorming outputs
- product context and research
- early framing artifacts

### Planning

- product brief
- PRD
- requirement decisions

### Solutioning

- UX specification
- architecture
- epics and story decomposition

### Implementation Readiness

- readiness summaries
- unresolved blockers
- handoff notes

### Delivery Feedback

- ingested review bundles
- decision logs
- follow-up queues

## 5. Core UX Flows

### Flow A: Stakeholder Orientation

1. User enters the board.
2. User sees phase zones and workstream anchors.
3. User finds a “start here” summary and readiness markers.
4. User selects an artifact or summary based on role and task.

### Flow B: Artifact Review

1. User opens a section-level artifact.
2. User reads the focused content rather than a full monolith.
3. User comments or flags gaps.
4. The feedback remains tied to the same section through future updates.

### Flow C: Triage Review

1. Operator ingests comments into BMAD.
2. Review bundle groups comments by artifact and topic.
3. Decision state is assigned.
4. Readiness summaries update to reflect unresolved items.

## 6. Screen/Object Types

### Anchor Docs

Used for product brief, PRD, UX, architecture, research, and grouped story narratives.

### Summary Tables

Used for decision registers, readiness summaries, and story status overviews.

### Review Objects

Used to cluster open questions, accepted changes, deferred items, and blockers.

## 7. Board Behavior Requirements

- updates should keep known objects in place
- parent-child section relationships should remain visually understandable
- objects that need review should be visually distinct from archival or resolved content
- the board should tolerate manual curation without being overwritten

## 8. Role-Aware Lenses

The UX should support at least three scanning modes even if implemented through conventions rather than separate apps:

- Product lens: scope, assumptions, priorities, and decisions
- UX lens: user journeys, requirements clarity, and unresolved experience questions
- Delivery lens: readiness, blockers, sequencing, and handoff completeness

## 9. Accessibility And Comprehension

- headings and labels must be plain-language and scan-friendly
- status markers should not rely on color alone
- summary content must be readable without opening every detail object
- board structure should remain understandable for first-time viewers

## 10. MVP UX Decisions

- prioritize docs and summary tables over ambitious visual automation
- use section-level artifacts by default
- introduce explicit decision and readiness views
- optimize for shared understanding, not decorative density

## 11. UX Risks

- too many objects can fragment understanding
- too few summaries force users into deep document reading
- review content can overwhelm anchor artifacts unless separated

## 12. Recommended UX Validation In `fluidscan`

- test whether non-CLI reviewers can find the right artifact without guidance
- test whether open decisions are obvious within two minutes
- test whether delivery stakeholders can identify blockers without reading raw comments
