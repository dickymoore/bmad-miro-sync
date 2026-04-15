from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from bmad_miro_sync.comments import DEFAULT_COMMENTS_OUTPUT, ingest_comments
from bmad_miro_sync.manifest import SyncManifest

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")


class CommentIngestTests(unittest.TestCase):
    def test_ingest_comments_writes_grouped_review_artifact(self) -> None:
        manifest = SyncManifest(
            version=2,
            items={
                "_bmad-output/planning-artifacts/prd.md#goals": {
                    "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                    "title": "PRD / Goals",
                    "miro_url": "https://miro.com/app/board/example/",
                }
            },
        )
        payload = {
            "comments": [
                {
                    "artifact_id": "_bmad-output/planning-artifacts/prd.md#goals",
                    "author": "Jane Doe",
                    "created_at": "2026-04-15T11:00:00Z",
                    "body": "Please expand the acceptance criteria.",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / DEFAULT_COMMENTS_OUTPUT
            ingest_comments(manifest, payload, output_path=output_path)
            content = output_path.read_text(encoding="utf-8")

            self.assertIn("## _bmad-output/planning-artifacts/prd.md", content)
            self.assertIn("### PRD / Goals", content)
            self.assertIn("Jane Doe on 2026-04-15T11:00:00Z", content)

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
                            "_bmad-output/planning-artifacts/prd.md#goals": {
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "title": "PRD / Goals",
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
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#goals",
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


if __name__ == "__main__":
    unittest.main()
