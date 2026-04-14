from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.config import load_config
from bmad_miro_sync.manifest import apply_results, load_manifest, save_manifest
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
    def test_plan_discovers_docs_and_story_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts/stories").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/stories/1-1-first-story.md").write_text(
                "# First Story\n\nStory body\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            plan = build_sync_plan(root, root / ".bmad-miro.toml", config)

            actions = [operation.action for operation in plan.operations]
            self.assertIn("create_doc", actions)
            self.assertIn("create_table", actions)
            self.assertEqual(plan.operations[0].action, "ensure_frame")

    def test_existing_manifest_skips_unchanged_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\nBody\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            artifact = first_plan.artifacts[0]
            results = {
                "items": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "artifact_sha256": artifact.sha256,
                        "item_type": "doc",
                        "item_id": "123",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=123",
                        "title": artifact.title,
                        "target_key": f"doc:{artifact.artifact_id}",
                        "updated_at": "2026-04-14T15:00:00Z",
                    }
                ]
            }
            manifest = apply_results(load_manifest(root, config.manifest_path), results)
            save_manifest(root, config.manifest_path, manifest)

            second_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            doc_actions = [op.action for op in second_plan.operations if op.item_type == "doc"]
            self.assertEqual(doc_actions, ["skip"])

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
                            "artifact_id": "doc:test",
                            "artifact_sha256": "abc",
                            "item_type": "doc",
                            "item_id": "123",
                            "miro_url": "https://miro.com/x",
                            "title": "Test",
                            "target_key": "doc:test",
                            "updated_at": "2026-04-14T15:00:00Z",
                        }
                    ]
                },
            )
            path = save_manifest(root, config.manifest_path, updated)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("doc:test", payload["items"])


if __name__ == "__main__":
    unittest.main()
