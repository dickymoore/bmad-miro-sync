from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .manifest import SyncManifest


DEFAULT_COMMENTS_OUTPUT = "_bmad-output/review-artifacts/miro-comments.md"


def ingest_comments(
    manifest: SyncManifest,
    comments_payload: dict[str, Any],
    *,
    output_path: str | Path,
) -> Path:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    for entry in comments_payload.get("comments", []):
        artifact_id = entry.get("artifact_id")
        if not artifact_id:
            continue
        manifest_entry = manifest.items.get(artifact_id, {})
        source_artifact_id = entry.get("source_artifact_id") or manifest_entry.get("source_artifact_id") or artifact_id
        section_title = entry.get("section_title") or manifest_entry.get("title") or artifact_id
        grouped[source_artifact_id][section_title].append(
            {
                "author": entry.get("author", "Unknown"),
                "created_at": entry.get("created_at", ""),
                "body": (entry.get("body") or "").strip(),
                "miro_url": entry.get("miro_url") or manifest_entry.get("miro_url") or "",
            }
        )

    lines = ["# Miro Review Feedback", ""]
    if not grouped:
        lines.extend(
            [
                "_No comments were ingested from Miro._",
                "",
            ]
        )
    else:
        for source_artifact_id in sorted(grouped):
            lines.append(f"## {source_artifact_id}")
            lines.append("")
            for section_title in sorted(grouped[source_artifact_id]):
                lines.append(f"### {section_title}")
                lines.append("")
                for comment in sorted(
                    grouped[source_artifact_id][section_title],
                    key=lambda item: (item["created_at"], item["author"], item["body"]),
                ):
                    metadata = f"{comment['author']}"
                    if comment["created_at"]:
                        metadata += f" on {comment['created_at']}"
                    if comment["miro_url"]:
                        metadata += f" ({comment['miro_url']})"
                    lines.append(f"- {metadata}: {comment['body']}")
                lines.append("")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target
