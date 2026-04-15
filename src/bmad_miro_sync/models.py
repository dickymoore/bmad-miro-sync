from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ArtifactRecord:
    artifact_id: str
    source_artifact_id: str
    kind: str
    title: str
    phase: str
    relative_path: str
    content: str
    sha256: str
    source_type: str = "file"
    heading_level: int = 0
    parent_artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PublishOperation:
    op_id: str
    action: str
    item_type: str
    title: str
    phase: str
    artifact_id: str
    source_artifact_id: str
    target_key: str
    content: str | None = None
    columns: list[dict[str, Any]] | None = None
    rows: list[dict[str, Any]] | None = None
    existing_item: dict[str, Any] | None = None
    status: str = "pending"
    heading_level: int = 0
    parent_artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SyncPlan:
    board_url: str
    project_root: str
    config_path: str
    operations: list[PublishOperation] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_url": self.board_url,
            "project_root": self.project_root,
            "config_path": self.config_path,
            "warnings": list(self.warnings),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "operations": [operation.to_dict() for operation in self.operations],
        }
