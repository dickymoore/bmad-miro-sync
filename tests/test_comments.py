from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from bmad_miro_sync.comments import DEFAULT_COMMENTS_OUTPUT, ingest_comments, normalize_comments
from bmad_miro_sync.manifest import SyncManifest

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")


class CommentIngestTests(unittest.TestCase):
    def test_normalize_comments_groups_by_artifact_section_and_topic(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Please expand the acceptance criteria.",
                    "published_object_id": "doc-123",
                    "published_object_type": "doc",
                    "published_object_reference": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                },
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "John Smith",
                    "created_at": "2026-04-15T11:05:00Z",
                    "body": "Add one negative-path example.",
                },
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "author": "Pat Lee",
                    "created_at": "2026-04-15T11:10:00Z",
                    "body": "Looks ready for delivery.",
                }
            ]
        }

        normalized = normalize_comments(manifest, payload)

        self.assertEqual(len(normalized.resolved), 3)
        self.assertEqual(len(normalized.unresolved), 0)
        self.assertEqual(normalized.resolved[0].source_artifact_id, "_bmad-output/planning-artifacts/prd.md")
        self.assertEqual(normalized.resolved[0].section_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
        self.assertEqual(normalized.resolved[0].topic, "Acceptance criteria")
        self.assertEqual(normalized.resolved[0].published_object_id, "doc-123")
        self.assertEqual(normalized.resolved[1].topic, "Acceptance criteria")
        self.assertEqual(normalized.resolved[2].topic, "General feedback")

    def test_ingest_comments_writes_grouped_review_artifact(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Please expand the acceptance criteria.",
                },
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "John Smith",
                    "created_at": "2026-04-15T11:05:00Z",
                    "body": "Add one negative-path example.",
                },
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "author": "Pat Lee",
                    "created_at": "2026-04-15T11:10:00Z",
                    "body": "Looks ready for delivery.",
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            ingest_comments(manifest, payload, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("## _bmad-output/planning-artifacts/prd.md", content)
            self.assertIn("### PRD / Goals", content)
            self.assertEqual(content.count("#### Acceptance criteria"), 1)
            self.assertIn("#### General feedback", content)
            self.assertIn("Published object: `doc-123`", content)
            self.assertIn("Section artifact: `_bmad-output/planning-artifacts/prd.md#prd/goals`", content)
            self.assertIn("Jane Doe on 2026-04-15T11:00:00Z", content)
            self.assertIn("John Smith on 2026-04-15T11:05:00Z", content)

    def test_ingest_comments_preserves_backward_compatible_payloads(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "section_title": "PRD / Goals",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Legacy payload should still render cleanly.",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            ]
        }

        normalized = normalize_comments(manifest, payload)

        self.assertEqual(len(normalized.resolved), 1)
        self.assertEqual(normalized.resolved[0].topic, "General feedback")
        self.assertEqual(normalized.resolved[0].source_artifact_id, "_bmad-output/planning-artifacts/prd.md")
        self.assertEqual(normalized.resolved[0].section_title, "PRD / Goals")
        self.assertEqual(normalized.resolved[0].published_object_id, "doc-123")

    def test_normalize_comments_uses_manifest_source_artifact_after_resolution(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "source_artifact_id": "_bmad-output/planning-artifacts/architecture.md",
                    "author": "Jane Doe",
                    "body": "Do not group this under the wrong file.",
                }
            ]
        }

        normalized = normalize_comments(manifest, payload)

        self.assertEqual(len(normalized.resolved), 1)
        self.assertEqual(
            normalized.resolved[0].source_artifact_id,
            "_bmad-output/planning-artifacts/prd.md",
        )

    def test_ingest_comments_resolves_legacy_section_reference_from_source_and_title(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "section_slug": "goals",
                    "item_id": "doc-123",
                    "item_type": "doc",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#goals",
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "section_title": "Goals",
                    "author": "Jane Doe",
                    "body": "Legacy section ids should still resolve.",
                }
            ]
        }

        normalized = normalize_comments(manifest, payload)

        self.assertEqual(len(normalized.resolved), 1)
        self.assertEqual(len(normalized.unresolved), 0)
        self.assertEqual(normalized.resolved[0].artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
        self.assertEqual(normalized.resolved[0].section_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
        self.assertEqual(normalized.resolved[0].section_title, "PRD / Goals")

    def test_ingest_comments_reports_unresolved_inputs(self) -> None:
        manifest = SyncManifest(version=3, items={})
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Please expand the acceptance criteria.",
                    "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            ingest_comments(manifest, payload, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("## Unresolved Inputs", content)
            self.assertIn("Incoming artifact reference: `_bmad-output/planning-artifacts/prd.md#prd/goals`", content)
            self.assertIn("Incoming source artifact: `_bmad-output/planning-artifacts/prd.md`", content)
            self.assertIn("Incoming section id: `_bmad-output/planning-artifacts/prd.md#prd/goals`", content)
            self.assertIn("Topic: `General feedback`", content)
            self.assertIn("Jane Doe on 2026-04-15T11:00:00Z", content)
            self.assertNotIn("## _bmad-output/planning-artifacts/prd.md", content)

    def test_normalize_comments_treats_non_list_payload_as_empty(self) -> None:
        manifest = SyncManifest(version=3, items={})

        normalized = normalize_comments(manifest, {"comments": None})

        self.assertEqual(normalized.resolved, [])
        self.assertEqual(normalized.unresolved, [])

    def test_ingest_comments_rejects_structurally_empty_comment_object(self) -> None:
        manifest = SyncManifest(version=3, items={})

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            with self.assertRaisesRegex(
                ValueError,
                "Comment entry at comments\\[0\\] is empty.",
            ):
                ingest_comments(manifest, {"comments": [{}]}, output_path=output_path)
            self.assertFalse(output_path.exists())

    def test_normalize_comments_treats_non_mapping_payload_as_empty(self) -> None:
        manifest = SyncManifest(version=3, items={})

        normalized = normalize_comments(manifest, [])  # type: ignore[arg-type]

        self.assertEqual(normalized.resolved, [])
        self.assertEqual(normalized.unresolved, [])

    def test_normalize_comments_prefers_section_id_when_artifact_id_is_unresolved(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#legacy-goals",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "section_title": "PRD / Goals",
                    "author": "Jane Doe",
                    "body": "Use the canonical section id when available.",
                }
            ]
        }

        normalized = normalize_comments(manifest, payload)

        self.assertEqual(len(normalized.resolved), 1)
        self.assertEqual(len(normalized.unresolved), 0)
        self.assertEqual(normalized.resolved[0].artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
        self.assertEqual(normalized.resolved[0].section_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")

    def test_normalize_comments_rejects_conflicting_artifact_and_section_ids(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD",
                },
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                },
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd",
                    "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "section_title": "PRD / Goals",
                    "author": "Jane Doe",
                    "body": "Do not merge this into the parent section.",
                }
            ]
        }

        normalized = normalize_comments(manifest, payload)

        self.assertEqual(len(normalized.resolved), 0)
        self.assertEqual(len(normalized.unresolved), 1)
        self.assertEqual(
            normalized.unresolved[0].incoming_artifact_reference,
            "_bmad-output/planning-artifacts/prd.md#prd",
        )
        self.assertEqual(
            normalized.unresolved[0].section_id,
            "_bmad-output/planning-artifacts/prd.md#prd/goals",
        )
        self.assertIn("resolved to different manifest entries", normalized.unresolved[0].reason)

    def test_ingest_comments_sanitizes_topic_heading_text(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "### Acceptance criteria\nFollow-up",
                    "author": "Jane Doe",
                    "body": "Please expand the acceptance criteria.",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            ingest_comments(manifest, payload, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("#### Acceptance criteria Follow-up", content)
            self.assertNotIn("#### ### Acceptance criteria", content)

    def test_ingest_comments_preserves_multiline_bodies_in_markdown_lists(self) -> None:
        manifest = SyncManifest(
            version=3,
            items={
                "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "author": "Jane Doe",
                    "body": "First line\nSecond line",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            ingest_comments(manifest, payload, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("- Jane Doe: First line\n  Second line", content)
            self.assertIn("  Object reference: `artifact:_bmad-output/planning-artifacts/prd.md#prd/goals`", content)

    def test_ingest_comments_preserves_multiline_unresolved_bodies(self) -> None:
        manifest = SyncManifest(version=3, items={})
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "topic": "Acceptance criteria",
                    "author": "Jane Doe",
                    "body": "First line\nSecond line",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            ingest_comments(manifest, payload, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("- Jane Doe: First line\n  Second line", content)
            self.assertIn("  Topic: `Acceptance criteria`", content)

    def test_cli_ingest_comments_writes_default_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                'board_url = "https://miro.com/app/board/uXjVGixS6vQ=/"\n',
                encoding="utf-8",
            )
            (root / ".bmad-miro-sync/state.json").write_text(
                json.dumps(
                    {
                        "version": 2,
                        "items": {
                            "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "title": "PRD / Goals",
                                "item_id": "doc-123",
                                "item_type": "doc",
                                "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            comments_path = root / ".bmad-miro-sync/run/comments.json"
            comments_path.parent.mkdir(parents=True, exist_ok=True)
            comments_path.write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "topic": "Acceptance criteria",
                                "author": "Jane Doe",
                                "body": "Looks good.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "python3",
                    "-m",
                    "bmad_miro_sync",
                    "ingest-comments",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--comments",
                    str(comments_path),
                ],
                check=True,
                capture_output=True,
                env={**os.environ, "PYTHONPATH": REPO_SRC},
                text=True,
                cwd=root,
            )

            payload = json.loads(completed.stdout)
            output_path = Path(payload["output_path"])
            self.assertEqual(output_path, root / DEFAULT_COMMENTS_OUTPUT)
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("#### Acceptance criteria", content)
            self.assertIn("Published object: `doc-123`", content)


if __name__ == "__main__":
    unittest.main()
