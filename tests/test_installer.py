from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.installer import install_project


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
            self.assertNotIn("## BMad Miro Sync Policy", skill.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
