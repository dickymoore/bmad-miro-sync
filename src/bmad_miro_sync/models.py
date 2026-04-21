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
    phase_zone: str
    workstream: str
    collaboration_intent: str
    relative_path: str
    content: str
    sha256: str
    source_type: str = "file"
    heading_level: int = 0
    parent_artifact_id: str | None = None
    section_path: tuple[str, ...] = ()
    section_title_path: tuple[str, ...] = ()
    section_slug: str = ""
    section_sibling_index: int = 1
    lineage_key: str = ""
    lineage_status: str = "new"
    previous_artifact_id: str | None = None
    previous_parent_artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["section_path"] = list(self.section_path)
        payload["section_title_path"] = list(self.section_title_path)
        return payload


@dataclass(slots=True)
class DiscoverySelection:
    artifact_class: str
    phase: str
    phase_zone: str
    workstream: str
    collaboration_intent: str
    relative_path: str
    source_path: str
    source_variant: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoverySkippedCandidate:
    artifact_class: str
    phase: str
    phase_zone: str
    workstream: str
    collaboration_intent: str
    relative_path: str
    source_path: str
    source_variant: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoveryMissingArtifactClass:
    artifact_class: str
    search_paths: list[str]
    warning: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoveryReport:
    selected: list[DiscoverySelection] = field(default_factory=list)
    skipped: list[DiscoverySkippedCandidate] = field(default_factory=list)
    missing_required: list[DiscoveryMissingArtifactClass] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": [item.to_dict() for item in self.selected],
            "skipped": [item.to_dict() for item in self.skipped],
            "missing_required": [item.to_dict() for item in self.missing_required],
        }


@dataclass(slots=True)
class ArtifactDiscoveryResult:
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    selected: list[DiscoverySelection] = field(default_factory=list)
    skipped: list[DiscoverySkippedCandidate] = field(default_factory=list)
    missing_required: list[DiscoveryMissingArtifactClass] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_report(self) -> DiscoveryReport:
        return DiscoveryReport(
            selected=list(self.selected),
            skipped=list(self.skipped),
            missing_required=list(self.missing_required),
        )


@dataclass(slots=True)
class DeterministicOrder:
    zone_rank: int = 0
    workstream_rank: int = 0
    object_rank: int = 0
    artifact_rank: int = 0
    section_rank: int = 0


@dataclass(slots=True)
class ObjectStrategyDecision:
    object_family: str
    preferred_item_type: str
    resolved_item_type: str
    degraded: bool = False
    fallback_reason: str | None = None
    degraded_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PublishOperation:
    op_id: str
    action: str
    item_type: str
    title: str
    phase: str
    phase_zone: str
    workstream: str
    collaboration_intent: str
    artifact_id: str
    source_artifact_id: str
    target_key: str
    container_target_key: str | None = None
    content: str | None = None
    columns: list[dict[str, Any]] | None = None
    rows: list[dict[str, Any]] | None = None
    existing_item: dict[str, Any] | None = None
    layout_policy: str | None = None
    layout_snapshot: dict[str, Any] | None = None
    object_family: str | None = None
    preferred_item_type: str | None = None
    resolved_item_type: str | None = None
    degraded: bool = False
    fallback_reason: str | None = None
    degraded_warning: str | None = None
    status: str = "pending"
    lifecycle_state: str = "active"
    removal_policy: str | None = None
    heading_level: int = 0
    parent_artifact_id: str | None = None
    deterministic_order: DeterministicOrder = field(default_factory=DeterministicOrder)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SyncPlan:
    board_url: str
    project_root: str
    config_path: str
    manifest_path: str
    operations: list[PublishOperation] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    discovery: DiscoveryReport = field(default_factory=DiscoveryReport)
    object_strategies: list[ObjectStrategyDecision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_url": self.board_url,
            "project_root": self.project_root,
            "config_path": self.config_path,
            "manifest_path": self.manifest_path,
            "warnings": list(self.warnings),
            "discovery": self.discovery.to_dict(),
            "object_strategies": [strategy.to_dict() for strategy in self.object_strategies],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "operations": [operation.to_dict() for operation in self.operations],
        }
