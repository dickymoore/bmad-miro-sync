from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.decisions import (
    DEFAULT_DECISION_RECORDS_OUTPUT,
    decision_result_from_dict,
    decision_result_to_dict,
    triage_feedback,
    write_decision_records,
    write_decision_sidecar,
)
from bmad_miro_sync.manifest import SyncManifest


class DecisionTriageTests(unittest.TestCase):
    def test_triage_feedback_rejects_non_object_review_input(self) -> None:
        manifest = SyncManifest(version=3, items={})

        with self.assertRaisesRegex(ValueError, "Review input must be a JSON object"):
            triage_feedback(manifest, [])  # type: ignore[arg-type]

    def test_triage_feedback_requires_comments_list(self) -> None:
        manifest = SyncManifest(version=3, items={})

        with self.assertRaisesRegex(ValueError, "Review input must include a 'comments' list"):
            triage_feedback(manifest, {})

    def test_triage_feedback_defaults_to_open_for_untriaged_bundle(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Please expand the acceptance criteria.",
                }
            ]
        }

        result = triage_feedback(manifest, payload)

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].status, "open")
        self.assertEqual(result.records[0].owner, "Awaiting triage")
        self.assertEqual(result.records[0].rationale, "Awaiting triage")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_DECISION_RECORDS_OUTPUT
            write_decision_records(result, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("# Decision Records", content)
            self.assertIn("Open topics: 1", content)
            self.assertIn("Status: Open", content)
            self.assertIn("Owner: Awaiting triage", content)
            self.assertIn("Rationale: Awaiting triage", content)
            self.assertIn("#### Acceptance criteria", content)

    def test_triage_feedback_rejects_unknown_status_values(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Scope",
                    "author": "Jane Doe",
                    "body": "Need tighter scope boundaries.",
                }
            ],
            "triage": [
                {
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Scope",
                    "status": "done",
                    "owner": "Product",
                    "rationale": "This is complete.",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "Unknown decision status"):
            triage_feedback(manifest, payload)

    def test_triage_feedback_requires_explicit_topic_in_triage_assignments(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Scope",
                    "author": "Jane Doe",
                    "body": "Need tighter scope boundaries.",
                }
            ],
            "triage": [
                {
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "status": "open",
                    "owner": "Product",
                    "rationale": "Still under review.",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "Each triage assignment must include: topic\\."):
            triage_feedback(manifest, payload)

    def test_triage_feedback_keeps_unresolved_inputs_visible_and_never_auto_resolved(self) -> None:
        manifest = SyncManifest(version=3, items={})
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Manifest mapping",
                    "author": "Jane Doe",
                    "body": "This comment was attached to an unpublished section.",
                }
            ]
        }

        result = triage_feedback(manifest, payload)

        self.assertEqual(len(result.records), 1)
        self.assertTrue(result.records[0].is_unresolved)
        self.assertEqual(result.records[0].status, "open")

        invalid_payload = {
            **payload,
            "triage": [
                {
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Manifest mapping",
                    "status": "resolved",
                    "owner": "Delivery",
                    "rationale": "Mark it done anyway.",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "Unresolved bundles may only be triaged as open or blocked"):
            triage_feedback(manifest, invalid_payload)

        blocked_payload = {
            **payload,
            "triage": [
                {
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Manifest mapping",
                    "status": "blocked",
                    "owner": "Delivery",
                    "rationale": "Need a valid manifest mapping before this can move.",
                }
            ],
        }
        blocked = triage_feedback(manifest, blocked_payload)
        self.assertEqual(blocked.records[0].status, "blocked")

    def test_triage_feedback_rejects_ambiguous_duplicate_section_topic_bundles(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                },
                "_bmad-output/planning-artifacts/prd.md#prd/risks": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Risks",
                    "item_id": "doc-456",
                    "item_type": "doc",
                },
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Scope",
                    "author": "Jane Doe",
                    "body": "This is a valid comment on Goals.",
                },
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/risks",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "topic": "Scope",
                    "author": "John Doe",
                    "body": "This mismatched reference must remain unresolved.",
                },
            ],
            "triage": [
                {
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "topic": "Scope",
                    "status": "accepted",
                    "owner": "Product",
                    "rationale": "Apply the requested change to Goals.",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "matched multiple grouped bundles"):
            triage_feedback(manifest, payload)

        payload["triage"][0]["source_artifact_id"] = "_bmad-output/planning-artifacts/other.md"
        with self.assertRaisesRegex(ValueError, "No grouped bundle matched triage entry"):
            triage_feedback(manifest, payload)

    def test_decision_result_serialization_round_trips_record_data(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Please expand the acceptance criteria.",
                }
            ],
            "triage": [
                {
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "status": "deferred",
                    "owner": "Product",
                    "rationale": "Queue it behind implementation readiness work.",
                    "follow_up_notes": "Revisit after Story 3.3.",
                }
            ],
        }

        result = triage_feedback(manifest, payload)
        serialized = decision_result_to_dict(result)
        restored = decision_result_from_dict(serialized)

        self.assertEqual(len(restored.records), 1)
        self.assertEqual(restored.records[0].status, "deferred")
        self.assertEqual(restored.records[0].owner, "Product")
        self.assertEqual(restored.records[0].follow_up_notes, "Revisit after Story 3.3.")
        self.assertEqual(restored.records[0].published_object_reference, "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals")
        self.assertEqual(restored.records[0].comments[0].body, "Please expand the acceptance criteria.")

        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "_bmad-output/review-artifacts/decision-records.json"
            write_decision_sidecar(result, output_path=sidecar_path)
            stored = decision_result_from_dict(__import__("json").loads(sidecar_path.read_text(encoding="utf-8")))
            self.assertEqual(stored.records[0].rationale, "Queue it behind implementation readiness work.")

    def test_decision_result_deserialization_rejects_unknown_status_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown decision status 'done' in serialized decision record"):
            decision_result_from_dict(
                {
                    "decision_records": [
                        {
                            "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                            "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                            "section_title": "PRD / Goals",
                            "topic": "Scope",
                            "status": "done",
                            "owner": "Product",
                            "rationale": "Complete.",
                            "comments": [],
                            "unresolved_reasons": [],
                        }
                    ]
                }
            )

    def test_decision_result_deserialization_rejects_resolved_unresolved_records(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Serialized unresolved decision records may only be open or blocked.",
        ):
            decision_result_from_dict(
                {
                    "decision_records": [
                        {
                            "source_artifact_id": "unresolved-inputs",
                            "section_id": "missing-artifact-id",
                            "section_title": "Unknown section",
                            "topic": "Manifest mapping",
                            "status": "resolved",
                            "owner": "Delivery",
                            "rationale": "Marked complete manually.",
                            "is_unresolved": True,
                            "comments": [],
                            "unresolved_reasons": ["Missing manifest match."],
                        }
                    ]
                }
            )
