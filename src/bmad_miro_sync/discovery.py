from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .classifier import classify_artifact, title_from_path
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
        digest = sha256(content.encode("utf-8")).hexdigest()
        artifacts.append(
            ArtifactRecord(
                artifact_id=relative_path,
                kind=kind,
                title=title_from_path(relative_path, content),
                phase=phase,
                relative_path=relative_path,
                content=content,
                sha256=digest,
            )
        )
    return artifacts
