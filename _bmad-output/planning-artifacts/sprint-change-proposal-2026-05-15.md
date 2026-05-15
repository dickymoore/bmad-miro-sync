# Sprint Change Proposal: Richer Inline Grouping For Review Cards

## 1. Issue Summary

During live `fluidscan` validation, review-oriented hybrid cards were still splitting semantically connected inline markdown structures into separate cards. The trigger example was:

- `**Recommended Techniques:**`
- followed by a short list of techniques

That split forced reviewers to reconstruct meaning across adjacent cards even when the source intent was clearly one introduced content group. The earlier fix handled only the simplest `label + one block` case and was therefore incomplete.

### Evidence

- Live board example: `Technique Selection` split `Recommended Techniques` awkwardly.
- Source markdown pattern in brainstorming outputs:
  - bold label-only line
  - followed by a short list or short explanatory paragraph
- Counter-example in the same source:
  - `**Key Ideas Generated:**`
  - followed by many repeated labeled category entries, which should remain separate.

## 2. Impact Analysis

### Epic Impact

- **Epic 1: Publish A Review-Ready BMAD Workspace**
  - impacted directly
  - no epic scope change required
  - acceptance interpretation tightened: section-aware publication must preserve inline semantic groupings when they fit naturally into one review card

### Story Impact

- **Story 1.2: Split markdown into stable reviewable sections**
  - affected because "reviewable sections" now needs an explicit inline grouping rule for label-led content blocks
- **Story 1.3: Generate a deterministic board plan**
  - affected because grouped blocks must remain deterministic and must not collapse repeated collections

### Artifact Conflicts

- **PRD**
  - no goal conflict
  - change strengthens the requirement that the board be understandable without opening repo source
- **Architecture**
  - no architectural layer change
  - reinforces that block parsing belongs in the host-neutral artifact/sync core
- **UX Design**
  - directly aligned with:
    - orient first, detail second
    - section-level reviewability
    - avoiding review noise

### Technical Impact

- parser rule change in markdown block extraction
- planner behavior change where richer grouped blocks can now trigger full section compaction when the whole section fits naturally in one card
- renderer already supports grouped/compound body cards and compact sections, so no new host contract was needed

## 3. Recommended Approach

### Selected Path

- **Option 1: Direct Adjustment**

### Rationale

This is not a strategic or scope-level change. It is a refinement to the parsing and carding model inside the current MVP architecture. The correct place to solve it is in the inline block extractor, not by adding more section-level exceptions.

### Effort / Risk

- Effort: Medium
- Risk: Low to Medium

### Why this path

- preserves existing hybrid review model
- generalizes the rule beyond the original single example
- avoids introducing document-specific heuristics
- keeps repeated collections like idea/category inventories separate

## 4. Detailed Change Proposals

### Parser Rule Expansion

#### OLD

- label-only paragraph could merge only with one immediately following short list or one short paragraph

#### NEW

- label-only paragraph can merge with a short content group:
  - short paragraph
  - short list
  - short paragraph + short list
  - short paragraph + short list + short follow-up paragraph
- merge stops when:
  - a repeated labeled series begins
  - another label-only lead-in begins
  - content exceeds size/sentence/item thresholds

#### Rationale

This better matches the source authoring style used in BMAD outputs, especially brainstorming and facilitation artifacts.

### Planner Behavior Clarification

#### OLD

- grouped body blocks existed, but only narrow patterns reached them

#### NEW

- if richer grouping causes an entire section to fit cleanly into one review card, the planner may emit that section as `section_compact`

#### Rationale

This directly matches the intended principle:

- if a section fits in one card reasonably, keep it in one card
- if it becomes a collection, fan it out

### Test Coverage Expansion

Added targeted coverage for:

- label + list
- label + paragraph + list + paragraph
- repeated labeled series staying split
- planner-level hybrid expansion using the richer grouping rules

## 5. Implementation Handoff

### Scope Classification

- **Minor to Moderate**

### Handoff

- **Developer agent**
  - maintain parser thresholds and grouping rules
  - validate additional source families if new inline authoring patterns appear

### Success Criteria

- introductory bold labels remain attached to the short content they introduce
- repeated labeled collections remain split into separate review cards
- deterministic planning remains stable
- no document-specific special casing is required

## 6. Approval State

Implemented as an approved direct course correction based on live review evidence from `fluidscan`.
