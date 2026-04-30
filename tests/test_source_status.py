from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.config import load_config
from bmad_miro_sync.manifest import apply_results, load_manifest
from bmad_miro_sync.source_status import build_source_status_ledger
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


class SourceStatusTests(unittest.TestCase):
    def test_source_status_reports_not_published_for_new_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root, config_path = _write_basic_prd_project(Path(tmpdir))
            config = load_config(config_path)
            plan = build_sync_plan(root, config_path, config)
            manifest = load_manifest(root, config.manifest_path)

            ledger = build_source_status_ledger(plan, manifest)
            status = ledger.sources["_bmad-output/planning-artifacts/prd.md"]

            self.assertEqual(status.status, "not_published")
            self.assertEqual(status.derived_section_count, 2)
            self.assertEqual(status.published_section_count, 0)
            self.assertEqual(status.pending_section_count, 2)

    def test_source_status_reports_published_when_all_current_sections_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root, config_path = _write_basic_prd_project(Path(tmpdir))
            config = load_config(config_path)
            plan = build_sync_plan(root, config_path, config)
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                _successful_results(plan, updated_at="2026-04-27T11:05:00Z"),
            )

            ledger = build_source_status_ledger(plan, manifest)
            status = ledger.sources["_bmad-output/planning-artifacts/prd.md"]

            self.assertEqual(status.status, "published")
            self.assertEqual(status.published_section_count, 2)
            self.assertEqual(status.pending_section_count, 0)
            self.assertEqual(status.published_source_sha256, status.source_sha256)
            self.assertEqual(status.last_successful_publish_at, "2026-04-27T11:05:00Z")

    def test_source_status_reports_partially_published_when_only_some_sections_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root, config_path = _write_basic_prd_project(Path(tmpdir))
            config = load_config(config_path)
            plan = build_sync_plan(root, config_path, config)
            first_artifact = plan.artifacts[0]
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "run_status": "partial",
                    "executed_at": "2026-04-27T11:10:00Z",
                    "items": [
                        {
                            "artifact_id": first_artifact.artifact_id,
                            "artifact_sha256": first_artifact.sha256,
                            "source_artifact_id": first_artifact.source_artifact_id,
                            "item_type": "doc",
                            "title": first_artifact.title,
                            "phase": first_artifact.phase,
                            "phase_zone": first_artifact.phase_zone,
                            "workstream": first_artifact.workstream,
                            "collaboration_intent": first_artifact.collaboration_intent,
                            "target_key": f"artifact:{first_artifact.artifact_id}",
                            "item_id": "item-1",
                            "miro_url": "https://miro.com/app/board/uXjVGixS6vQ=/",
                            "execution_status": "created",
                            "updated_at": "2026-04-27T11:10:00Z",
                        }
                    ],
                },
            )

            ledger = build_source_status_ledger(plan, manifest)
            status = ledger.sources["_bmad-output/planning-artifacts/prd.md"]

            self.assertEqual(status.status, "partially_published")
            self.assertEqual(status.published_section_count, 1)
            self.assertEqual(status.pending_section_count, 1)

    def test_source_status_reports_out_of_date_when_source_hash_changes_after_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root, config_path = _write_basic_prd_project(Path(tmpdir))
            config = load_config(config_path)
            initial_plan = build_sync_plan(root, config_path, config)
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                _successful_results(initial_plan, updated_at="2026-04-27T11:15:00Z"),
            )
            initial_ledger = build_source_status_ledger(initial_plan, manifest)

            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\nIntro revised\n\n## Goals\n\nBody revised\n",
                encoding="utf-8",
            )
            updated_plan = build_sync_plan(root, config_path, config)

            updated_ledger = build_source_status_ledger(updated_plan, manifest, previous_ledger=initial_ledger)
            status = updated_ledger.sources["_bmad-output/planning-artifacts/prd.md"]

            self.assertEqual(status.status, "out_of_date")
            self.assertNotEqual(status.source_sha256, initial_ledger.sources["_bmad-output/planning-artifacts/prd.md"].source_sha256)
            self.assertEqual(status.published_source_sha256, initial_ledger.sources["_bmad-output/planning-artifacts/prd.md"].published_source_sha256)

    def test_source_status_reports_failed_when_current_results_include_failed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root, config_path = _write_basic_prd_project(Path(tmpdir))
            config = load_config(config_path)
            plan = build_sync_plan(root, config_path, config)
            failed_artifact = plan.artifacts[0]

            ledger = build_source_status_ledger(
                plan,
                load_manifest(root, config.manifest_path),
                results={
                    "run_status": "failed",
                    "executed_at": "2026-04-27T11:20:00Z",
                    "items": [
                        {
                            "artifact_id": failed_artifact.artifact_id,
                            "source_artifact_id": failed_artifact.source_artifact_id,
                            "execution_status": "failed",
                            "error": "Miro rejected the payload",
                        }
                    ],
                },
            )
            status = ledger.sources["_bmad-output/planning-artifacts/prd.md"]

            self.assertEqual(status.status, "failed")
            self.assertEqual(status.failed_section_count, 1)
            self.assertEqual(status.last_failed_publish_at, "2026-04-27T11:20:00Z")
            self.assertEqual(status.last_error, "Miro rejected the payload")


def _write_basic_prd_project(root: Path) -> tuple[Path, Path]:
    (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
    config_path = root / ".bmad-miro.toml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")
    (root / "_bmad-output/planning-artifacts/prd.md").write_text(
        "# PRD\n\nIntro\n\n## Goals\n\nBody\n",
        encoding="utf-8",
    )
    return root, config_path


def _successful_results(plan, *, updated_at: str) -> dict:
    items = []
    for artifact in plan.artifacts:
        items.append(
            {
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "source_artifact_id": artifact.source_artifact_id,
                "item_type": "doc",
                "title": artifact.title,
                "phase": artifact.phase,
                "phase_zone": artifact.phase_zone,
                "workstream": artifact.workstream,
                "collaboration_intent": artifact.collaboration_intent,
                "target_key": f"artifact:{artifact.artifact_id}",
                "item_id": f"item-{artifact.artifact_id}",
                "miro_url": "https://miro.com/app/board/uXjVGixS6vQ=/",
                "execution_status": "created",
                "updated_at": updated_at,
            }
        )
    return {
        "run_status": "complete",
        "executed_at": updated_at,
        "items": items,
    }


if __name__ == "__main__":
    unittest.main()
