from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.workflow import (
    DEFAULT_COLLABORATION_REPORT_PATH,
    DEFAULT_COMMENTS_PATH,
    DEFAULT_RESULTS_PATH,
    DEFAULT_REVIEW_INPUT_PATH,
    WorkflowStageError,
    run_codex_collaboration_workflow,
)


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

CUSTOM_MANIFEST_CONFIG_TEXT = """
board_url = "https://miro.com/app/board/uXjVGixS6vQ=/"
source_root = "_bmad-output"
manifest_path = "custom/state.json"

[layout]
create_phase_frames = true

[publish]
analysis = true
planning = true
solutioning = true
implementation = true
stories_table = true
"""


class CollaborationWorkflowTests(unittest.TestCase):
    def test_run_codex_collaboration_workflow_rejects_out_of_repo_runtime_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "project"
            outside_root = Path(tmpdir) / "outside"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            outside_root.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "runtime_dir must stay inside the project root"):
                run_codex_collaboration_workflow(
                    root,
                    root / ".bmad-miro.toml",
                    runtime_dir=outside_root / "run",
                )

            with self.assertRaisesRegex(ValueError, "report_path must stay inside the project root"):
                run_codex_collaboration_workflow(
                    root,
                    root / ".bmad-miro.toml",
                    report_path=outside_root / "collaboration-run.json",
                )

    def test_run_codex_collaboration_workflow_rejects_runtime_dir_that_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            runtime_file = root / ".bmad-miro-sync" / "run"
            runtime_file.parent.mkdir(parents=True)
            runtime_file.write_text("not a directory\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowStageError, "Invalid repo-local runtime_dir:"):
                run_codex_collaboration_workflow(root, root / ".bmad-miro.toml")

    def test_run_codex_collaboration_workflow_rejects_report_path_that_is_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            report_dir = root / ".bmad-miro-sync" / "run" / "collaboration-run.json"
            report_dir.mkdir(parents=True)

            with self.assertRaisesRegex(WorkflowStageError, "Invalid repo-local report path:"):
                run_codex_collaboration_workflow(root, root / ".bmad-miro.toml")

    def test_run_codex_collaboration_workflow_reports_configured_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CUSTOM_MANIFEST_CONFIG_TEXT, encoding="utf-8")
            runtime_dir.mkdir(parents=True)

            publish_seed = run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", stop_after="publish")
            artifact = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))["artifacts"][0]
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "comments.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "section_id": artifact["artifact_id"],
                                "source_artifact_id": artifact["source_artifact_id"],
                                "section_title": artifact["title"],
                                "topic": "Acceptance criteria",
                                "author": "Reviewer",
                                "created_at": "2026-04-18T09:10:00Z",
                                "body": "Looks good.",
                                "published_object_id": "doc-123",
                                "published_object_type": "doc",
                                "published_object_reference": f"artifact:{artifact['artifact_id']}",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "review-input.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "section_id": artifact["artifact_id"],
                                "source_artifact_id": artifact["source_artifact_id"],
                                "section_title": artifact["title"],
                                "topic": "Acceptance criteria",
                                "author": "Reviewer",
                                "created_at": "2026-04-18T09:10:00Z",
                                "body": "Looks good.",
                                "published_object_id": "doc-123",
                                "published_object_type": "doc",
                                "published_object_reference": f"artifact:{artifact['artifact_id']}",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            }
                        ],
                        "triage": [
                            {
                                "section_id": artifact["artifact_id"],
                                "topic": "Acceptance criteria",
                                "status": "accepted",
                                "owner": "product",
                                "rationale": "Approved in review",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            report = run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", start_at="apply-results")

            self.assertEqual(publish_seed["artifacts"]["runtime"]["state"], "custom/state.json")
            self.assertEqual(report["artifacts"]["runtime"]["state"], "custom/state.json")
            self.assertTrue((root / "custom/state.json").exists())

    def test_run_codex_collaboration_workflow_writes_repo_local_run_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            runtime_dir.mkdir(parents=True)

            publish_seed = run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", stop_after="publish")
            self.assertEqual(publish_seed["artifacts"]["publish"]["bundle"], ".bmad-miro-sync/run/publish-bundle.json")
            self.assertEqual(
                publish_seed["artifacts"]["publish"]["bundle_aliases"],
                [".bmad-miro-sync/run/codex-bundle.json"],
            )
            self.assertTrue((runtime_dir / "publish-bundle.json").exists())
            self.assertTrue((runtime_dir / "codex-bundle.json").exists())
            artifact = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))["artifacts"][0]
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "comments.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "section_id": artifact["artifact_id"],
                                "source_artifact_id": artifact["source_artifact_id"],
                                "section_title": artifact["title"],
                                "topic": "Acceptance criteria",
                                "author": "Reviewer",
                                "created_at": "2026-04-18T09:10:00Z",
                                "body": "Looks good.",
                                "published_object_id": "doc-123",
                                "published_object_type": "doc",
                                "published_object_reference": f"artifact:{artifact['artifact_id']}",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "review-input.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "section_id": artifact["artifact_id"],
                                "source_artifact_id": artifact["source_artifact_id"],
                                "section_title": artifact["title"],
                                "topic": "Acceptance criteria",
                                "author": "Reviewer",
                                "created_at": "2026-04-18T09:10:00Z",
                                "body": "Looks good.",
                                "published_object_id": "doc-123",
                                "published_object_type": "doc",
                                "published_object_reference": f"artifact:{artifact['artifact_id']}",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            }
                        ],
                        "triage": [
                            {
                                "section_id": artifact["artifact_id"],
                                "topic": "Acceptance criteria",
                                "status": "accepted",
                                "owner": "product",
                                "rationale": "Approved in review",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            report = run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", start_at="apply-results")

            self.assertEqual(publish_seed["run_status"], "partial")
            self.assertEqual(publish_seed["stages"]["publish"]["status"], "completed")
            self.assertEqual(report["run_status"], "completed")
            self.assertEqual(report["report_path"], DEFAULT_COLLABORATION_REPORT_PATH)
            self.assertEqual(report["artifacts"]["runtime"]["results"], DEFAULT_RESULTS_PATH)
            self.assertEqual(report["artifacts"]["runtime"]["comments"], DEFAULT_COMMENTS_PATH)
            self.assertEqual(report["artifacts"]["runtime"]["review_input"], DEFAULT_REVIEW_INPUT_PATH)
            self.assertTrue((root / DEFAULT_COLLABORATION_REPORT_PATH).exists())
            self.assertEqual(report["stages"]["publish"]["status"], "completed")
            self.assertEqual(
                report["stages"]["publish"]["message"],
                "Exported the Codex publish bundle and stage instructions.",
            )
            self.assertEqual(
                report["stages"]["publish"]["started_at"],
                publish_seed["stages"]["publish"]["started_at"],
            )
            self.assertEqual(
                report["stages"]["publish"]["completed_at"],
                publish_seed["stages"]["publish"]["completed_at"],
            )
            self.assertEqual(report["stages"]["apply-results"]["status"], "completed")
            self.assertEqual(report["stages"]["ingest-comments"]["status"], "completed")
            self.assertEqual(report["stages"]["triage-feedback"]["status"], "completed")
            self.assertEqual(report["stages"]["summarize-readiness"]["status"], "completed")

    def test_run_codex_collaboration_workflow_preserves_earlier_stage_outputs_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            runtime_dir.mkdir(parents=True)

            run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", stop_after="publish")
            artifact = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))["artifacts"][0]
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "comments.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "section_id": artifact["artifact_id"],
                                "source_artifact_id": artifact["source_artifact_id"],
                                "section_title": artifact["title"],
                                "topic": "Acceptance criteria",
                                "author": "Reviewer",
                                "created_at": "2026-04-18T09:10:00Z",
                                "body": "Needs triage.",
                                "published_object_id": "doc-123",
                                "published_object_type": "doc",
                                "published_object_reference": f"artifact:{artifact['artifact_id']}",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            report = run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", start_at="apply-results")

            self.assertEqual(report["run_status"], "failed")
            self.assertEqual(report["failed_stage"], "triage-feedback")
            self.assertEqual(report["stages"]["apply-results"]["status"], "completed")
            self.assertEqual(report["stages"]["ingest-comments"]["status"], "completed")
            self.assertEqual(report["stages"]["triage-feedback"]["status"], "failed")
            self.assertEqual(report["stages"]["summarize-readiness"]["status"], "pending")
            self.assertTrue((root / ".bmad-miro-sync/state.json").exists())
            self.assertTrue((root / "_bmad-output/review-artifacts/miro-comments.md").exists())

    def test_run_codex_collaboration_workflow_requires_runtime_plan_when_resuming_apply_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            runtime_dir.mkdir(parents=True)

            run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", stop_after="publish")
            artifact = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))["artifacts"][0]
            (runtime_dir / "plan.json").unlink()
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            report = run_codex_collaboration_workflow(
                root,
                root / ".bmad-miro.toml",
                start_at="apply-results",
                stop_after="apply-results",
            )

            self.assertEqual(report["run_status"], "failed")
            self.assertEqual(report["failed_stage"], "apply-results")
            self.assertEqual(report["stages"]["publish"]["status"], "completed")
            self.assertEqual(report["stages"]["apply-results"]["status"], "failed")
            self.assertIn(".bmad-miro-sync/run/plan.json", report["stages"]["apply-results"]["message"])
            self.assertIn("Re-run the publish stage", report["stages"]["apply-results"]["message"])

    def test_run_codex_collaboration_workflow_rejects_manifest_mismatch_when_resuming_apply_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            runtime_dir.mkdir(parents=True)

            run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", stop_after="publish")
            artifact = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))["artifacts"][0]
            plan_payload = json.loads((runtime_dir / "plan.json").read_text(encoding="utf-8"))
            plan_payload["manifest_path"] = "custom/state.json"
            (runtime_dir / "plan.json").write_text(json.dumps(plan_payload, indent=2) + "\n", encoding="utf-8")
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "execution_status": "created",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            report = run_codex_collaboration_workflow(
                root,
                root / ".bmad-miro.toml",
                start_at="apply-results",
                stop_after="apply-results",
            )

            self.assertEqual(report["run_status"], "failed")
            self.assertEqual(report["failed_stage"], "apply-results")
            self.assertIn("Plan/runtime manifest mismatch", report["stages"]["apply-results"]["message"])

    def test_run_codex_collaboration_workflow_reports_invalid_comments_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            runtime_dir.mkdir(parents=True)

            run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", stop_after="publish")
            artifact = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))["artifacts"][0]
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "comments.json").write_text(json.dumps({"foo": []}, indent=2) + "\n", encoding="utf-8")

            report = run_codex_collaboration_workflow(root, root / ".bmad-miro.toml", start_at="apply-results")

            self.assertEqual(report["run_status"], "failed")
            self.assertEqual(report["failed_stage"], "ingest-comments")
            self.assertIn("Comments input must include a 'comments' list.", report["stages"]["ingest-comments"]["message"])


if __name__ == "__main__":
    unittest.main()
