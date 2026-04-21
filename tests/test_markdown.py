from __future__ import annotations

import unittest

from bmad_miro_sync.markdown import split_markdown_sections


class MarkdownSectionTests(unittest.TestCase):
    def test_split_markdown_sections_promotes_nested_headings_into_tree(self) -> None:
        sections = split_markdown_sections(
            "# PRD\n\nIntro\n\n## Goals\n\nGoal body\n\n### Metrics\n\nMeasure it\n\n## Risks\n\nRisk body\n"
        )

        self.assertEqual([section.slug for section in sections], ["prd", "prd/goals", "prd/goals/metrics", "prd/risks"])
        self.assertEqual(sections[0].content, "# PRD\n\nIntro")
        self.assertEqual(sections[1].content, "## Goals\n\nGoal body")
        self.assertEqual(sections[2].parent_slug, "prd/goals")
        self.assertEqual(sections[2].title_path, ("PRD", "Goals", "Metrics"))

    def test_split_markdown_sections_disambiguates_duplicate_siblings_by_parent(self) -> None:
        sections = split_markdown_sections(
            "# Root\n\n## Notes\n\nAlpha\n\n## Notes\n\nBeta\n\n### Notes\n\nNested\n"
        )

        self.assertEqual([section.slug for section in sections], ["root", "root/notes", "root/notes-2", "root/notes-2/notes"])
        self.assertEqual(sections[1].sibling_index, 1)
        self.assertEqual(sections[2].sibling_index, 2)
        self.assertEqual(sections[3].parent_slug, "root/notes-2")

    def test_split_markdown_sections_preserves_deterministic_overview_ids(self) -> None:
        markdown = "Preamble only\n\nStill overview."

        first = split_markdown_sections(markdown)
        second = split_markdown_sections(markdown)

        self.assertEqual([section.slug for section in first], ["overview"])
        self.assertEqual(first[0].lineage_key, second[0].lineage_key)

    def test_split_markdown_sections_uses_overview_for_preamble_before_headings(self) -> None:
        sections = split_markdown_sections("Intro\n\n# Heading\n\nBody\n")

        self.assertEqual([section.slug for section in sections], ["overview", "heading"])
        self.assertEqual(sections[0].content, "Intro")
        self.assertEqual(sections[1].parent_slug, None)

    def test_split_markdown_sections_disambiguates_real_overview_heading_after_preamble(self) -> None:
        sections = split_markdown_sections("Intro\n\n# Overview\n\nBody\n")

        self.assertEqual([section.slug for section in sections], ["overview", "overview-2"])
        self.assertEqual(len({section.slug for section in sections}), 2)
        self.assertEqual(sections[1].path, ("overview-2",))


if __name__ == "__main__":
    unittest.main()
