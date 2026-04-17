# Sprint Change Proposal: bmad-miro-sync

Date: 2026-04-17
Change trigger: Strategic pivot based on Miro validation in `fluidscan`
Mode: Batch
Scope classification: Major

## 1. Issue Summary

The current project framing describes `bmad-miro-sync` as a reusable tool that publishes BMAD artifacts into Miro. That framing is too narrow and now incorrect. The `fluidscan` testbed showed that section-level publishing, stable IDs, and comment ingest are useful, but they only create visibility. The actual product need is collaboration across BMAD stakeholders who do not work in the CLI.

This is a strategic pivot and a misunderstanding correction:

- `fluidscan` is a separate testbed, not the product itself
- sync is enabling infrastructure, not the core product promise
- the product must serve business analysts, product owners, scrum masters, UX and design stakeholders, and similar non-CLI users

## 2. Checklist Status

### Section 1: Understand The Trigger And Context

- [x] 1.1 Trigger identified: existing product brief and architecture framed the product as sync-first
- [x] 1.2 Core problem defined: strategic pivot and requirement misunderstanding
- [x] 1.3 Evidence gathered: `fluidscan` Miro export results, stable manifest mappings, comment-ingest flow, and lack of collaboration-specific planning artifacts

### Section 2: Epic Impact Assessment

- [x] 2.1 Current epic viability: current implicit sync-first implementation direction is no longer sufficient
- [x] 2.2 Epic-level change required: redefine scope around collaboration model, review loop, and readiness outputs
- [x] 2.3 Future epic review completed: all future work must align to collaboration-first positioning
- [x] 2.4 New epics required: review/decision and readiness epics added
- [x] 2.5 Priority change required: collaboration model and UX move ahead of implementation detail

### Section 3: Artifact Conflict And Impact Analysis

- [x] 3.1 Product brief conflicts identified
- [x] 3.2 Architecture conflicts identified
- [!] 3.3 UX specification missing and required
- [!] 3.4 PRD and epics missing and required

### Section 4: Path Forward Evaluation

- [x] 4.1 Direct adjustment: partially viable but insufficient alone
- [ ] 4.2 Potential rollback: not recommended because current implementation concepts remain useful as infrastructure
- [x] 4.3 PRD MVP review: required
- [x] 4.4 Selected approach: Hybrid leaning to Option 3

### Section 5: Proposal Components

- [x] 5.1 Issue summary created
- [x] 5.2 Epic and artifact adjustments documented
- [x] 5.3 Recommended path forward documented
- [x] 5.4 MVP impact defined
- [x] 5.5 Handoff plan defined

### Section 6: Final Review And Handoff

- [x] 6.1 Checklist complete
- [x] 6.2 Proposal accuracy verified against current repo artifacts and `fluidscan` evidence

## 3. Impact Analysis

### Epic Impact

- The implicit sync-engine-first roadmap is replaced by a collaboration-first roadmap.
- New epics are required for collaboration model, feedback triage, and readiness.
- UX and information architecture become mandatory MVP workstreams rather than optional polish.

### Story Impact

- existing implementation direction should be treated as retained infrastructure, not discarded product value
- future stories must explicitly support stakeholder orientation, review, decisions, and handoff

### Artifact Conflicts

- `product-brief.md` required full rewrite of problem, users, product goal, and MVP scope
- `architecture.md` required full rewrite of system purpose and major components
- `prd.md` did not exist and was required
- `ux-design-specification.md` did not exist and was required
- `epics.md` did not exist and was required

### Technical Impact

- implementation should later prioritize collaboration object model and readiness outputs
- sync/manifest components remain useful but are demoted to enabling infrastructure
- no implementation work should proceed until collaboration design is accepted

## 4. Recommended Approach

Recommended path: Hybrid with MVP review.

Rationale:

- Directly patching the existing brief and architecture would leave the repo without a proper PRD, UX spec, or epics set.
- Rolling back current implementation thinking would waste valid lessons from `fluidscan`.
- The correct move is to preserve the reusable sync and traceability concepts while redefining the product around collaboration workflows and completing the missing solutioning artifacts.

Effort estimate: Medium
Risk level: Medium
Timeline impact: positive overall because it prevents the team from implementing the wrong product

## 5. Detailed Change Proposals

### Product Brief

OLD:

- reusable synchronization tool that publishes BMAD outputs into Miro
- primary value framed as visibility
- primary users included operators and technical stakeholders

NEW:

- collaboration layer for BMAD in Miro
- primary value framed as structured cross-functional collaboration for non-CLI stakeholders
- sync reframed as enabling infrastructure
- users expanded to business analysts, product owners, scrum masters, UX/design stakeholders, and delivery leads

Rationale: corrects the product thesis and aligns the brief to validated user needs.

### Architecture

OLD:

- three-layer design centered on core sync engine, delivery interfaces, and state/configuration
- collaboration concerns were implicit

NEW:

- four-layer design centered on artifact/sync core, collaboration model, review/decision pipeline, and delivery interfaces
- explicit lesson capture from `fluidscan`
- readiness outputs and collaboration objects added to the domain model

Rationale: architecture must represent the actual product, not just its transport mechanism.

### PRD

OLD:

- missing

NEW:

- new PRD covering goals, users, workflows, functional requirements, UX requirements, and success metrics

Rationale: solutioning cannot finish cleanly without a product requirements baseline.

### UX Specification

OLD:

- missing

NEW:

- board information architecture, stakeholder flows, object types, and validation plan

Rationale: the product is Miro-facing and non-CLI user experience is central to its value.

### Epics And Stories

OLD:

- missing

NEW:

- epics for collaboration foundation, review loop, readiness, and operating path

Rationale: backlog decomposition must follow the corrected product direction.

## 6. Implementation Handoff

This change is Major.

Handoff recipients:

- Product Manager: confirm corrected product positioning and MVP boundaries
- UX/Design: validate board IA, role-aware flows, and review ergonomics
- Architect: validate collaboration domain model and integration boundaries
- Product Owner / Delivery Lead: convert epics into implementation sequencing only after readiness review

Success criteria for implementation planning:

- all implementation work references collaboration-first artifacts
- no workstream treats Miro as a generic file dump target
- review and readiness workflows remain in MVP scope

## 7. Deliverables Produced

- updated `product-brief.md`
- updated `architecture.md`
- new `prd.md`
- new `ux-design-specification.md`
- new `epics.md`
- new `research/miro-collaboration-findings-2026-04-17.md`
- new `solutioning-readiness.md`
