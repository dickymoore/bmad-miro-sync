from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.installer import install_project
from bmad_miro_sync.templates import SYNC_POLICY_BODY


class InstallerTests(unittest.TestCase):
    def test_install_writes_project_files_and_patches_skills_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".agents/skills/bmad-create-prd").mkdir(parents=True)
            (root / ".agents/skills/bmad-create-prd/SKILL.md").write_text(
                "---\nname: bmad-create-prd\ndescription: test\n---\n\nFollow the instructions.\n",
                encoding="utf-8",
            )
            (root / ".gitignore").write_text(".codex/\n", encoding="utf-8")

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
            )

            self.assertTrue((root / ".bmad-miro.toml").exists())
            self.assertTrue((root / "docs/miro-sync.md").exists())
            self.assertTrue((root / ".agents/skills/bmad-miro-auto-sync/SKILL.md").exists())
            self.assertTrue((root / ".agents/skills/bmad-ingest-miro-comments/SKILL.md").exists())
            self.assertEqual(result.backup_files, [])
            auto_sync = (root / ".agents/skills/bmad-miro-auto-sync/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("create_phase_frames = false", auto_sync)
            self.assertIn("do not ask the user", auto_sync)
            self.assertIn(root / ".agents/skills/bmad-create-prd/SKILL.md", result.patched_skills)
            patched = (root / ".agents/skills/bmad-create-prd/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## BMad Miro Sync Policy", patched)

    def test_install_can_skip_bmad_skill_patching(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".agents/skills/bmad-create-prd").mkdir(parents=True)
            skill = root / ".agents/skills/bmad-create-prd/SKILL.md"
            skill.write_text(
                "---\nname: bmad-create-prd\ndescription: test\n---\n\nFollow the instructions.\n",
                encoding="utf-8",
            )

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
                patch_bmad_skills=False,
            )

            self.assertEqual(result.patched_skills, [])
            self.assertEqual(result.backup_files, [])
            self.assertNotIn("## BMad Miro Sync Policy", skill.read_text(encoding="utf-8"))

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

    def test_install_does_not_duplicate_equivalent_project_sync_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".agents/skills/bmad-create-prd").mkdir(parents=True)
            skill = root / ".agents/skills/bmad-create-prd/SKILL.md"
            skill.write_text(
                "---\nname: bmad-create-prd\ndescription: test\n---\n\n"
                "## FluidScan Sync Policy\n\n"
                f"{SYNC_POLICY_BODY}\n\n"
                "Follow the instructions.\n",
                encoding="utf-8",
            )

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
            )

            self.assertEqual(result.patched_skills, [])
            updated = skill.read_text(encoding="utf-8")
            self.assertIn("## FluidScan Sync Policy", updated)
            self.assertNotIn("## BMad Miro Sync Policy", updated)
            self.assertEqual(updated.count(SYNC_POLICY_BODY), 1)

    def test_install_dedupes_existing_matching_sync_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".agents/skills/bmad-create-prd").mkdir(parents=True)
            skill = root / ".agents/skills/bmad-create-prd/SKILL.md"
            skill.write_text(
                "---\nname: bmad-create-prd\ndescription: test\n---\n\n"
                "## BMad Miro Sync Policy\n\n"
                f"{SYNC_POLICY_BODY}\n\n"
                "## FluidScan Sync Policy\n\n"
                f"{SYNC_POLICY_BODY}\n\n"
                "Follow the instructions.\n",
                encoding="utf-8",
            )

            result = install_project(
                root,
                "https://miro.com/app/board/uXjVGixS6vQ=/",
                sync_src="/tmp/bmad-miro-sync/src",
            )

            self.assertIn(skill, result.patched_skills)
            updated = skill.read_text(encoding="utf-8")
            self.assertEqual(updated.count(SYNC_POLICY_BODY), 1)


if __name__ == "__main__":
    unittest.main()
