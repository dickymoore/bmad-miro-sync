from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.config import load_config
from bmad_miro_sync.host_exports import write_json
from bmad_miro_sync.manifest import SyncManifest, apply_results, load_manifest, save_manifest
from bmad_miro_sync.planner import build_sync_plan


CONFIG_TEXT = """
board_url = "https://miro.com/app/board/uXjVGixS6vQ=/"
source_root = "_bmad-output"
manifest_path = ".bmad-miro-sync/state.json"

[layout]
create_phase_frames = true

[publish]
analysis = true
planning = true
solutioning = true
implementation = true
stories_table = true
"""


class PlannerTests(unittest.TestCase):
    def test_plan_orders_zone_and_workstream_scaffolding_before_leaf_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\nIntro\n\n## Goals\n\nBody\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/architecture.md").write_text(
                "# Architecture\n\nSystem design\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/implementation-artifacts/implementation-readiness.md").write_text(
                "# Readiness Summary\n\nStatus: Blocked\nOwner: Delivery\n\n- Finalize test plan\n- Resolve open UX review\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            self.assertEqual(
                [operation.action for operation in plan.operations[:6]],
                [
                    "ensure_zone",
                    "ensure_zone",
                    "ensure_zone",
                    "ensure_workstream_anchor",
                    "ensure_workstream_anchor",
                    "ensure_workstream_anchor",
                ],
            )
            readiness_operation = next(
                operation
                for operation in plan.operations
                if operation.artifact_id == "_bmad-output/implementation-artifacts/implementation-readiness.md#readiness-summary"
            )
            self.assertEqual(readiness_operation.item_type, "table")
            self.assertEqual(readiness_operation.phase_zone, "implementation_readiness")
            self.assertEqual(readiness_operation.workstream, "delivery")
            self.assertEqual(readiness_operation.container_target_key, "workstream:implementation_readiness:delivery")
            self.assertEqual(readiness_operation.deterministic_order.object_rank, 2)
            prd_sections = [artifact for artifact in plan.artifacts if artifact.source_artifact_id.endswith("prd.md")]
            self.assertEqual(
                [artifact.artifact_id for artifact in prd_sections],
                [
                    "_bmad-output/planning-artifacts/prd.md#prd",
                    "_bmad-output/planning-artifacts/prd.md#prd/goals",
                ],
            )
            self.assertEqual(prd_sections[1].parent_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd")
            self.assertEqual(prd_sections[1].section_path, ("prd", "goals"))
            self.assertEqual(prd_sections[1].lineage_status, "new")
            self.assertEqual(prd_sections[0].phase_zone, "planning")
            self.assertEqual(prd_sections[0].workstream, "product")
            self.assertEqual(prd_sections[0].collaboration_intent, "anchor")

    def test_decision_records_publish_as_delivery_feedback_summary_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/review-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/review-artifacts/decision-records.md").write_text(
                "# Decision Records\n\n"
                "Open topics: 2\n"
                "Blocked topics: 1\n"
                "Deferred topics: 1\n"
                "Accepted topics: 0\n"
                "Resolved topics: 0\n\n"
                "## _bmad-output/planning-artifacts/prd.md\n\n"
                "### PRD / Goals\n\n"
                "#### Acceptance criteria\n\n"
                "Status: Open\n"
                "Owner: Awaiting triage\n"
                "Rationale: Awaiting triage\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            operation = next(
                op for op in plan.operations if op.artifact_id == "_bmad-output/review-artifacts/decision-records.md#decision-records"
            )
            self.assertEqual(operation.item_type, "table")
            self.assertEqual(operation.phase_zone, "delivery_feedback")
            self.assertEqual(operation.workstream, "delivery")
            self.assertEqual(operation.collaboration_intent, "summary")
            self.assertEqual(operation.columns[0]["column_title"], "Field")
            self.assertEqual(operation.rows[0]["cells"][0]["value"], "Open topics")

    def test_implementation_handoff_publishes_as_delivery_readiness_summary_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/implementation-handoff.md").write_text(
                "# Implementation Handoff\n\n"
                "Overall readiness: At Risk\n"
                "Ready for implementation handoff: No\n"
                "Blocking topics requiring action: 1\n"
                "Deferred follow-up items: 0\n"
                "Open questions: 0\n"
                "Missing workstream coverage: None\n\n"
                "## Workstream Handoff\n\n"
                "### UX\n\n"
                "Status: Blocked\n"
                "Action items:\n"
                "- Navigation handoff [Blocked]\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            operation = next(
                op
                for op in plan.operations
                if op.artifact_id == "_bmad-output/implementation-artifacts/implementation-handoff.md#implementation-handoff"
            )
            self.assertEqual(operation.item_type, "table")
            self.assertEqual(operation.phase_zone, "implementation_readiness")
            self.assertEqual(operation.workstream, "delivery")
            self.assertEqual(operation.collaboration_intent, "summary")
            self.assertEqual(operation.container_target_key, "workstream:implementation_readiness:delivery")
            self.assertEqual(operation.columns[0]["column_title"], "Field")
            self.assertEqual(operation.rows[0]["cells"][0]["value"], "Overall readiness")

    def test_plan_preserves_source_section_order_within_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\n## Zebra\n\nFirst\n\n## Alpha\n\nSecond\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            doc_operations = [operation.artifact_id for operation in plan.operations if operation.item_type == "doc"]
            self.assertEqual(
                doc_operations,
                [
                    "_bmad-output/planning-artifacts/prd.md#prd",
                    "_bmad-output/planning-artifacts/prd.md#prd/zebra",
                    "_bmad-output/planning-artifacts/prd.md#prd/alpha",
                ],
            )
            self.assertEqual(
                [
                    operation.deterministic_order.section_rank
                    for operation in plan.operations
                    if operation.item_type == "doc"
                ],
                [0, 1, 2],
            )

    def test_existing_manifest_skips_unchanged_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            artifact = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd"))
            results = {
                "items": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "artifact_sha256": artifact.sha256,
                        "item_type": "doc",
                        "item_id": "123",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=123",
                        "title": artifact.title,
                        "target_key": f"artifact:{artifact.artifact_id}",
                        "source_artifact_id": artifact.source_artifact_id,
                        "phase_zone": artifact.phase_zone,
                        "workstream": artifact.workstream,
                        "collaboration_intent": artifact.collaboration_intent,
                        "container_target_key": f"workstream:{artifact.phase_zone}:{artifact.workstream}",
                        "heading_level": artifact.heading_level,
                        "parent_artifact_id": artifact.parent_artifact_id,
                        "updated_at": "2026-04-14T15:00:00Z",
                    }
                ]
            }
            manifest = apply_results(load_manifest(root, config.manifest_path), results)
            save_manifest(root, config.manifest_path, manifest)

            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            doc_actions = [op.action for op in second_plan.operations if op.item_type == "doc"]
            self.assertEqual(doc_actions, ["skip"])

    def test_changed_content_updates_existing_doc_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            artifact = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd"))
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": artifact.artifact_id,
                            "artifact_sha256": artifact.sha256,
                            "item_type": "doc",
                            "item_id": "doc-123",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            "title": artifact.title,
                            "target_key": f"artifact:{artifact.artifact_id}",
                            "source_artifact_id": artifact.source_artifact_id,
                            "phase_zone": artifact.phase_zone,
                            "workstream": artifact.workstream,
                            "collaboration_intent": artifact.collaboration_intent,
                            "container_target_key": f"workstream:{artifact.phase_zone}:{artifact.workstream}",
                            "heading_level": artifact.heading_level,
                            "parent_artifact_id": artifact.parent_artifact_id,
                            "section_path": list(artifact.section_path),
                            "section_title_path": list(artifact.section_title_path),
                            "section_slug": artifact.section_slug,
                            "section_sibling_index": artifact.section_sibling_index,
                            "lineage_key": artifact.lineage_key,
                            "lineage_status": artifact.lineage_status,
                            "previous_artifact_id": artifact.previous_artifact_id,
                            "previous_parent_artifact_id": artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-18T09:00:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\nUpdated body\n", encoding="utf-8")
            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            operation = next(op for op in second_plan.operations if op.artifact_id == artifact.artifact_id)

            self.assertEqual(operation.action, "update_doc")
            self.assertIsNotNone(operation.existing_item)
            self.assertEqual(operation.existing_item["item_id"], "doc-123")

    def test_legacy_manifest_entries_are_normalized_for_repeat_sync_removals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            legacy_state = {
                "version": 2,
                "items": {
                    "_bmad-output/planning-artifacts/old.md#gone": {
                        "artifact_sha256": "abc",
                        "item_type": "doc",
                        "item_id": "doc-legacy",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-legacy",
                        "title": "Old",
                        "target_key": "artifact:_bmad-output/planning-artifacts/old.md#gone",
                        "source_artifact_id": "_bmad-output/planning-artifacts/old.md",
                        "heading_level": 0,
                        "parent_artifact_id": None,
                        "updated_at": "2026-04-14T15:00:00Z",
                    }
                },
            }
            state_path = root / ".bmad-miro-sync/state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(legacy_state, indent=2) + "\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            removal_operation = next(
                operation for operation in plan.operations if operation.action == "archive_doc" and "old.md#gone" in operation.artifact_id
            )
            self.assertEqual(removal_operation.existing_item["artifact_id"], "_bmad-output/planning-artifacts/old.md#gone")
            self.assertEqual(removal_operation.existing_item["content_fingerprint"], "abc")

    def test_item_type_replacement_creates_new_content_and_retires_stale_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            story_path = root / "_bmad-output/implementation-artifacts/1-3-sample-story.md"
            story_path.write_text(
                "# Story 1.3: Sample\n\nStatus: review\n\n- [x] Task one\n- [ ] Task two\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            root_table_operation = next(operation for operation in first_plan.operations if operation.item_type == "table")
            root_artifact = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id == root_table_operation.artifact_id)
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": root_table_operation.artifact_id,
                            "artifact_sha256": root_artifact.sha256,
                            "item_type": root_table_operation.item_type,
                            "item_id": "table-1",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=table-1",
                            "title": root_table_operation.title,
                            "target_key": root_table_operation.target_key,
                            "source_artifact_id": root_table_operation.source_artifact_id,
                            "phase_zone": root_table_operation.phase_zone,
                            "workstream": root_table_operation.workstream,
                            "collaboration_intent": root_table_operation.collaboration_intent,
                            "container_target_key": root_table_operation.container_target_key,
                            "heading_level": root_table_operation.heading_level,
                            "parent_artifact_id": root_table_operation.parent_artifact_id,
                            "section_path": list(root_artifact.section_path),
                            "section_title_path": list(root_artifact.section_title_path),
                            "section_slug": root_artifact.section_slug,
                            "section_sibling_index": root_artifact.section_sibling_index,
                            "lineage_key": root_artifact.lineage_key,
                            "lineage_status": root_artifact.lineage_status,
                            "previous_artifact_id": root_artifact.previous_artifact_id,
                            "previous_parent_artifact_id": root_artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-18T09:30:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            story_path.write_text(
                "# Story 1.3: Sample\n\nStatus: review\n\n## Story\n\nBody\n",
                encoding="utf-8",
            )
            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            create_operation = next(
                operation
                for operation in second_plan.operations
                if operation.artifact_id == root_artifact.artifact_id and operation.item_type == "doc"
            )
            retire_operation = next(
                operation
                for operation in second_plan.operations
                if operation.action == "archive_table" and operation.existing_item and operation.existing_item["artifact_id"] == root_artifact.artifact_id
            )

            self.assertEqual(create_operation.action, "create_doc")
            self.assertIsNone(create_operation.existing_item)
            self.assertTrue(retire_operation.artifact_id.endswith("::retired::table"))
            self.assertEqual(retire_operation.existing_item["item_id"], "table-1")

    def test_missing_manifest_item_plans_archive_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            section = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd/goals"))
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": artifact.artifact_id,
                            "artifact_sha256": artifact.sha256,
                            "item_type": "doc",
                            "item_id": f"doc-{index}",
                            "miro_url": f"https://miro.com/app/board/x/?moveToWidget=doc-{index}",
                            "title": artifact.title,
                            "target_key": f"artifact:{artifact.artifact_id}",
                            "source_artifact_id": artifact.source_artifact_id,
                            "phase_zone": artifact.phase_zone,
                            "workstream": artifact.workstream,
                            "collaboration_intent": artifact.collaboration_intent,
                            "container_target_key": f"workstream:{artifact.phase_zone}:{artifact.workstream}",
                            "heading_level": artifact.heading_level,
                            "parent_artifact_id": artifact.parent_artifact_id,
                            "section_path": list(artifact.section_path),
                            "section_title_path": list(artifact.section_title_path),
                            "section_slug": artifact.section_slug,
                            "section_sibling_index": artifact.section_sibling_index,
                            "lineage_key": artifact.lineage_key,
                            "lineage_status": artifact.lineage_status,
                            "previous_artifact_id": artifact.previous_artifact_id,
                            "previous_parent_artifact_id": artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-18T09:15:00Z",
                        }
                        for index, artifact in enumerate(first_plan.artifacts, start=1)
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")
            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            operation = next(op for op in second_plan.operations if op.artifact_id == section.artifact_id)

            self.assertEqual(operation.action, "archive_doc")
            self.assertEqual(operation.lifecycle_state, "archived")
            self.assertIsNotNone(operation.existing_item)
            self.assertEqual(operation.existing_item["item_id"], "doc-2")

    def test_missing_manifest_item_respects_remove_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                CONFIG_TEXT
                + """
[sync]
removed_item_policy = "remove"
""",
                encoding="utf-8",
            )
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            section = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd/goals"))
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": artifact.artifact_id,
                            "artifact_sha256": artifact.sha256,
                            "item_type": "doc",
                            "item_id": f"doc-{index}",
                            "miro_url": f"https://miro.com/app/board/x/?moveToWidget=doc-{index}",
                            "title": artifact.title,
                            "target_key": f"artifact:{artifact.artifact_id}",
                            "source_artifact_id": artifact.source_artifact_id,
                            "phase_zone": artifact.phase_zone,
                            "workstream": artifact.workstream,
                            "collaboration_intent": artifact.collaboration_intent,
                            "container_target_key": f"workstream:{artifact.phase_zone}:{artifact.workstream}",
                            "heading_level": artifact.heading_level,
                            "parent_artifact_id": artifact.parent_artifact_id,
                            "section_path": list(artifact.section_path),
                            "section_title_path": list(artifact.section_title_path),
                            "section_slug": artifact.section_slug,
                            "section_sibling_index": artifact.section_sibling_index,
                            "lineage_key": artifact.lineage_key,
                            "lineage_status": artifact.lineage_status,
                            "previous_artifact_id": artifact.previous_artifact_id,
                            "previous_parent_artifact_id": artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-18T09:30:00Z",
                        }
                        for index, artifact in enumerate(first_plan.artifacts, start=1)
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")
            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            operation = next(op for op in second_plan.operations if op.artifact_id == section.artifact_id)

            self.assertEqual(operation.action, "remove_doc")
            self.assertEqual(operation.lifecycle_state, "removed")

    def test_plan_serializes_structured_discovery_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts/prd").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                CONFIG_TEXT
                + """
[discovery]
source_paths = ["_bmad-output/planning-artifacts"]
required_artifact_classes = ["prd", "ux_design"]
""",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd/index.md").write_text("# PRD Index\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            payload = plan.to_dict()

            self.assertEqual(payload["discovery"]["selected"][0]["relative_path"], "_bmad-output/planning-artifacts/prd.md")
            self.assertEqual(payload["discovery"]["skipped"][0]["relative_path"], "_bmad-output/planning-artifacts/prd/index.md")
            self.assertEqual(payload["discovery"]["missing_required"][0]["artifact_class"], "ux_design")
            self.assertTrue(any("ux_design" in warning for warning in payload["warnings"]))
            self.assertEqual(payload["artifacts"][0]["section_path"], ["prd"])
            self.assertEqual(payload["artifacts"][0]["phase_zone"], "planning")
            self.assertEqual(payload["artifacts"][0]["workstream"], "product")
            self.assertEqual(payload["artifacts"][0]["collaboration_intent"], "anchor")
            self.assertEqual(payload["artifacts"][0]["lineage_status"], "new")
            self.assertIsNone(payload["artifacts"][0]["previous_artifact_id"])
            self.assertEqual(payload["discovery"]["selected"][0]["phase_zone"], "planning")
            self.assertEqual(payload["operations"][0]["item_type"], "zone")
            self.assertEqual(payload["operations"][0]["deterministic_order"]["object_rank"], 0)

    def test_renamed_section_reuses_manifest_item_via_previous_artifact_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            original_section = next(
                artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd/goals")
            )
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": original_section.artifact_id,
                            "artifact_sha256": original_section.sha256,
                            "item_type": "doc",
                        "item_id": "123",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=123",
                        "title": original_section.title,
                        "target_key": f"artifact:{original_section.artifact_id}",
                        "source_artifact_id": original_section.source_artifact_id,
                        "phase_zone": original_section.phase_zone,
                        "workstream": original_section.workstream,
                        "collaboration_intent": original_section.collaboration_intent,
                        "container_target_key": f"workstream:{original_section.phase_zone}:{original_section.workstream}",
                        "heading_level": original_section.heading_level,
                        "parent_artifact_id": original_section.parent_artifact_id,
                        "updated_at": "2026-04-14T15:00:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n", encoding="utf-8")

            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            renamed_operation = next(
                operation for operation in second_plan.operations if operation.artifact_id.endswith("#prd/objectives")
            )

            self.assertEqual(renamed_operation.action, "update_doc")
            self.assertIsNotNone(renamed_operation.existing_item)
            self.assertEqual(
                renamed_operation.existing_item["target_key"],
                "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
            )

    def test_apply_results_replaces_stale_previous_artifact_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            original_section = next(
                artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd/goals")
            )
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": original_section.artifact_id,
                            "artifact_sha256": original_section.sha256,
                            "item_type": "doc",
                            "item_id": "123",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=123",
                            "title": original_section.title,
                            "target_key": f"artifact:{original_section.artifact_id}",
                            "source_artifact_id": original_section.source_artifact_id,
                            "phase_zone": original_section.phase_zone,
                            "workstream": original_section.workstream,
                            "collaboration_intent": original_section.collaboration_intent,
                            "container_target_key": f"workstream:{original_section.phase_zone}:{original_section.workstream}",
                            "heading_level": original_section.heading_level,
                            "parent_artifact_id": original_section.parent_artifact_id,
                            "section_path": list(original_section.section_path),
                            "section_title_path": list(original_section.section_title_path),
                            "section_slug": original_section.section_slug,
                            "section_sibling_index": original_section.section_sibling_index,
                            "lineage_key": original_section.lineage_key,
                            "lineage_status": original_section.lineage_status,
                            "previous_artifact_id": original_section.previous_artifact_id,
                            "previous_parent_artifact_id": original_section.previous_parent_artifact_id,
                            "updated_at": "2026-04-14T15:00:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n", encoding="utf-8")
            renamed_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            renamed_operation = next(
                operation for operation in renamed_plan.operations if operation.artifact_id.endswith("#prd/objectives")
            )
            renamed_artifact = next(
                artifact for artifact in renamed_plan.artifacts if artifact.artifact_id == renamed_operation.artifact_id
            )
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": renamed_operation.artifact_id,
                            "artifact_sha256": renamed_artifact.sha256,
                            "item_type": renamed_operation.item_type,
                            "item_id": "123",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=123",
                            "title": renamed_operation.title,
                            "target_key": renamed_operation.target_key,
                            "source_artifact_id": renamed_operation.source_artifact_id,
                            "phase_zone": renamed_operation.phase_zone,
                            "workstream": renamed_operation.workstream,
                            "collaboration_intent": renamed_operation.collaboration_intent,
                            "container_target_key": renamed_operation.container_target_key,
                            "heading_level": renamed_operation.heading_level,
                            "parent_artifact_id": renamed_operation.parent_artifact_id,
                            "section_path": list(renamed_artifact.section_path),
                            "section_title_path": list(renamed_artifact.section_title_path),
                            "section_slug": renamed_artifact.section_slug,
                            "section_sibling_index": renamed_artifact.section_sibling_index,
                            "lineage_key": renamed_artifact.lineage_key,
                            "lineage_status": renamed_artifact.lineage_status,
                            "previous_artifact_id": renamed_artifact.previous_artifact_id,
                            "previous_parent_artifact_id": renamed_artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-14T15:00:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            reloaded_manifest = load_manifest(root, config.manifest_path)
            self.assertNotIn(original_section.artifact_id, reloaded_manifest.items)
            self.assertIn(renamed_operation.artifact_id, reloaded_manifest.items)

            doc_path.write_text("# PRD\n\n## Goals\n\nNew body\n\n## Objectives\n\nBody\n", encoding="utf-8")
            final_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            recreated_goals = next(
                operation for operation in final_plan.operations if operation.artifact_id.endswith("#prd/goals")
            )

            self.assertEqual(recreated_goals.action, "create_doc")
            self.assertIsNone(recreated_goals.existing_item)

    def test_apply_results_accepts_orientation_items_without_artifact_sha256(self) -> None:
        manifest = apply_results(
            SyncManifest(version=3, items={}),
            {
                "items": [
                    {
                        "artifact_id": "zone:planning",
                        "item_type": "zone",
                        "item_id": "zone-1",
                        "target_key": "zone:planning",
                        "source_artifact_id": "zone:planning",
                        "phase_zone": "planning",
                        "workstream": "general",
                        "collaboration_intent": "orientation",
                        "updated_at": "2026-04-17T22:07:45+01:00",
                    },
                    {
                        "artifact_id": "workstream:planning:product",
                        "item_type": "workstream_anchor",
                        "item_id": "anchor-1",
                        "target_key": "workstream:planning:product",
                        "source_artifact_id": "workstream:planning:product",
                        "phase_zone": "planning",
                        "workstream": "product",
                        "collaboration_intent": "orientation",
                        "container_target_key": "zone:planning",
                        "updated_at": "2026-04-17T22:07:45+01:00",
                    },
                ]
            },
        )

        self.assertIn("zone:planning", manifest.items)
        self.assertIsNone(manifest.items["zone:planning"]["artifact_sha256"])
        self.assertEqual(manifest.items["workstream:planning:product"]["item_type"], "workstream_anchor")
        self.assertEqual(manifest.items["workstream:planning:product"]["container_target_key"], "zone:planning")

    def test_apply_results_persists_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            config = load_config(root / ".bmad-miro.toml")
            manifest = load_manifest(root, config.manifest_path)
            updated = apply_results(
                manifest,
                {
                    "items": [
                        {
                            "artifact_id": "doc:test#overview",
                            "artifact_sha256": "abc",
                            "item_type": "doc",
                            "item_id": "123",
                            "miro_url": "https://miro.com/x",
                            "title": "Test",
                            "target_key": "artifact:doc:test#overview",
                            "source_artifact_id": "doc:test",
                            "phase_zone": "planning",
                            "workstream": "general",
                            "collaboration_intent": "anchor",
                            "container_target_key": "workstream:planning:general",
                            "heading_level": 0,
                            "parent_artifact_id": None,
                            "section_path": ["overview"],
                            "section_title_path": ["Overview"],
                            "section_slug": "overview",
                            "section_sibling_index": 1,
                            "lineage_key": "lineage-123",
                            "lineage_status": "new",
                            "previous_artifact_id": None,
                            "previous_parent_artifact_id": None,
                            "updated_at": "2026-04-14T15:00:00Z",
                        }
                    ]
                },
            )
            path = save_manifest(root, config.manifest_path, updated)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 3)
            self.assertIn("doc:test#overview", payload["items"])
            self.assertEqual(payload["items"]["doc:test#overview"]["phase_zone"], "planning")
            self.assertEqual(payload["items"]["doc:test#overview"]["section_path"], ["overview"])
            self.assertEqual(payload["items"]["doc:test#overview"]["lineage_status"], "new")

    def test_story_root_html_comment_does_not_force_summary_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/1-3-sample-story.md").write_text(
                "# Story 1.3: Sample\n\nStatus: review\n\n<!-- Note: Hidden implementation detail. -->\n\n## Story\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            root_operation = next(
                operation
                for operation in plan.operations
                if operation.artifact_id == "_bmad-output/implementation-artifacts/1-3-sample-story.md#story-1-3-sample"
            )

            self.assertEqual(root_operation.item_type, "doc")
            self.assertEqual(root_operation.action, "create_doc")

    def test_repeated_runs_keep_identical_operation_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/implementation-readiness.md").write_text(
                "# Readiness Summary\n\nStatus: Ready\nOwner: Delivery\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first = build_sync_plan(root, root / ".bmad-miro.toml", config)
            second = build_sync_plan(root, root / ".bmad-miro.toml", config)

            self.assertEqual(
                [operation.op_id for operation in first.operations],
                [operation.op_id for operation in second.operations],
            )
            self.assertEqual(
                [operation.deterministic_order for operation in first.operations],
                [operation.deterministic_order for operation in second.operations],
            )

    def test_repeat_sync_updates_preserve_existing_layout_while_new_siblings_auto_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            config_path.write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path.write_text("# PRD\n\n## Goals\n\nInitial body\n", encoding="utf-8")

            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            initial_results = {
                "items": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "artifact_sha256": artifact.sha256,
                        "item_type": "doc",
                        "item_id": f"doc-{index}",
                        "miro_url": f"https://miro.com/app/board/x/?moveToWidget=doc-{index}",
                        "title": artifact.title,
                        "target_key": f"artifact:{artifact.artifact_id}",
                        "source_artifact_id": artifact.source_artifact_id,
                        "phase_zone": artifact.phase_zone,
                        "workstream": artifact.workstream,
                        "collaboration_intent": artifact.collaboration_intent,
                        "container_target_key": "frame:curated-lane",
                        "heading_level": artifact.heading_level,
                        "parent_artifact_id": artifact.parent_artifact_id,
                        "section_path": list(artifact.section_path),
                        "section_title_path": list(artifact.section_title_path),
                        "section_slug": artifact.section_slug,
                        "section_sibling_index": artifact.section_sibling_index,
                        "lineage_key": artifact.lineage_key,
                        "lineage_status": artifact.lineage_status,
                        "previous_artifact_id": artifact.previous_artifact_id,
                        "previous_parent_artifact_id": artifact.previous_parent_artifact_id,
                        "layout_snapshot": {
                            "x": 100 + index,
                            "y": 200 + index,
                            "width": 320,
                            "height": 180,
                            "parent_item_id": "frame-1",
                            "group_id": "group-1",
                        },
                        "updated_at": "2026-04-18T10:35:00Z",
                    }
                    for index, artifact in enumerate(initial_plan.artifacts, start=1)
                ]
            }
            manifest = apply_results(load_manifest(root, config.manifest_path), initial_results)
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\n## Goals\n\nUpdated body\n\n## Risks\n\nNew section\n", encoding="utf-8")
            repeat_plan = build_sync_plan(root, config_path, config)

            goals_operation = next(
                operation for operation in repeat_plan.operations if operation.artifact_id.endswith("#prd/goals")
            )
            risks_operation = next(
                operation for operation in repeat_plan.operations if operation.artifact_id.endswith("#prd/risks")
            )

            self.assertEqual(goals_operation.action, "update_doc")
            self.assertEqual(goals_operation.existing_item["item_id"], "doc-2")
            self.assertEqual(goals_operation.layout_policy, "preserve")
            self.assertEqual(
                goals_operation.layout_snapshot,
                {
                    "x": 102,
                    "y": 202,
                    "width": 320,
                    "height": 180,
                    "parent_item_id": "frame-1",
                    "group_id": "group-1",
                },
            )
            self.assertEqual(goals_operation.container_target_key, "frame:curated-lane")
            self.assertEqual(risks_operation.action, "create_doc")
            self.assertEqual(risks_operation.layout_policy, "auto")
            self.assertIsNone(risks_operation.layout_snapshot)
            self.assertEqual(risks_operation.container_target_key, "workstream:planning:product")

    def test_removal_operations_are_planned_when_last_source_artifact_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            config_path.write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            first_plan = build_sync_plan(root, config_path, config)
            root_artifact = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#prd"))

            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": root_artifact.artifact_id,
                            "artifact_sha256": root_artifact.sha256,
                            "item_type": "doc",
                            "item_id": "doc-123",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            "title": root_artifact.title,
                            "target_key": f"artifact:{root_artifact.artifact_id}",
                            "source_artifact_id": root_artifact.source_artifact_id,
                            "phase_zone": root_artifact.phase_zone,
                            "workstream": root_artifact.workstream,
                            "collaboration_intent": root_artifact.collaboration_intent,
                            "container_target_key": f"workstream:{root_artifact.phase_zone}:{root_artifact.workstream}",
                            "heading_level": root_artifact.heading_level,
                            "parent_artifact_id": root_artifact.parent_artifact_id,
                            "section_path": list(root_artifact.section_path),
                            "section_title_path": list(root_artifact.section_title_path),
                            "section_slug": root_artifact.section_slug,
                            "section_sibling_index": root_artifact.section_sibling_index,
                            "lineage_key": root_artifact.lineage_key,
                            "lineage_status": root_artifact.lineage_status,
                            "previous_artifact_id": root_artifact.previous_artifact_id,
                            "previous_parent_artifact_id": root_artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-18T10:00:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)
            doc_path.unlink()

            plan = build_sync_plan(root, config_path, config)
            removal_operation = next(
                operation for operation in plan.operations if operation.artifact_id == root_artifact.artifact_id
            )

            self.assertEqual(removal_operation.action, "archive_doc")
            self.assertEqual(removal_operation.lifecycle_state, "archived")
            self.assertIn(
                "No markdown artifacts were discovered, so the plan only contains retirements for previously synced content.",
                plan.warnings,
            )

    def test_story_summary_strategy_degrades_table_to_doc_and_reuses_replacement_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            story_path = root / "_bmad-output/implementation-artifacts/1-3-sample-story.md"
            config_path.write_text(
                CONFIG_TEXT
                + """
[object_strategies]
story_summary = "doc"
""",
                encoding="utf-8",
            )
            story_path.write_text(
                "# Story 1.3: Sample\n\nStatus: review\n\n- [x] Task one\n- [ ] Task two\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            first_plan = build_sync_plan(root, config_path, config)
            summary_artifact = next(artifact for artifact in first_plan.artifacts if artifact.artifact_id.endswith("#story-1-3-sample"))
            summary_operation = next(operation for operation in first_plan.operations if operation.artifact_id == summary_artifact.artifact_id)

            self.assertEqual(summary_operation.item_type, "doc")
            self.assertEqual(summary_operation.action, "create_doc")
            self.assertEqual(summary_operation.object_family, "story_summary")
            self.assertEqual(summary_operation.preferred_item_type, "table")
            self.assertEqual(summary_operation.resolved_item_type, "doc")
            self.assertTrue(summary_operation.degraded)
            self.assertIn("story summary tables", summary_operation.degraded_warning or "")
            self.assertIn(
                "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                first_plan.warnings,
            )
            self.assertEqual(
                next(strategy for strategy in first_plan.object_strategies if strategy.object_family == "story_summary").resolved_item_type,
                "doc",
            )

            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": summary_artifact.artifact_id,
                            "artifact_sha256": summary_artifact.sha256,
                            "item_type": "table",
                            "item_id": "table-1",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=table-1",
                            "title": summary_operation.title,
                            "target_key": summary_operation.target_key,
                            "source_artifact_id": summary_operation.source_artifact_id,
                            "phase_zone": summary_operation.phase_zone,
                            "workstream": summary_operation.workstream,
                            "collaboration_intent": summary_operation.collaboration_intent,
                            "container_target_key": summary_operation.container_target_key,
                            "object_family": "story_summary",
                            "preferred_item_type": "table",
                            "resolved_item_type": "table",
                            "degraded": False,
                            "heading_level": summary_operation.heading_level,
                            "parent_artifact_id": summary_operation.parent_artifact_id,
                            "section_path": list(summary_artifact.section_path),
                            "section_title_path": list(summary_artifact.section_title_path),
                            "section_slug": summary_artifact.section_slug,
                            "section_sibling_index": summary_artifact.section_sibling_index,
                            "lineage_key": summary_artifact.lineage_key,
                            "lineage_status": summary_artifact.lineage_status,
                            "previous_artifact_id": summary_artifact.previous_artifact_id,
                            "previous_parent_artifact_id": summary_artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-18T11:10:00Z",
                        }
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            replacement_plan = build_sync_plan(root, config_path, config)
            replacement_create = next(
                operation
                for operation in replacement_plan.operations
                if operation.artifact_id == summary_artifact.artifact_id and operation.item_type == "doc"
            )
            replacement_retire = next(
                operation
                for operation in replacement_plan.operations
                if operation.action == "archive_table" and operation.existing_item and operation.existing_item["artifact_id"] == summary_artifact.artifact_id
            )

            self.assertEqual(replacement_create.action, "create_doc")
            self.assertIsNone(replacement_create.existing_item)
            self.assertEqual(replacement_create.layout_policy, "auto")
            self.assertEqual(replacement_retire.preferred_item_type, "table")
            self.assertEqual(replacement_retire.resolved_item_type, "doc")
            self.assertTrue(replacement_retire.degraded)
            self.assertTrue(replacement_retire.artifact_id.endswith("::retired::table"))

    def test_unused_story_summary_fallback_does_not_emit_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(
                CONFIG_TEXT
                + """
[object_strategies]
story_summary = "doc"
""",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            plan = build_sync_plan(root, config_path, config)

            self.assertNotIn(
                "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                plan.warnings,
            )
            self.assertFalse(any(operation.object_family == "story_summary" for operation in plan.operations))

    def test_phase_zone_fallback_warning_is_emitted_when_zone_scaffolding_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(
                CONFIG_TEXT
                + """
[object_strategies]
phase_zone = "workstream_anchor"
""",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            plan = build_sync_plan(root, config_path, config)

            self.assertIn(
                "Preferred phase-zone containers are unavailable; workstream anchors will carry orientation without separate zone objects.",
                plan.warnings,
            )
            self.assertFalse(any(operation.action == "ensure_zone" for operation in plan.operations))


if __name__ == "__main__":
    unittest.main()
