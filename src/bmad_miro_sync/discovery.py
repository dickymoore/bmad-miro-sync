from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .classifier import classify_artifact, title_from_path
from .markdown import split_markdown_sections
from .models import ArtifactRecord


def discover_artifacts(project_root: str | Path, source_root: str) -> list[ArtifactRecord]:
    root = Path(project_root)
    source = root / source_root
    if not source.exists():
        return []

    artifacts: list[ArtifactRecord] = []
    for path in sorted(source.rglob("*.md")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8")
        kind, phase = classify_artifact(relative_path)
        file_title = title_from_path(relative_path, content)
        sections = split_markdown_sections(content)
        if not sections:
            continue
        slug_to_id = {
            section.slug: f"{relative_path}#{section.slug}"
            for section in sections
        }
        for section in sections:
            section_title = f"{file_title} / {section.title}"
            artifacts.append(
                ArtifactRecord(
                    artifact_id=slug_to_id[section.slug],
                    source_artifact_id=relative_path,
                    kind=kind,
                    title=section_title,
                    phase=phase,
                    relative_path=relative_path,
                    content=section.content,
                    sha256=sha256(section.content.encode("utf-8")).hexdigest(),
                    source_type="section",
                    heading_level=section.heading_level,
                    parent_artifact_id=slug_to_id.get(section.parent_slug) if section.parent_slug else None,
                )
            )
    return artifacts
