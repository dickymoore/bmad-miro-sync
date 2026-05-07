# Miro Board Taxonomy

This document names the visual objects used by `bmad-miro-sync` when publishing BMAD outputs into Miro.

## Top-Level Structures

### Phase Column
- Internal item type: `zone`
- Purpose: Represents a BMAD phase such as `Analysis`, `Planning`, or `Solutioning`
- Visual treatment:
  - pale tinted full-height background
  - stronger border
  - phase title at the top
- Layout role:
  - one phase column per BMAD phase
  - phases progress left-to-right when `layout.phase_axis = "horizontal"`

### Phase Separator
- Internal item type: `phase_separator`
- Purpose: Creates a visible divider between adjacent phase columns
- Visual treatment:
  - thin vertical tinted line between phases
- Layout role:
  - one separator between each adjacent pair of rendered phase columns

### Workstream Header
- Internal item type: `workstream_anchor`
- Purpose: Labels a workstream lane within a phase, for example `Product` or `UX`
- Visual treatment:
  - high-contrast capsule/header card
  - uses workstream accent color
- Layout role:
  - anchors source frames within a given phase/workstream column

## Content Structures

### Source Frame
- Internal item type: `source_frame`
- Purpose: Container for one BMAD source artifact such as `PRD`, `Product Brief`, or `Technical Research`
- Visual treatment:
  - light framed container behind a set of cards
- Layout role:
  - groups all cards from one BMAD source file

### Source Header Card
- Internal item type: `doc`
- Artifact id pattern: `source_header:<source_artifact_id>`
- Purpose: Human-facing title card inside a source frame
- Visual treatment:
  - stronger header card than normal content cards
  - includes artifact title and subtitle like `Product · 12 sections`
- Layout role:
  - always appears at the top of a source frame

### Major Card
- Internal item type: `doc`
- Purpose: Represents a major section or root-level summary card
- Visual treatment:
  - slightly stronger fill and border than a normal card
- Layout role:
  - summary-first reading path inside a source frame

### Standard Card
- Internal item type: `doc`
- Purpose: Represents a normal section card within a source frame
- Visual treatment:
  - white card with colored border accent
- Layout role:
  - detail content under a source frame

### Table Card
- Internal item type: `table`
- Purpose: Structured summaries such as readiness/status/story tables
- Visual treatment:
  - Miro text/table rendering
- Layout role:
  - used where structured fields are better than prose cards

## Mapping from BMAD Source Files to Frames

Examples:
- `prd.md` -> `PRD`
- `product-brief-*.md` -> `Product Brief`
- `product-brief-*-distillate.md` -> `Product Brief Distillate`
- `technical-*-research-*.md` -> `Technical Research`
- `market-*-research-*.md` -> `Market Research`
- `ux-design-specification.md` -> `UX Design Specification`
- `brainstorming-session-*.md` -> `Brainstorming Session`

## What Is Customizable

Project-local customization lives in `.bmad-miro.toml`.

### Colors you can already customize
- `[layout.phase_colors]`
  - controls phase column tint color
- `[layout.workstream_colors]`
  - controls workstream headers, source header accents, and card border accents

### Layout you can already customize
- `layout.phase_axis`
- `layout.phase_gap_x`
- `layout.phase_gap_y`
- `layout.phase_column_padding_x`
- `layout.phase_column_padding_top`
- `layout.phase_column_padding_bottom`
- `layout.phase_fill_opacity`
- `layout.phase_border_width`
- `layout.phase_border_lighten`
- `layout.phase_border_darken`
- `layout.phase_separator_width`
- `layout.phase_separator_fill_opacity`
- `layout.phase_separator_border_width`
- `layout.phase_separator_lighten`
- `layout.phase_separator_border_darken`
- `layout.doc_width`
- `layout.content_gap_y`
- `layout.source_gap_y`
- `layout.source_header_height`
- `layout.workstream_header_width`
- `layout.workstream_header_height`
- `layout.zone_title_font_size`
- `layout.workstream_title_font_size`
- `layout.source_title_font_size`
- `layout.doc_font_size`

### What is not yet user-configurable
- major-card vs standard-card styling thresholds

Those remaining values are still renderer defaults in code and can be promoted later if needed.
