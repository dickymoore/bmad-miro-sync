from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


class ManifestStateTests(unittest.TestCase):
    def test_apply_results_reconciles_plan_into_created_and_pending_operation_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\n## Goals\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            plan_payload = plan.to_dict()
            write_json(runtime_dir / "plan.json", plan_payload)

            artifact = next(artifact for artifact in plan.artifacts if artifact.artifact_id.endswith("#prd"))
            results = {
                "run_status": "partial",
                "executed_at": "2026-04-17T22:40:00Z",
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
                        "execution_status": "created",
                        "updated_at": "2026-04-17T22:40:00Z",
                    }
                ],
            }

            manifest = apply_results(
                SyncManifest(version=2, items={}),
                results,
                plan=plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertEqual(manifest.version, 3)
            self.assertIn(artifact.artifact_id, manifest.items)
            created_item = manifest.items[artifact.artifact_id]
            self.assertEqual(created_item["execution_status"], "created")
            self.assertEqual(created_item["content_fingerprint"], artifact.sha256)
            self.assertEqual(created_item["sync_timestamp"], "2026-04-17T22:40:00Z")
            self.assertEqual(created_item["section_path"], ["prd"])

            self.assertIn(f"doc:{artifact.artifact_id}", manifest.operations)
            created_operation = manifest.operations[f"doc:{artifact.artifact_id}"]
            self.assertEqual(created_operation["execution_status"], "created")
            self.assertEqual(created_operation["content_fingerprint"], artifact.sha256)
            self.assertEqual(created_operation["target_key"], f"artifact:{artifact.artifact_id}")

            pending_zone = manifest.operations["zone:planning"]
            self.assertEqual(pending_zone["execution_status"], "pending")
            self.assertIsNone(pending_zone["content_fingerprint"])
            self.assertIsNone(pending_zone["last_attempted_at"])

            pending_anchor = manifest.operations["workstream:planning:product"]
            self.assertEqual(pending_anchor["execution_status"], "pending")
            self.assertEqual(pending_anchor["container_target_key"], "zone:planning")
            self.assertIsNone(pending_anchor["last_attempted_at"])

            self.assertEqual(manifest.last_run["run_status"], "partial")
            self.assertEqual(manifest.last_run["executed_operation_count"], 1)
            self.assertGreater(manifest.last_run["pending_operation_count"], 0)
            self.assertEqual(manifest.last_run["plan_path"], ".bmad-miro-sync/run/plan.json")
            self.assertEqual(manifest.last_run["results_path"], ".bmad-miro-sync/run/results.json")

    def test_apply_results_failed_create_keeps_operation_failed_without_item_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            plan_payload = plan.to_dict()
            write_json(runtime_dir / "plan.json", plan_payload)

            artifact = next(artifact for artifact in plan.artifacts if artifact.artifact_id.endswith("#prd"))
            results = {
                "run_status": "failed",
                "executed_at": "2026-04-17T23:10:00Z",
                "items": [
                    {
                        "op_id": f"doc:{artifact.artifact_id}",
                        "artifact_id": artifact.artifact_id,
                        "item_type": "doc",
                        "execution_status": "failed",
                        "error": "create_doc failed",
                    }
                ],
            }

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                results,
                plan=plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertNotIn(artifact.artifact_id, manifest.items)
            failed_operation = manifest.operations[f"doc:{artifact.artifact_id}"]
            self.assertEqual(failed_operation["execution_status"], "failed")
            self.assertEqual(failed_operation["error"], "create_doc failed")
            self.assertIsNone(failed_operation["item_id"])
            self.assertIsNone(failed_operation["sync_timestamp"])
            self.assertEqual(failed_operation["last_attempted_at"], "2026-04-17T23:10:00Z")
            self.assertEqual(manifest.last_run["run_status"], "failed")

    def test_apply_results_preserves_pending_retired_mapping_during_item_type_replacement(self) -> None:
        existing_item = {
            "artifact_id": "_bmad-output/implementation-artifacts/story.md#summary",
            "artifact_sha256": "old-sha",
            "content_fingerprint": "old-sha",
            "item_type": "doc",
            "item_id": "doc-123",
            "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
            "title": "Story / Summary",
            "updated_at": "2026-04-17T22:00:00Z",
            "sync_timestamp": "2026-04-17T22:00:00Z",
            "execution_status": "updated",
            "lifecycle_state": "active",
            "target_key": "artifact:_bmad-output/implementation-artifacts/story.md#summary",
            "source_artifact_id": "_bmad-output/implementation-artifacts/story.md",
            "phase": "implementation",
            "phase_zone": "implementation_readiness",
            "workstream": "delivery",
            "collaboration_intent": "summary",
            "container_target_key": "workstream:implementation_readiness:delivery",
            "heading_level": 1,
            "parent_artifact_id": None,
            "section_path": ["summary"],
            "section_title_path": ["Summary"],
            "section_slug": "summary",
            "section_sibling_index": 1,
            "lineage_key": "story::summary",
            "lineage_status": "new",
            "previous_artifact_id": None,
            "previous_parent_artifact_id": None,
        }
        retired_artifact_id = f"{existing_item['artifact_id']}::retired::doc"
        plan = {
            "artifacts": [
                {
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "relative_path": "story.md",
                    "content": "- [ ] Item one\n- [x] Item two\n",
                    "sha256": "new-sha",
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "section_path": existing_item["section_path"],
                    "section_title_path": existing_item["section_title_path"],
                    "section_slug": existing_item["section_slug"],
                    "section_sibling_index": existing_item["section_sibling_index"],
                    "lineage_key": existing_item["lineage_key"],
                    "lineage_status": existing_item["lineage_status"],
                    "previous_artifact_id": existing_item["previous_artifact_id"],
                    "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                }
            ],
            "operations": [
                {
                    "op_id": f"table:{existing_item['artifact_id']}",
                    "action": "create_table",
                    "item_type": "table",
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "target_key": existing_item["target_key"],
                    "container_target_key": existing_item["container_target_key"],
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                },
                {
                    "op_id": f"doc:{retired_artifact_id}",
                    "action": "archive_doc",
                    "item_type": "doc",
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "artifact_id": retired_artifact_id,
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "target_key": f"retired:{existing_item['target_key']}",
                    "container_target_key": existing_item["container_target_key"],
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "lifecycle_state": "archived",
                    "removal_policy": "archive",
                    "existing_item": existing_item,
                },
            ],
        }
        results = {
            "run_status": "partial",
            "executed_at": "2026-04-17T23:55:00Z",
            "items": [
                {
                    "op_id": f"table:{existing_item['artifact_id']}",
                    "artifact_id": existing_item["artifact_id"],
                    "artifact_sha256": "new-sha",
                    "item_type": "table",
                    "item_id": "table-123",
                    "miro_url": "https://miro.com/app/board/x/?moveToWidget=table-123",
                    "title": existing_item["title"],
                    "target_key": existing_item["target_key"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "container_target_key": existing_item["container_target_key"],
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "section_path": existing_item["section_path"],
                    "section_title_path": existing_item["section_title_path"],
                    "section_slug": existing_item["section_slug"],
                    "section_sibling_index": existing_item["section_sibling_index"],
                    "lineage_key": existing_item["lineage_key"],
                    "lineage_status": existing_item["lineage_status"],
                    "previous_artifact_id": existing_item["previous_artifact_id"],
                    "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                    "execution_status": "created",
                    "updated_at": "2026-04-17T23:55:00Z",
                }
            ],
        }

        manifest = apply_results(
            SyncManifest(version=3, items={existing_item["artifact_id"]: existing_item}),
            results,
            plan=plan,
            plan_path=".bmad-miro-sync/run/plan.json",
            results_path=".bmad-miro-sync/run/results.json",
        )

        self.assertEqual(manifest.items[existing_item["artifact_id"]]["item_type"], "table")
        self.assertEqual(manifest.items[existing_item["artifact_id"]]["item_id"], "table-123")
        self.assertIn(retired_artifact_id, manifest.items)
        retired_item = manifest.items[retired_artifact_id]
        self.assertEqual(retired_item["item_type"], "doc")
        self.assertEqual(retired_item["item_id"], "doc-123")
        self.assertEqual(retired_item["execution_status"], "pending")
        self.assertEqual(retired_item["lifecycle_state"], "active")
        self.assertEqual(retired_item["target_key"], f"retired:{existing_item['target_key']}")
        self.assertEqual(manifest.operations[f"doc:{retired_artifact_id}"]["execution_status"], "pending")

    def test_apply_results_normalizes_complete_run_status_when_plan_entries_remain_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\n## Goals\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            plan_payload = plan.to_dict()
            write_json(runtime_dir / "plan.json", plan_payload)

            artifact = next(artifact for artifact in plan.artifacts if artifact.artifact_id.endswith("#prd"))
            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-17T23:40:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{artifact.artifact_id}",
                            "artifact_id": artifact.artifact_id,
                            "artifact_sha256": artifact.sha256,
                            "item_type": "doc",
                            "item_id": "doc-123",
                            "target_key": f"artifact:{artifact.artifact_id}",
                            "source_artifact_id": artifact.source_artifact_id,
                            "execution_status": "created",
                        }
                    ],
                },
                plan=plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertEqual(manifest.last_run["run_status"], "partial")
            self.assertGreater(manifest.last_run["pending_operation_count"], 0)

    def test_apply_results_normalizes_partial_run_status_when_every_plan_operation_is_accounted_for(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            plan_payload = plan.to_dict()
            write_json(runtime_dir / "plan.json", plan_payload)
            artifact_index = {artifact["artifact_id"]: artifact for artifact in plan_payload["artifacts"]}

            results_items = []
            for operation in plan_payload["operations"]:
                result_entry = {
                    "op_id": operation["op_id"],
                    "artifact_id": operation["artifact_id"],
                    "item_type": operation["item_type"],
                    "item_id": operation["op_id"].replace(":", "-"),
                    "target_key": operation["target_key"],
                    "source_artifact_id": operation["source_artifact_id"],
                    "phase_zone": operation["phase_zone"],
                    "workstream": operation["workstream"],
                    "collaboration_intent": operation["collaboration_intent"],
                    "container_target_key": operation["container_target_key"],
                    "heading_level": operation["heading_level"],
                    "parent_artifact_id": operation["parent_artifact_id"],
                    "execution_status": "created",
                    "updated_at": "2026-04-17T23:45:00Z",
                }
                artifact = artifact_index.get(operation["artifact_id"])
                if artifact is not None:
                    result_entry["artifact_sha256"] = artifact["sha256"]
                    result_entry["section_path"] = artifact["section_path"]
                    result_entry["section_title_path"] = artifact["section_title_path"]
                    result_entry["section_slug"] = artifact["section_slug"]
                    result_entry["section_sibling_index"] = artifact["section_sibling_index"]
                    result_entry["lineage_key"] = artifact["lineage_key"]
                    result_entry["lineage_status"] = artifact["lineage_status"]
                    result_entry["previous_artifact_id"] = artifact["previous_artifact_id"]
                    result_entry["previous_parent_artifact_id"] = artifact["previous_parent_artifact_id"]
                results_items.append(result_entry)

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "partial",
                    "executed_at": "2026-04-17T23:45:00Z",
                    "items": results_items,
                },
                plan=plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertEqual(manifest.last_run["run_status"], "complete")
            self.assertEqual(manifest.last_run["pending_operation_count"], 0)

    def test_apply_results_counts_unchanged_skip_operations_as_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            initial_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            initial_plan_payload = initial_plan.to_dict()
            write_json(runtime_dir / "plan.json", initial_plan_payload)
            initial_artifact_index = {artifact["artifact_id"]: artifact for artifact in initial_plan_payload["artifacts"]}

            initial_results = []
            for operation in initial_plan_payload["operations"]:
                result_entry = {
                    "op_id": operation["op_id"],
                    "artifact_id": operation["artifact_id"],
                    "item_type": operation["item_type"],
                    "item_id": operation["op_id"].replace(":", "-"),
                    "target_key": operation["target_key"],
                    "source_artifact_id": operation["source_artifact_id"],
                    "phase_zone": operation["phase_zone"],
                    "workstream": operation["workstream"],
                    "collaboration_intent": operation["collaboration_intent"],
                    "container_target_key": operation["container_target_key"],
                    "heading_level": operation["heading_level"],
                    "parent_artifact_id": operation["parent_artifact_id"],
                    "execution_status": "created",
                    "updated_at": "2026-04-18T12:00:00Z",
                }
                artifact = initial_artifact_index.get(operation["artifact_id"])
                if artifact is not None:
                    result_entry["artifact_sha256"] = artifact["sha256"]
                    result_entry["section_path"] = artifact["section_path"]
                    result_entry["section_title_path"] = artifact["section_title_path"]
                    result_entry["section_slug"] = artifact["section_slug"]
                    result_entry["section_sibling_index"] = artifact["section_sibling_index"]
                    result_entry["lineage_key"] = artifact["lineage_key"]
                    result_entry["lineage_status"] = artifact["lineage_status"]
                    result_entry["previous_artifact_id"] = artifact["previous_artifact_id"]
                    result_entry["previous_parent_artifact_id"] = artifact["previous_parent_artifact_id"]
                initial_results.append(result_entry)

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T12:00:00Z",
                    "items": initial_results,
                },
                plan=initial_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )
            save_manifest(root, config.manifest_path, manifest)

            repeat_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            repeat_plan_payload = repeat_plan.to_dict()
            repeat_artifact_index = {artifact["artifact_id"]: artifact for artifact in repeat_plan_payload["artifacts"]}
            repeat_results = []
            for operation in repeat_plan_payload["operations"]:
                if operation["action"] == "skip":
                    continue
                result_entry = {
                    "op_id": operation["op_id"],
                    "artifact_id": operation["artifact_id"],
                    "item_type": operation["item_type"],
                    "item_id": operation["op_id"].replace(":", "-"),
                    "target_key": operation["target_key"],
                    "source_artifact_id": operation["source_artifact_id"],
                    "phase_zone": operation["phase_zone"],
                    "workstream": operation["workstream"],
                    "collaboration_intent": operation["collaboration_intent"],
                    "container_target_key": operation["container_target_key"],
                    "heading_level": operation["heading_level"],
                    "parent_artifact_id": operation["parent_artifact_id"],
                    "execution_status": "created",
                    "updated_at": "2026-04-18T12:05:00Z",
                }
                artifact = repeat_artifact_index.get(operation["artifact_id"])
                if artifact is not None:
                    result_entry["artifact_sha256"] = artifact["sha256"]
                    result_entry["section_path"] = artifact["section_path"]
                    result_entry["section_title_path"] = artifact["section_title_path"]
                    result_entry["section_slug"] = artifact["section_slug"]
                    result_entry["section_sibling_index"] = artifact["section_sibling_index"]
                    result_entry["lineage_key"] = artifact["lineage_key"]
                    result_entry["lineage_status"] = artifact["lineage_status"]
                    result_entry["previous_artifact_id"] = artifact["previous_artifact_id"]
                    result_entry["previous_parent_artifact_id"] = artifact["previous_parent_artifact_id"]
                repeat_results.append(result_entry)

            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T12:05:00Z",
                    "items": repeat_results,
                },
                plan=repeat_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertEqual(
                [operation["action"] for operation in repeat_plan_payload["operations"]],
                ["ensure_zone", "ensure_workstream_anchor", "skip"],
            )
            self.assertEqual(manifest.last_run["run_status"], "complete")
            self.assertEqual(manifest.last_run["pending_operation_count"], 0)
            self.assertEqual(manifest.last_run["executed_operation_count"], manifest.last_run["total_operation_count"])

    def test_apply_results_marks_run_failed_when_failed_entries_and_pending_work_coexist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            plan_payload = plan.to_dict()
            write_json(runtime_dir / "plan.json", plan_payload)

            artifact = next(artifact for artifact in plan.artifacts if artifact.artifact_id.endswith("#prd"))
            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "partial",
                    "executed_at": "2026-04-17T23:55:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{artifact.artifact_id}",
                            "artifact_id": artifact.artifact_id,
                            "item_type": "doc",
                            "execution_status": "failed",
                            "error": "create_doc failed",
                        }
                    ],
                },
                plan=plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertEqual(manifest.last_run["run_status"], "failed")
            self.assertGreater(manifest.last_run["pending_operation_count"], 0)

    def test_apply_results_rejects_duplicate_result_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            plan_payload = plan.to_dict()
            write_json(runtime_dir / "plan.json", plan_payload)

            artifact = next(artifact for artifact in plan.artifacts if artifact.artifact_id.endswith("#prd"))
            with self.assertRaisesRegex(ValueError, "Duplicate results entry key"):
                apply_results(
                    SyncManifest(version=3, items={}),
                    {
                        "run_status": "partial",
                        "executed_at": "2026-04-17T23:55:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact.artifact_id}",
                                "artifact_id": artifact.artifact_id,
                                "artifact_sha256": artifact.sha256,
                                "item_type": "doc",
                                "target_key": f"artifact:{artifact.artifact_id}",
                                "execution_status": "created",
                            },
                            {
                                "op_id": f"doc:{artifact.artifact_id}",
                                "artifact_id": artifact.artifact_id,
                                "artifact_sha256": artifact.sha256,
                                "item_type": "doc",
                                "target_key": f"artifact:{artifact.artifact_id}",
                                "execution_status": "updated",
                            },
                        ],
                    },
                    plan=plan_payload,
                    plan_path=runtime_dir / "plan.json",
                    results_path=runtime_dir / "results.json",
                )

    def test_apply_results_pending_update_keeps_existing_mapping_and_current_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            config_path.write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            initial_plan_payload = initial_plan.to_dict()
            write_json(runtime_dir / "plan.json", initial_plan_payload)
            artifact = next(artifact for artifact in initial_plan.artifacts if artifact.artifact_id.endswith("#prd"))

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T00:05:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{artifact.artifact_id}",
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
                            "execution_status": "created",
                            "updated_at": "2026-04-18T00:05:00Z",
                        }
                    ],
                },
                plan=initial_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            doc_path.write_text("# PRD\n\nUpdated body\n", encoding="utf-8")
            pending_plan = build_sync_plan(root, config_path, config)
            pending_plan_payload = pending_plan.to_dict()
            updated_artifact = next(artifact for artifact in pending_plan.artifacts if artifact.artifact_id.endswith("#prd"))

            manifest = apply_results(
                manifest,
                {
                    "run_status": "partial",
                    "executed_at": "2026-04-18T00:10:00Z",
                    "items": [],
                },
                plan=pending_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            pending_operation = manifest.operations[f"doc:{updated_artifact.artifact_id}"]
            self.assertEqual(pending_operation["execution_status"], "pending")
            self.assertEqual(pending_operation["item_id"], "doc-123")
            self.assertEqual(
                pending_operation["miro_url"],
                "https://miro.com/app/board/x/?moveToWidget=doc-123",
            )
            self.assertEqual(pending_operation["content_fingerprint"], updated_artifact.sha256)
            self.assertIsNone(pending_operation["sync_timestamp"])

    def test_apply_results_failed_update_keeps_existing_mapping_in_operation_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            config_path.write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            initial_plan_payload = initial_plan.to_dict()
            write_json(runtime_dir / "plan.json", initial_plan_payload)
            artifact = next(artifact for artifact in initial_plan.artifacts if artifact.artifact_id.endswith("#prd"))

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T00:20:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{artifact.artifact_id}",
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
                            "execution_status": "created",
                            "updated_at": "2026-04-18T00:20:00Z",
                        }
                    ],
                },
                plan=initial_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            doc_path.write_text("# PRD\n\nUpdated body\n", encoding="utf-8")
            failed_plan = build_sync_plan(root, config_path, config)
            failed_plan_payload = failed_plan.to_dict()
            updated_artifact = next(artifact for artifact in failed_plan.artifacts if artifact.artifact_id.endswith("#prd"))

            manifest = apply_results(
                manifest,
                {
                    "run_status": "failed",
                    "executed_at": "2026-04-18T00:25:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{updated_artifact.artifact_id}",
                            "artifact_id": updated_artifact.artifact_id,
                            "item_type": "doc",
                            "execution_status": "failed",
                            "error": "update_doc failed",
                        }
                    ],
                },
                plan=failed_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            failed_operation = manifest.operations[f"doc:{updated_artifact.artifact_id}"]
            self.assertEqual(failed_operation["execution_status"], "failed")
            self.assertEqual(failed_operation["item_id"], "doc-123")
            self.assertEqual(
                failed_operation["miro_url"],
                "https://miro.com/app/board/x/?moveToWidget=doc-123",
            )
            self.assertEqual(failed_operation["content_fingerprint"], updated_artifact.sha256)
            self.assertEqual(failed_operation["sync_timestamp"], "2026-04-18T00:20:00Z")
            self.assertEqual(failed_operation["last_attempted_at"], "2026-04-18T00:25:00Z")
            self.assertEqual(manifest.items[updated_artifact.artifact_id]["item_id"], "doc-123")

    def test_apply_results_archived_transition_keeps_item_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            config_path.write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            initial_plan_payload = initial_plan.to_dict()
            write_json(runtime_dir / "plan.json", initial_plan_payload)
            section = next(artifact for artifact in initial_plan.artifacts if artifact.artifact_id.endswith("#prd/goals"))

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T10:00:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{artifact.artifact_id}",
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
                            "execution_status": "created",
                            "updated_at": "2026-04-18T10:00:00Z",
                        }
                        for index, artifact in enumerate(initial_plan.artifacts, start=1)
                    ],
                },
                plan=initial_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")
            archive_plan = build_sync_plan(root, config_path, config)
            archive_plan_payload = archive_plan.to_dict()

            manifest = apply_results(
                manifest,
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T10:05:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{section.artifact_id}",
                            "artifact_id": section.artifact_id,
                            "item_type": "doc",
                            "execution_status": "archived",
                        }
                    ],
                },
                plan=archive_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            archived_item = manifest.items[section.artifact_id]
            self.assertEqual(archived_item["item_id"], "doc-2")
            self.assertEqual(archived_item["lifecycle_state"], "archived")
            self.assertEqual(archived_item["execution_status"], "archived")
            self.assertEqual(archived_item["content_fingerprint"], section.sha256)
            self.assertEqual(archived_item["sync_timestamp"], "2026-04-18T10:05:00Z")
            self.assertEqual(archived_item["lifecycle_transitioned_at"], "2026-04-18T10:05:00Z")

    def test_apply_results_removed_transition_keeps_last_known_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            config_path.write_text(
                CONFIG_TEXT
                + """
[sync]
removed_item_policy = "remove"
""",
                encoding="utf-8",
            )
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            initial_plan_payload = initial_plan.to_dict()
            write_json(runtime_dir / "plan.json", initial_plan_payload)
            section = next(artifact for artifact in initial_plan.artifacts if artifact.artifact_id.endswith("#prd/goals"))

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T10:10:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{artifact.artifact_id}",
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
                            "execution_status": "created",
                            "updated_at": "2026-04-18T10:10:00Z",
                        }
                        for index, artifact in enumerate(initial_plan.artifacts, start=1)
                    ],
                },
                plan=initial_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")
            remove_plan = build_sync_plan(root, config_path, config)
            remove_plan_payload = remove_plan.to_dict()

            manifest = apply_results(
                manifest,
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T10:15:00Z",
                    "items": [
                        {
                            "op_id": f"doc:{section.artifact_id}",
                            "artifact_id": section.artifact_id,
                            "item_type": "doc",
                            "execution_status": "removed",
                        }
                    ],
                },
                plan=remove_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            removed_item = manifest.items[section.artifact_id]
            self.assertEqual(removed_item["item_id"], "doc-2")
            self.assertEqual(removed_item["miro_url"], "https://miro.com/app/board/x/?moveToWidget=doc-2")
            self.assertEqual(removed_item["lifecycle_state"], "removed")
            self.assertEqual(removed_item["execution_status"], "removed")
            self.assertEqual(removed_item["content_fingerprint"], section.sha256)
            self.assertEqual(removed_item["lifecycle_transitioned_at"], "2026-04-18T10:15:00Z")

    def test_apply_results_preserves_new_mapping_when_replacing_item_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            story_path = root / "_bmad-output/implementation-artifacts/1-3-sample-story.md"
            config_path.write_text(CONFIG_TEXT, encoding="utf-8")
            story_path.write_text(
                "# Story 1.3: Sample\n\nStatus: review\n\n- [x] Task one\n- [ ] Task two\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            initial_plan_payload = initial_plan.to_dict()
            write_json(runtime_dir / "plan.json", initial_plan_payload)
            root_table_operation = next(operation for operation in initial_plan.operations if operation.item_type == "table")
            root_artifact = next(artifact for artifact in initial_plan.artifacts if artifact.artifact_id == root_table_operation.artifact_id)

            manifest = apply_results(
                SyncManifest(version=3, items={}),
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T10:20:00Z",
                    "items": [
                        {
                            "op_id": root_table_operation.op_id,
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
                            "execution_status": "created",
                            "updated_at": "2026-04-18T10:20:00Z",
                        }
                    ],
                },
                plan=initial_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )
            save_manifest(root, config.manifest_path, manifest)

            story_path.write_text(
                "# Story 1.3: Sample\n\nStatus: review\n\n## Story\n\nBody\n",
                encoding="utf-8",
            )
            replacement_plan = build_sync_plan(root, config_path, config)
            replacement_plan_payload = replacement_plan.to_dict()
            replacement_artifact = next(
                artifact for artifact in replacement_plan.artifacts if artifact.artifact_id == root_artifact.artifact_id
            )
            create_operation = next(
                operation
                for operation in replacement_plan.operations
                if operation.artifact_id == root_artifact.artifact_id and operation.item_type == "doc"
            )
            retire_operation = next(
                operation
                for operation in replacement_plan.operations
                if operation.action == "archive_table" and operation.existing_item and operation.existing_item["artifact_id"] == root_artifact.artifact_id
            )

            manifest = apply_results(
                manifest,
                {
                    "run_status": "complete",
                    "executed_at": "2026-04-18T10:25:00Z",
                    "items": [
                        {
                            "op_id": create_operation.op_id,
                            "artifact_id": create_operation.artifact_id,
                            "artifact_sha256": replacement_artifact.sha256,
                            "item_type": create_operation.item_type,
                            "item_id": "doc-2",
                            "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-2",
                            "title": create_operation.title,
                            "target_key": create_operation.target_key,
                            "source_artifact_id": create_operation.source_artifact_id,
                            "phase_zone": create_operation.phase_zone,
                            "workstream": create_operation.workstream,
                            "collaboration_intent": create_operation.collaboration_intent,
                            "container_target_key": create_operation.container_target_key,
                            "heading_level": create_operation.heading_level,
                            "parent_artifact_id": create_operation.parent_artifact_id,
                            "section_path": list(replacement_artifact.section_path),
                            "section_title_path": list(replacement_artifact.section_title_path),
                            "section_slug": replacement_artifact.section_slug,
                            "section_sibling_index": replacement_artifact.section_sibling_index,
                            "lineage_key": replacement_artifact.lineage_key,
                            "lineage_status": replacement_artifact.lineage_status,
                            "previous_artifact_id": replacement_artifact.previous_artifact_id,
                            "previous_parent_artifact_id": replacement_artifact.previous_parent_artifact_id,
                            "execution_status": "created",
                            "updated_at": "2026-04-18T10:25:00Z",
                        },
                        {
                            "op_id": retire_operation.op_id,
                            "artifact_id": retire_operation.artifact_id,
                            "item_type": retire_operation.item_type,
                            "execution_status": "archived",
                            "updated_at": "2026-04-18T10:25:00Z",
                        },
                    ],
                },
                plan=replacement_plan_payload,
                plan_path=runtime_dir / "plan.json",
                results_path=runtime_dir / "results.json",
            )

            self.assertEqual(manifest.items[root_artifact.artifact_id]["item_id"], "doc-2")
            self.assertEqual(manifest.items[root_artifact.artifact_id]["item_type"], "doc")
            archived_item = manifest.items[retire_operation.artifact_id]
            self.assertEqual(archived_item["item_id"], "table-1")
            self.assertEqual(archived_item["item_type"], "table")
            self.assertEqual(archived_item["lifecycle_state"], "archived")
            self.assertEqual(archived_item["execution_status"], "archived")

    def test_apply_results_repeat_update_round_trips_layout_snapshot(self) -> None:
        existing_item = {
            "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
            "artifact_sha256": "old-sha",
            "content_fingerprint": "old-sha",
            "item_type": "doc",
            "item_id": "doc-123",
            "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
            "title": "PRD / Goals",
            "updated_at": "2026-04-18T10:00:00Z",
            "sync_timestamp": "2026-04-18T10:00:00Z",
            "execution_status": "updated",
            "lifecycle_state": "active",
            "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
            "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
            "phase": "planning",
            "phase_zone": "planning",
            "workstream": "product",
            "collaboration_intent": "anchor",
            "container_target_key": "workstream:planning:product",
            "heading_level": 1,
            "parent_artifact_id": "_bmad-output/planning-artifacts/prd.md#prd",
            "section_path": ["prd", "goals"],
            "section_title_path": ["PRD", "Goals"],
            "section_slug": "goals",
            "section_sibling_index": 1,
            "lineage_key": "prd::goals",
            "lineage_status": "unchanged",
            "previous_artifact_id": None,
            "previous_parent_artifact_id": None,
            "layout_snapshot": {
                "x": 110,
                "y": 220,
                "width": 320,
                "height": 180,
                "parent_item_id": "frame-1",
                "group_id": "group-1",
            },
        }
        plan = {
            "artifacts": [
                {
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "relative_path": "_bmad-output/planning-artifacts/prd.md",
                    "content": "Updated body",
                    "sha256": "new-sha",
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "section_path": existing_item["section_path"],
                    "section_title_path": existing_item["section_title_path"],
                    "section_slug": existing_item["section_slug"],
                    "section_sibling_index": existing_item["section_sibling_index"],
                    "lineage_key": existing_item["lineage_key"],
                    "lineage_status": existing_item["lineage_status"],
                    "previous_artifact_id": existing_item["previous_artifact_id"],
                    "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                }
            ],
            "operations": [
                {
                    "op_id": f"doc:{existing_item['artifact_id']}",
                    "action": "update_doc",
                    "item_type": "doc",
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "target_key": existing_item["target_key"],
                    "container_target_key": existing_item["container_target_key"],
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "layout_policy": "preserve",
                    "layout_snapshot": existing_item["layout_snapshot"],
                    "existing_item": existing_item,
                }
            ],
        }
        results = {
            "run_status": "complete",
            "executed_at": "2026-04-18T10:45:00Z",
            "items": [
                {
                    "op_id": f"doc:{existing_item['artifact_id']}",
                    "artifact_id": existing_item["artifact_id"],
                    "artifact_sha256": "new-sha",
                    "item_type": "doc",
                    "item_id": existing_item["item_id"],
                    "miro_url": existing_item["miro_url"],
                    "title": existing_item["title"],
                    "target_key": existing_item["target_key"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "container_target_key": existing_item["container_target_key"],
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "section_path": existing_item["section_path"],
                    "section_title_path": existing_item["section_title_path"],
                    "section_slug": existing_item["section_slug"],
                    "section_sibling_index": existing_item["section_sibling_index"],
                    "lineage_key": existing_item["lineage_key"],
                    "lineage_status": existing_item["lineage_status"],
                    "previous_artifact_id": existing_item["previous_artifact_id"],
                    "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                    "layout_snapshot": {
                        "x": 175,
                        "y": 260,
                        "width": 480,
                        "height": 220,
                        "parent_item_id": "frame-2",
                        "group_id": "group-9",
                    },
                    "execution_status": "updated",
                    "updated_at": "2026-04-18T10:45:00Z",
                }
            ],
        }

        manifest = apply_results(
            SyncManifest(version=3, items={existing_item["artifact_id"]: existing_item}),
            results,
            plan=plan,
            plan_path=".bmad-miro-sync/run/plan.json",
            results_path=".bmad-miro-sync/run/results.json",
        )

        updated_item = manifest.items[existing_item["artifact_id"]]
        self.assertEqual(updated_item["item_id"], "doc-123")
        self.assertEqual(updated_item["layout_policy"], "preserve")
        self.assertEqual(
            updated_item["layout_snapshot"],
            {
                "x": 175,
                "y": 260,
                "width": 480,
                "height": 220,
                "parent_item_id": "frame-2",
                "group_id": "group-9",
            },
        )
        self.assertEqual(
            manifest.operations[f"doc:{existing_item['artifact_id']}"]["layout_snapshot"],
            updated_item["layout_snapshot"],
        )
        self.assertEqual(manifest.operations[f"doc:{existing_item['artifact_id']}"]["layout_policy"], "preserve")

    def test_apply_results_merges_partial_layout_snapshot_updates(self) -> None:
        existing_item = {
            "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
            "artifact_sha256": "old-sha",
            "content_fingerprint": "old-sha",
            "item_type": "doc",
            "item_id": "doc-123",
            "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
            "title": "PRD / Goals",
            "updated_at": "2026-04-18T10:00:00Z",
            "sync_timestamp": "2026-04-18T10:00:00Z",
            "execution_status": "updated",
            "lifecycle_state": "active",
            "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
            "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
            "phase": "planning",
            "phase_zone": "planning",
            "workstream": "product",
            "collaboration_intent": "anchor",
            "container_target_key": "workstream:planning:product",
            "heading_level": 1,
            "parent_artifact_id": "_bmad-output/planning-artifacts/prd.md#prd",
            "section_path": ["prd", "goals"],
            "section_title_path": ["PRD", "Goals"],
            "section_slug": "goals",
            "section_sibling_index": 1,
            "lineage_key": "prd::goals",
            "lineage_status": "unchanged",
            "previous_artifact_id": None,
            "previous_parent_artifact_id": None,
            "layout_snapshot": {
                "x": 110,
                "y": 220,
                "width": 320,
                "height": 180,
                "parent_item_id": "frame-1",
                "group_id": "group-1",
            },
        }
        plan = {
            "artifacts": [
                {
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "relative_path": "_bmad-output/planning-artifacts/prd.md",
                    "content": "Updated body",
                    "sha256": "new-sha",
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "section_path": existing_item["section_path"],
                    "section_title_path": existing_item["section_title_path"],
                    "section_slug": existing_item["section_slug"],
                    "section_sibling_index": existing_item["section_sibling_index"],
                    "lineage_key": existing_item["lineage_key"],
                    "lineage_status": existing_item["lineage_status"],
                    "previous_artifact_id": existing_item["previous_artifact_id"],
                    "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                }
            ],
            "operations": [
                {
                    "op_id": f"doc:{existing_item['artifact_id']}",
                    "action": "update_doc",
                    "item_type": "doc",
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "target_key": existing_item["target_key"],
                    "container_target_key": existing_item["container_target_key"],
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "layout_policy": "preserve",
                    "layout_snapshot": existing_item["layout_snapshot"],
                    "existing_item": existing_item,
                }
            ],
        }

        manifest = apply_results(
            SyncManifest(version=3, items={existing_item["artifact_id"]: existing_item}),
            {
                "run_status": "complete",
                "executed_at": "2026-04-18T10:55:00Z",
                "items": [
                    {
                        "op_id": f"doc:{existing_item['artifact_id']}",
                        "artifact_id": existing_item["artifact_id"],
                        "artifact_sha256": "new-sha",
                        "item_type": "doc",
                        "item_id": existing_item["item_id"],
                        "miro_url": existing_item["miro_url"],
                        "title": existing_item["title"],
                        "target_key": existing_item["target_key"],
                        "source_artifact_id": existing_item["source_artifact_id"],
                        "phase_zone": existing_item["phase_zone"],
                        "workstream": existing_item["workstream"],
                        "collaboration_intent": existing_item["collaboration_intent"],
                        "container_target_key": existing_item["container_target_key"],
                        "heading_level": existing_item["heading_level"],
                        "parent_artifact_id": existing_item["parent_artifact_id"],
                        "layout_snapshot": {
                            "x": 175,
                            "y": 260,
                        },
                        "execution_status": "updated",
                        "updated_at": "2026-04-18T10:55:00Z",
                    }
                ],
            },
            plan=plan,
            plan_path=".bmad-miro-sync/run/plan.json",
            results_path=".bmad-miro-sync/run/results.json",
        )

        updated_item = manifest.items[existing_item["artifact_id"]]
        self.assertEqual(updated_item["layout_snapshot"]["x"], 175)
        self.assertEqual(updated_item["layout_snapshot"]["y"], 260)
        self.assertEqual(updated_item["layout_snapshot"]["width"], 320)
        self.assertEqual(updated_item["layout_snapshot"]["height"], 180)
        self.assertEqual(updated_item["layout_snapshot"]["parent_item_id"], "frame-1")
        self.assertEqual(updated_item["layout_snapshot"]["group_id"], "group-1")

    def test_apply_results_persists_degraded_mode_metadata_and_run_level_strategy_state(self) -> None:
        existing_item = {
            "artifact_id": "_bmad-output/implementation-artifacts/story.md#story",
            "artifact_sha256": "old-sha",
            "content_fingerprint": "old-sha",
            "item_type": "table",
            "item_id": "table-1",
            "miro_url": "https://miro.com/app/board/x/?moveToWidget=table-1",
            "title": "Story / Summary",
            "updated_at": "2026-04-18T11:00:00Z",
            "sync_timestamp": "2026-04-18T11:00:00Z",
            "execution_status": "created",
            "lifecycle_state": "active",
            "target_key": "artifact:_bmad-output/implementation-artifacts/story.md#story",
            "source_artifact_id": "_bmad-output/implementation-artifacts/story.md",
            "phase": "implementation",
            "phase_zone": "implementation_readiness",
            "workstream": "delivery",
            "collaboration_intent": "summary",
            "container_target_key": "workstream:implementation_readiness:delivery",
            "object_family": "story_summary",
            "preferred_item_type": "table",
            "resolved_item_type": "table",
            "degraded": False,
            "heading_level": 0,
            "parent_artifact_id": None,
            "section_path": ["story"],
            "section_title_path": ["Story 1.3: Sample"],
            "section_slug": "story",
            "section_sibling_index": 1,
            "lineage_key": "story::summary",
            "lineage_status": "new",
            "previous_artifact_id": None,
            "previous_parent_artifact_id": None,
        }
        plan = {
            "warnings": [
                "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
            ],
            "object_strategies": [
                {
                    "object_family": "story_summary",
                    "preferred_item_type": "table",
                    "resolved_item_type": "doc",
                    "degraded": True,
                    "fallback_reason": "Configured object strategy resolved story summaries to docs.",
                    "degraded_warning": "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                }
            ],
            "artifacts": [
                {
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "relative_path": "story.md",
                    "content": "Story body",
                    "sha256": "new-sha",
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                    "section_path": existing_item["section_path"],
                    "section_title_path": existing_item["section_title_path"],
                    "section_slug": existing_item["section_slug"],
                    "section_sibling_index": existing_item["section_sibling_index"],
                    "lineage_key": existing_item["lineage_key"],
                    "lineage_status": existing_item["lineage_status"],
                    "previous_artifact_id": existing_item["previous_artifact_id"],
                    "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                }
            ],
            "operations": [
                {
                    "op_id": f"doc:{existing_item['artifact_id']}",
                    "action": "create_doc",
                    "item_type": "doc",
                    "title": existing_item["title"],
                    "phase": existing_item["phase"],
                    "phase_zone": existing_item["phase_zone"],
                    "workstream": existing_item["workstream"],
                    "collaboration_intent": existing_item["collaboration_intent"],
                    "artifact_id": existing_item["artifact_id"],
                    "source_artifact_id": existing_item["source_artifact_id"],
                    "target_key": existing_item["target_key"],
                    "container_target_key": existing_item["container_target_key"],
                    "object_family": "story_summary",
                    "preferred_item_type": "table",
                    "resolved_item_type": "doc",
                    "degraded": True,
                    "fallback_reason": "Configured object strategy resolved story summaries to docs.",
                    "degraded_warning": "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                    "heading_level": existing_item["heading_level"],
                    "parent_artifact_id": existing_item["parent_artifact_id"],
                }
            ],
        }

        manifest = apply_results(
            SyncManifest(version=3, items={existing_item["artifact_id"]: existing_item}),
            {
                "run_status": "complete",
                "executed_at": "2026-04-18T11:20:00Z",
                "warnings": ["Host executed degraded-mode doc fallback successfully."],
                "object_strategies": [
                    {
                        "object_family": "story_summary",
                        "preferred_item_type": "table",
                        "resolved_item_type": "doc",
                        "degraded": True,
                        "fallback_reason": "Host confirmed story summary fallback to docs during execution.",
                        "degraded_warning": "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                    }
                ],
                "items": [
                    {
                        "op_id": f"doc:{existing_item['artifact_id']}",
                        "artifact_id": existing_item["artifact_id"],
                        "artifact_sha256": "new-sha",
                        "item_type": "doc",
                        "item_id": "doc-2",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-2",
                        "title": existing_item["title"],
                        "target_key": existing_item["target_key"],
                        "source_artifact_id": existing_item["source_artifact_id"],
                        "phase_zone": existing_item["phase_zone"],
                        "workstream": existing_item["workstream"],
                        "collaboration_intent": existing_item["collaboration_intent"],
                        "container_target_key": existing_item["container_target_key"],
                        "object_family": "story_summary",
                        "preferred_item_type": "table",
                        "resolved_item_type": "doc",
                        "degraded": True,
                        "fallback_reason": "Configured object strategy resolved story summaries to docs.",
                        "degraded_warning": "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                        "heading_level": existing_item["heading_level"],
                        "parent_artifact_id": existing_item["parent_artifact_id"],
                        "section_path": existing_item["section_path"],
                        "section_title_path": existing_item["section_title_path"],
                        "section_slug": existing_item["section_slug"],
                        "section_sibling_index": existing_item["section_sibling_index"],
                        "lineage_key": existing_item["lineage_key"],
                        "lineage_status": existing_item["lineage_status"],
                        "previous_artifact_id": existing_item["previous_artifact_id"],
                        "previous_parent_artifact_id": existing_item["previous_parent_artifact_id"],
                        "execution_status": "created",
                        "updated_at": "2026-04-18T11:20:00Z",
                    }
                ],
            },
            plan=plan,
            plan_path=".bmad-miro-sync/run/plan.json",
            results_path=".bmad-miro-sync/run/results.json",
        )

        updated_item = manifest.items[existing_item["artifact_id"]]
        self.assertEqual(updated_item["item_type"], "doc")
        self.assertEqual(updated_item["preferred_item_type"], "table")
        self.assertEqual(updated_item["resolved_item_type"], "doc")
        self.assertTrue(updated_item["degraded"])
        self.assertIn("story summaries", updated_item["degraded_warning"])
        self.assertIn("object_strategies", manifest.last_run)
        self.assertEqual(manifest.last_run["object_strategies"][0]["resolved_item_type"], "doc")
        self.assertEqual(
            manifest.last_run["object_strategies"][0]["fallback_reason"],
            "Host confirmed story summary fallback to docs during execution.",
        )
        self.assertIn(
            "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
            manifest.last_run["warnings"],
        )
        self.assertIn(
            "Host executed degraded-mode doc fallback successfully.",
            manifest.last_run["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
