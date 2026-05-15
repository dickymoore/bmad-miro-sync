from __future__ import annotations

import unittest

from bmad_miro_sync.content_blocks import extract_markdown_blocks


class ContentBlockTests(unittest.TestCase):
    def test_merges_label_only_paragraph_with_following_short_list(self) -> None:
        body = (
            "**Recommended Techniques:**\n\n"
            "- **First Principles Thinking:** Clarify what is essential.\n"
            "- **Morphological Analysis:** Explore the design space.\n"
            "- **Six Thinking Hats:** Stress-test the concepts.\n\n"
            "**AI Rationale:** This sequence moves from fundamentals to evaluation."
        )

        blocks = extract_markdown_blocks(body)

        self.assertEqual([block.block_type for block in blocks], ["compound"])
        self.assertIn("**Recommended Techniques:**", blocks[0].content)
        self.assertIn("Morphological Analysis", blocks[0].content)
        self.assertIn("AI Rationale", blocks[0].content)

    def test_does_not_merge_label_only_paragraph_into_repeated_labeled_series(self) -> None:
        body = (
            "**Key Ideas Generated:**\n\n"
            "**[Category #1]**: Sacred Center\n"
            "_Concept_: The center of the screen becomes the only active reading zone.\n\n"
            "**[Category #2]**: Vanishing Chrome\n"
            "_Concept_: The control strip withdraws visually unless summoned.\n\n"
            "**[Category #3]**: Anchor-Led Typography\n"
            "_Concept_: Typography is treated as gaze engineering.\n"
        )

        blocks = extract_markdown_blocks(body)

        self.assertEqual(blocks[0].block_type, "paragraph")
        self.assertEqual(blocks[0].content, "**Key Ideas Generated:**")
        self.assertEqual([block.block_type for block in blocks[1:]], ["paragraph", "paragraph", "paragraph"])
        self.assertIn("Sacred Center", blocks[1].content)

    def test_merges_label_with_short_paragraph_and_list_group(self) -> None:
        body = (
            "**Recommended Approach:**\n\n"
            "Use a calmer default reading layout so first-time reviewers can orient themselves quickly.\n\n"
            "- Keep the primary signal obvious.\n"
            "- Keep follow-on decisions easy to scan.\n\n"
            "This should remain readable without opening the repo.\n\n"
            "**Next Topic:**\n\n"
            "Treat advanced cases separately.\n"
        )

        blocks = extract_markdown_blocks(body)

        self.assertEqual([block.block_type for block in blocks], ["compound", "compound"])
        self.assertIn("Recommended Approach", blocks[0].content)
        self.assertIn("Keep the primary signal obvious", blocks[0].content)
        self.assertIn("This should remain readable", blocks[0].content)
        self.assertIn("Next Topic", blocks[1].content)


if __name__ == "__main__":
    unittest.main()
