from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.config import load_config
from bmad_miro_sync.structure_analysis import build_structure_analysis, summarize_report_metrics


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


class StructureAnalysisTests(unittest.TestCase):
    def test_analysis_reports_truncation_and_recommends_hybrid_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/product-brief.md").write_text(
                "# Product Brief\n\n"
                "## Product Intent\n\n"
                "FluidScan helps people finish worthwhile long-form reading. "
                "It is designed for people who save more articles than they complete. "
                "The first release focuses on calm interaction and visible progress.\n\n"
                "## Reader Context\n\n"
                "- Readers often arrive with a large backlog.\n"
                "- They need fast session restart.\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            report = build_structure_analysis(root, root / ".bmad-miro.toml", config)
            summary = summarize_report_metrics(report)

            self.assertEqual(report.source_count, 1)
            self.assertGreater(report.section_count, 0)
            self.assertGreater(report.publishable_section_count, 0)
            self.assertEqual(report.recommendation.recommended_model_id, "hybrid_heading_paragraph_list_cards")
            self.assertGreater(summary["paragraph_length_p50"], 0)
            self.assertTrue(any(alt.model_id == "heading_paragraph_list_item_cards" for alt in report.alternatives))


if __name__ == "__main__":
    unittest.main()
