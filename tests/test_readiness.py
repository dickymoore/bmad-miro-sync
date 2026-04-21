from __future__ import annotations

import unittest

from bmad_miro_sync.decisions import DecisionRecord
from bmad_miro_sync.readiness import (
    REQUIRED_READINESS_WORKSTREAMS,
    aggregate_readiness,
    render_handoff_output,
    render_readiness_summary,
    workstream_for_record,
)


class ReadinessAggregationTests(unittest.TestCase):
    def test_aggregate_readiness_blocks_when_any_blocked_topic_exists(self) -> None:
        result = aggregate_readiness(
            [
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/prd.md",
                    section_id="_bmad-output/planning-artifacts/prd.md#prd/goals",
                    section_title="PRD / Goals",
                    topic="Scope",
                    status="accepted",
                    owner="Product",
                    rationale="Aligned.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/ux-design-specification.md",
                    section_id="_bmad-output/planning-artifacts/ux-design-specification.md#ux-spec/accessibility",
                    section_title="UX Spec / Accessibility",
                    topic="Keyboard support",
                    status="blocked",
                    owner="UX",
                    rationale="Need explicit accessibility flows.",
                    follow_up_notes="Resolve before implementation handoff.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/architecture.md",
                    section_id="_bmad-output/planning-artifacts/architecture.md#architecture/deployment",
                    section_title="Architecture / Deployment",
                    topic="Hosting",
                    status="resolved",
                    owner="Architecture",
                    rationale="Deployment approach accepted.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/implementation-artifacts/epics.md",
                    section_id="_bmad-output/implementation-artifacts/epics.md#epics/story-sequencing",
                    section_title="Epics / Story sequencing",
                    topic="Sequencing",
                    status="accepted",
                    owner="Delivery",
                    rationale="Sequence accepted.",
                ),
            ]
        )

        self.assertEqual(result.overall_state, "blocked")
        self.assertEqual(result.blockers[0].workstream, "ux")
        self.assertEqual(result.workstreams["ux"].state, "blocked")
        self.assertEqual(result.workstreams["product"].state, "ready")
        self.assertEqual(result.missing_workstreams, [])

    def test_aggregate_readiness_marks_at_risk_when_coverage_or_open_items_remain(self) -> None:
        result = aggregate_readiness(
            [
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/prd.md",
                    section_id="_bmad-output/planning-artifacts/prd.md#prd/goals",
                    section_title="PRD / Goals",
                    topic="Metrics",
                    status="accepted",
                    owner="Product",
                    rationale="Metrics are good enough.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/architecture.md",
                    section_id="_bmad-output/planning-artifacts/architecture.md#architecture/interfaces",
                    section_title="Architecture / Interfaces",
                    topic="API shape",
                    status="deferred",
                    owner="Architecture",
                    rationale="Finalize after UX feedback lands.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/implementation-artifacts/sprint-status.yaml",
                    section_id="_bmad-output/implementation-artifacts/sprint-status.yaml#delivery",
                    section_title="Sprint Status / Delivery",
                    topic="Implementation sequencing",
                    status="resolved",
                    owner="Delivery",
                    rationale="Sequencing confirmed.",
                ),
            ]
        )

        self.assertEqual(result.overall_state, "at risk")
        self.assertEqual(result.missing_workstreams, ["ux"])
        self.assertEqual(result.deferred_items[0].workstream, "architecture")
        self.assertEqual(result.workstreams["ux"].has_review_evidence, False)
        self.assertEqual(result.workstreams["ux"].state, "at risk")
        self.assertIn("No decision-backed review evidence", result.workstreams["ux"].notes[0])

    def test_aggregate_readiness_only_marks_ready_with_full_covered_resolved_or_accepted_evidence(self) -> None:
        result = aggregate_readiness(
            [
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/prd.md",
                    section_id="_bmad-output/planning-artifacts/prd.md#prd/goals",
                    section_title="PRD / Goals",
                    topic="KPIs",
                    status="accepted",
                    owner="Product",
                    rationale="Accepted.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/ux-design-specification.md",
                    section_id="_bmad-output/planning-artifacts/ux-design-specification.md#ux/flows",
                    section_title="UX / Flows",
                    topic="Navigation",
                    status="resolved",
                    owner="UX",
                    rationale="Reviewed.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/architecture.md",
                    section_id="_bmad-output/planning-artifacts/architecture.md#architecture/data",
                    section_title="Architecture / Data",
                    topic="Schema",
                    status="accepted",
                    owner="Architecture",
                    rationale="Approved.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/implementation-artifacts/epics.md",
                    section_id="_bmad-output/implementation-artifacts/epics.md#epics/story-sequencing",
                    section_title="Epics / Story sequencing",
                    topic="Sequencing",
                    status="resolved",
                    owner="Delivery",
                    rationale="Ready for handoff.",
                ),
            ]
        )

        self.assertEqual(result.overall_state, "ready")
        self.assertEqual(result.missing_workstreams, [])
        self.assertEqual(result.blockers, [])
        self.assertEqual(result.deferred_items, [])
        self.assertEqual(result.open_questions, [])
        self.assertEqual(set(result.workstreams), set(REQUIRED_READINESS_WORKSTREAMS))

    def test_workstream_for_record_uses_artifact_classification(self) -> None:
        self.assertEqual(
            workstream_for_record(
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/product-brief.md",
                    section_id="product-brief#summary",
                    section_title="Brief / Summary",
                    topic="Vision",
                    status="accepted",
                    owner="Product",
                    rationale="Accepted.",
                )
            ),
            "product",
        )

    def test_render_outputs_keep_blockers_and_orientation_sections_visible(self) -> None:
        aggregate = aggregate_readiness(
            [
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/prd.md",
                    section_id="_bmad-output/planning-artifacts/prd.md#prd/goals",
                    section_title="PRD / Goals",
                    topic="KPIs",
                    status="accepted",
                    owner="Product",
                    rationale="Accepted.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/ux-design-specification.md",
                    section_id="_bmad-output/planning-artifacts/ux-design-specification.md#ux/flows",
                    section_title="UX / Flows",
                    topic="Navigation handoff",
                    status="blocked",
                    owner="UX",
                    rationale="Prototype annotations are incomplete.",
                    follow_up_notes="Add the missing transition notes before handoff.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/architecture.md",
                    section_id="_bmad-output/planning-artifacts/architecture.md#architecture/data",
                    section_title="Architecture / Data",
                    topic="Schema",
                    status="accepted",
                    owner="Architecture",
                    rationale="Approved.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/implementation-artifacts/epics.md",
                    section_id="_bmad-output/implementation-artifacts/epics.md#epics/story-sequencing",
                    section_title="Epics / Story sequencing",
                    topic="Sequencing",
                    status="resolved",
                    owner="Delivery",
                    rationale="Ready for handoff.",
                ),
            ]
        )

        summary = render_readiness_summary(aggregate)
        handoff = render_handoff_output(aggregate)

        self.assertIn("## Source Artifacts", summary)
        self.assertIn("## Review Activity", summary)
        self.assertIn("## Readiness Conclusions", summary)
        self.assertIn("Navigation handoff [Blocked]", summary)
        self.assertIn("Artifact: `_bmad-output/planning-artifacts/ux-design-specification.md`", summary)

        self.assertIn("## Workstream Handoff", handoff)
        self.assertIn("Ready for implementation handoff: No", handoff)
        self.assertIn("Navigation handoff [Blocked]", handoff)
        self.assertIn("Follow-up: Add the missing transition notes before handoff.", handoff)

    def test_handoff_output_lists_all_follow_up_categories_for_a_workstream(self) -> None:
        aggregate = aggregate_readiness(
            [
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/prd.md",
                    section_id="_bmad-output/planning-artifacts/prd.md#prd/goals",
                    section_title="PRD / Goals",
                    topic="KPIs",
                    status="accepted",
                    owner="Product",
                    rationale="Accepted.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/ux-design-specification.md",
                    section_id="_bmad-output/planning-artifacts/ux-design-specification.md#ux/flows",
                    section_title="UX / Flows",
                    topic="Navigation handoff",
                    status="blocked",
                    owner="UX",
                    rationale="Prototype annotations are incomplete.",
                    follow_up_notes="Add the missing transition notes before handoff.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/ux-design-specification.md",
                    section_id="_bmad-output/planning-artifacts/ux-design-specification.md#ux/accessibility",
                    section_title="UX / Accessibility",
                    topic="Keyboard order",
                    status="deferred",
                    owner="UX",
                    rationale="Finalize after copy review.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/ux-design-specification.md",
                    section_id="_bmad-output/planning-artifacts/ux-design-specification.md#ux/content",
                    section_title="UX / Content",
                    topic="Empty states",
                    status="open",
                    owner="UX",
                    rationale="Need final product wording.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/planning-artifacts/architecture.md",
                    section_id="_bmad-output/planning-artifacts/architecture.md#architecture/data",
                    section_title="Architecture / Data",
                    topic="Schema",
                    status="accepted",
                    owner="Architecture",
                    rationale="Approved.",
                ),
                self._record(
                    source_artifact_id="_bmad-output/implementation-artifacts/epics.md",
                    section_id="_bmad-output/implementation-artifacts/epics.md#epics/story-sequencing",
                    section_title="Epics / Story sequencing",
                    topic="Sequencing",
                    status="resolved",
                    owner="Delivery",
                    rationale="Ready for handoff.",
                ),
            ]
        )

        handoff = render_handoff_output(aggregate)

        self.assertIn("Blocking items:", handoff)
        self.assertIn("Deferred follow-up:", handoff)
        self.assertIn("Open questions:", handoff)
        self.assertIn("Navigation handoff [Blocked]", handoff)
        self.assertIn("Keyboard order [Deferred]", handoff)
        self.assertIn("Empty states [Open]", handoff)

    def test_handoff_output_keeps_general_follow_up_visible(self) -> None:
        aggregate = aggregate_readiness(
            [
                self._record(
                    source_artifact_id="docs/operator-notes.md",
                    section_id="docs/operator-notes.md#launch-checklist",
                    section_title="Operator Notes / Launch Checklist",
                    topic="Board permissions",
                    status="blocked",
                    owner="Ops",
                    rationale="Workspace access still missing.",
                    follow_up_notes="Grant access before handoff.",
                )
            ]
        )

        handoff = render_handoff_output(aggregate)

        self.assertIn("## Cross-Workstream Follow-Up", handoff)
        self.assertIn("Board permissions [Blocked]", handoff)
        self.assertIn("Artifact: `docs/operator-notes.md`", handoff)
        self.assertIn("Follow-up: Grant access before handoff.", handoff)

    @staticmethod
    def _record(
        *,
        source_artifact_id: str,
        section_id: str,
        section_title: str,
        topic: str,
        status: str,
        owner: str,
        rationale: str,
        follow_up_notes: str = "",
    ) -> DecisionRecord:
        return DecisionRecord(
            source_artifact_id=source_artifact_id,
            section_id=section_id,
            section_title=section_title,
            topic=topic,
            status=status,
            owner=owner,
            rationale=rationale,
            follow_up_notes=follow_up_notes,
        )
