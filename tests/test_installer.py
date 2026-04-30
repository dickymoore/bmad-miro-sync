from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.installer import install_project
from bmad_miro_sync.templates import render_config


class InstallerTests(unittest.TestCase):
    def test_example_config_matches_generated_install_config(self) -> None:
        example_path = Path(__file__).resolve().parents[1] / ".bmad-miro.example.toml"

        self.assertEqual(
            example_path.read_text(encoding="utf-8"),
            render_config("https://miro.com/app/board/uXjVGixS6vQ=/"),
        )

    def test_install_writes_project_files_and_bmad_customizations_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".gitignore").write_text(".codex/\n", encoding="utf-8")

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
            )

            self.assertTrue((root / ".bmad-miro.toml").exists())
            self.assertTrue((root / "docs/miro-sync.md").exists())
            self.assertTrue((root / ".agents/skills/bmad-miro-sync/SKILL.md").exists())
            self.assertTrue((root / ".agents/skills/bmad-miro-ingest/SKILL.md").exists())
            self.assertTrue((root / ".agents/skills/bmad-miro-collaboration/SKILL.md").exists())
            self.assertEqual(result.backup_files, [])
            config_text = (root / ".bmad-miro.toml").read_text(encoding="utf-8")
            self.assertIn("#[discovery]", config_text)
            self.assertIn(
                '#source_paths = ["_bmad-output/planning-artifacts", "_bmad-output/implementation-artifacts", "_bmad-output/review-artifacts"]',
                config_text,
            )
            self.assertIn("#[object_strategies]", config_text)
            self.assertIn('[sync]\nremoved_item_policy = "archive"', config_text)
            gitignore_text = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".bmad-miro-sync/", gitignore_text)
            self.assertIn(".bmad-miro-auth.json", gitignore_text)
            auto_sync = (root / ".agents/skills/bmad-miro-sync/SKILL.md").read_text(encoding="utf-8")
            self.assertIn('[object_strategies].phase_zone = "workstream_anchor"', auto_sync)
            self.assertIn("do not ask the user", auto_sync)
            self.assertIn("complete the full publish pass in one run", auto_sync)
            self.assertIn("publish-direct", auto_sync)
            self.assertIn("MIRO_API_TOKEN", auto_sync)
            self.assertIn("Smaller runs may still complete through Codex Miro MCP alone", auto_sync)
            self.assertIn("create or confirm a Miro Developer team", auto_sync)
            self.assertIn("setup-miro-rest-auth", auto_sync)
            self.assertIn(".bmad-miro-auth.json", auto_sync)
            self.assertIn("Which BMAD outputs are up to date and which need syncing?", auto_sync)
            self.assertIn("source-status", auto_sync)
            self.assertIn("--changed-only", auto_sync)
            self.assertIn('--source "_bmad-output/planning-artifacts/prd.md"', auto_sync)
            self.assertIn("If Playwright MCP is available", auto_sync)
            self.assertNotIn("Only proceed with a partial results file", auto_sync)
            self.assertIn("name: bmad-miro-sync", auto_sync)
            comment_skill = (root / ".agents/skills/bmad-miro-ingest/SKILL.md").read_text(encoding="utf-8")
            self.assertIn('"section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals"', comment_skill)
            self.assertIn('"topic": "Acceptance criteria"', comment_skill)
            self.assertIn('"published_object_id": "doc-123"', comment_skill)
            self.assertIn('"published_object_reference": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals"', comment_skill)
            self.assertIn("name: bmad-miro-ingest", comment_skill)
            collaboration_skill = (root / ".agents/skills/bmad-miro-collaboration/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("name: bmad-miro-collaboration", collaboration_skill)
            self.assertIn("--stop-after publish", collaboration_skill)
            self.assertIn("--start-at apply-results", collaboration_skill)
            self.assertIn("workstream_anchor", collaboration_skill)
            self.assertIn("implementation-readiness.md", collaboration_skill)
            self.assertIn("requires a complete publish pass", collaboration_skill)
            self.assertIn("publish-direct", collaboration_skill)
            self.assertIn("Smaller runs may still complete through Codex Miro MCP alone", collaboration_skill)
            self.assertIn("setup-miro-rest-auth", collaboration_skill)
            self.assertEqual(result.patched_skills, [])
            customization = root / "_bmad/custom/bmad-create-prd.toml"
            self.assertIn(customization, result.bmad_customizations)
            customization_text = customization.read_text(encoding="utf-8")
            self.assertIn("[workflow]", customization_text)
            self.assertIn("bmad-miro-sync", customization_text)
            self.assertIn("bmad-miro-collaboration", customization_text)
            doc_text = (root / "docs/miro-sync.md").read_text(encoding="utf-8")
            self.assertIn("Run The Miro Collaboration Workflow", doc_text)
            self.assertIn("bmad-miro-collaboration", doc_text)
            self.assertIn("bmad-miro-sync", doc_text)
            self.assertIn("bmad-miro-ingest", doc_text)
            self.assertIn("_bmad/custom/", doc_text)
            self.assertIn("publish-direct", doc_text)
            self.assertIn("Playwright MCP", doc_text)
            self.assertIn("@playwright/mcp@latest", doc_text)
            self.assertIn("Smaller runs may still complete through Codex Miro MCP alone", doc_text)
            self.assertIn("create or confirm a Miro Developer team", doc_text)
            self.assertIn("setup-miro-rest-auth", doc_text)
            self.assertIn(".bmad-miro-auth.json", doc_text)
            self.assertIn("publish is one pass or blocked", doc_text)

    def test_install_removes_legacy_skill_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_paths = [
                root / ".agents/skills/bmad-miro-auto-sync/SKILL.md",
                root / ".agents/skills/bmad-ingest-miro-comments/SKILL.md",
                root / ".agents/skills/run-codex-collaboration-workflow/SKILL.md",
            ]
            for path in legacy_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("legacy\n", encoding="utf-8")

            install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
                patch_bmad_skills=False,
            )

            for path in legacy_paths:
                self.assertFalse(path.exists())
            self.assertTrue((root / ".agents/skills/bmad-miro-sync/SKILL.md").exists())

    def test_install_can_skip_bmad_skill_patching(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
                patch_bmad_skills=False,
            )

            self.assertEqual(result.bmad_customizations, [])
            self.assertEqual(result.patched_skills, [])
            self.assertEqual(result.backup_files, [])
            self.assertFalse((root / "_bmad/custom/bmad-create-prd.toml").exists())

    def test_install_backs_up_changed_config_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(
                'board_url = "https://miro.com/app/board/original=/"\nsource_root = "_bmad-output"\n',
                encoding="utf-8",
            )

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
                patch_bmad_skills=False,
            )

            self.assertEqual(len(result.backup_files), 1)
            backup_path = result.backup_files[0]
            self.assertTrue(backup_path.exists())
            self.assertEqual(
                backup_path.read_text(encoding="utf-8"),
                'board_url = "https://miro.com/app/board/original=/"\nsource_root = "_bmad-output"\n',
            )
            self.assertIn('uXjVGixS6vQ', config_path.read_text(encoding="utf-8"))

    def test_install_writes_bmad_team_override_without_needing_skill_patch_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
            )

            self.assertEqual(result.patched_skills, [])
            override = (root / "_bmad/custom/bmad-create-prd.toml").read_text(encoding="utf-8")
            self.assertIn("on_complete", override)
            self.assertIn("bmad-miro-sync", override)

    def test_install_overwrites_bmad_team_override_with_current_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            override_path = root / "_bmad/custom/bmad-create-prd.toml"
            override_path.parent.mkdir(parents=True, exist_ok=True)
            override_path.write_text("[workflow]\non_complete = \"old\"\n", encoding="utf-8")

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
            )

            self.assertIn(override_path, result.bmad_customizations)
            updated = override_path.read_text(encoding="utf-8")
            self.assertIn("bmad-miro-sync", updated)
            self.assertNotIn('on_complete = "old"', updated)


if __name__ == "__main__":
    unittest.main()
