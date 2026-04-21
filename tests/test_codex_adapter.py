from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.adapters.codex import export_bundle
from bmad_miro_sync.workflow import DEFAULT_COLLABORATION_REPORT_PATH


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


class CodexAdapterTests(unittest.TestCase):
    def test_export_bundle_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")

            output_dir = export_bundle(root, root / ".bmad-miro.toml", root / ".bmad-miro-sync/run")

            self.assertTrue((output_dir / "plan.json").exists())
            self.assertTrue((output_dir / "publish-bundle.json").exists())
            self.assertTrue((output_dir / "codex-bundle.json").exists())
            self.assertTrue((output_dir / "instructions.md").exists())
            self.assertTrue((output_dir / "results.template.json").exists())
            bundle = json.loads((output_dir / "publish-bundle.json").read_text(encoding="utf-8"))
            codex_alias = json.loads((output_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            plan_payload = json.loads((output_dir / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle, codex_alias)
            self.assertEqual(bundle["manifest_path"], ".bmad-miro-sync/state.json")
            self.assertEqual(plan_payload["manifest_path"], ".bmad-miro-sync/state.json")
            self.assertEqual(bundle["artifacts"][0]["artifact_id"], "_bmad-output/planning-artifacts/prd.md#prd")
            self.assertEqual(bundle["artifacts"][0]["source_artifact_id"], "_bmad-output/planning-artifacts/prd.md")
            self.assertIn("discovery", bundle)
            self.assertEqual(bundle["discovery"]["selected"][0]["relative_path"], "_bmad-output/planning-artifacts/prd.md")
            self.assertEqual(bundle["artifacts"][0]["section_path"], ["prd"])
            self.assertEqual(bundle["artifacts"][0]["phase_zone"], "planning")
            self.assertEqual(bundle["artifacts"][0]["workstream"], "product")
            self.assertEqual(bundle["artifacts"][0]["collaboration_intent"], "anchor")
            self.assertEqual(bundle["artifacts"][0]["lineage_status"], "new")
            self.assertIsNone(bundle["artifacts"][0]["previous_artifact_id"])
            self.assertEqual(bundle["operations"][0]["item_type"], "zone")
            self.assertEqual(bundle["operations"][0]["target_key"], "zone:planning")
            self.assertIn("layout_policy", bundle["operations"][0])
            self.assertIn("layout_snapshot", bundle["operations"][0])
            self.assertIn("object_strategies", bundle)
            self.assertEqual(bundle["object_strategies"][0]["object_family"], "phase_zone_scaffolding")
            self.assertIn("preferred_item_type", bundle["operations"][0])
            self.assertIn("resolved_item_type", bundle["operations"][0])
            instructions = (output_dir / "instructions.md").read_text(encoding="utf-8")
            self.assertIn("phase_zone", instructions)
            self.assertIn("deterministic_order", instructions)
            self.assertIn("layout_policy", instructions)
            self.assertIn("layout_snapshot", instructions)
            self.assertIn("live parent and grouping context", instructions)
            self.assertIn("preferred_item_type", instructions)
            self.assertIn("object_strategies", instructions)
            results_template = json.loads((output_dir / "results.template.json").read_text(encoding="utf-8"))
            self.assertEqual(results_template["run_status"], "<complete|partial|failed>")
            self.assertEqual(results_template["executed_at"], "<ISO-8601 timestamp>")
            self.assertEqual(results_template["object_strategies"][0]["resolved_item_type"], "<resolved item type>")
            template_item = results_template["items"][0]
            self.assertEqual(template_item["op_id"], "<operation id>")
            self.assertEqual(template_item["phase_zone"], "<operation phase zone>")
            self.assertEqual(template_item["section_path"], ["<stable section path segments>"])
            self.assertEqual(template_item["lineage_status"], "<new|changed|unchanged>")
            self.assertEqual(template_item["lifecycle_state"], "<active|archived|removed>")
            self.assertEqual(template_item["execution_status"], "<created|updated|unchanged|archived|removed|failed>")
            self.assertEqual(template_item["layout_policy"], "<auto|preserve>")
            self.assertEqual(template_item["layout_snapshot"]["parent_item_id"], "<container item id or null>")
            self.assertEqual(template_item["preferred_item_type"], "<preferred item type>")
            self.assertEqual(template_item["resolved_item_type"], "<resolved item type>")
            self.assertEqual(template_item["degraded"], "<true|false>")
            self.assertIn("previous_artifact_id", template_item)
            self.assertIn("null for zone/workstream", template_item["artifact_sha256"])
            self.assertIn("archived", instructions)
            self.assertIn("removed", instructions)

    def test_export_bundle_matches_collaboration_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync" / "run"
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")

            output_dir = export_bundle(root, root / ".bmad-miro.toml", runtime_dir)

            self.assertEqual(output_dir, runtime_dir.resolve())
            self.assertTrue((output_dir / "plan.json").is_file())
            self.assertTrue((output_dir / "publish-bundle.json").is_file())
            self.assertTrue((output_dir / "codex-bundle.json").is_file())
            self.assertTrue((output_dir / "instructions.md").is_file())
            self.assertTrue((output_dir / "results.template.json").is_file())
            self.assertEqual(DEFAULT_COLLABORATION_REPORT_PATH, ".bmad-miro-sync/run/collaboration-run.json")


if __name__ == "__main__":
    unittest.main()
