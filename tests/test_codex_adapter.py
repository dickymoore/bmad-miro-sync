from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.adapters.codex import export_bundle


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
            self.assertTrue((output_dir / "codex-bundle.json").exists())
            self.assertTrue((output_dir / "instructions.md").exists())
            self.assertTrue((output_dir / "results.template.json").exists())


if __name__ == "__main__":
    unittest.main()
