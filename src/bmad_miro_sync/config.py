from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True, frozen=True)
class ObjectStrategyConfig:
    phase_zone: str = "zone"
    story_summary: str = "table"


@dataclass(slots=True)
class SyncConfig:
    board_url: str
    source_root: str = "_bmad-output"
    source_paths: tuple[str, ...] = ("_bmad-output",)
    required_artifact_classes: tuple[str, ...] = ()
    manifest_path: str = ".bmad-miro-sync/state.json"
    object_strategies: ObjectStrategyConfig = ObjectStrategyConfig()
    create_phase_frames: bool = True
    publish_analysis: bool = True
    publish_planning: bool = True
    publish_solutioning: bool = True
    publish_implementation: bool = True
    publish_stories_table: bool = True
    removed_item_policy: str = "archive"


def load_config(config_path: str | Path, *, project_root: str | Path | None = None) -> SyncConfig:
    path = Path(config_path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    discovery = data.get("discovery", {})
    layout = data.get("layout", {})
    publish = data.get("publish", {})
    object_strategies = data.get("object_strategies", {})
    sync = data.get("sync", {})
    board_url = data["board_url"]
    source_root = data.get("source_root", "_bmad-output")
    configured_source_paths = discovery.get("source_paths")
    source_paths = _normalize_source_paths(configured_source_paths, default=source_root)
    required_artifact_classes = _normalize_string_list(discovery.get("required_artifact_classes"))
    resolved_strategies = ObjectStrategyConfig(
        phase_zone=_normalize_phase_zone_strategy(
            object_strategies.get("phase_zone"),
            default="zone" if layout.get("create_phase_frames", True) else "workstream_anchor",
        ),
        story_summary=_normalize_story_summary_strategy(
            object_strategies.get("story_summary"),
            default="table" if publish.get("stories_table", True) else "doc",
        ),
    )
    config = SyncConfig(
        board_url=board_url,
        source_root=source_root,
        source_paths=source_paths,
        required_artifact_classes=required_artifact_classes,
        manifest_path=data.get("manifest_path", ".bmad-miro-sync/state.json"),
        object_strategies=resolved_strategies,
        create_phase_frames=resolved_strategies.phase_zone == "zone",
        publish_analysis=publish.get("analysis", True),
        publish_planning=publish.get("planning", True),
        publish_solutioning=publish.get("solutioning", True),
        publish_implementation=publish.get("implementation", True),
        publish_stories_table=resolved_strategies.story_summary == "table",
        removed_item_policy=_normalize_removed_item_policy(sync.get("removed_item_policy", "archive")),
    )
    if project_root is not None:
        _validate_repo_local_config_paths(config, project_root=project_root)
    return config


def _normalize_source_paths(value: object, *, default: str) -> tuple[str, ...]:
    values = _normalize_string_list(value)
    if not values:
        return (default,)
    return values


def _normalize_string_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        normalized = value.strip()
        return (normalized,) if normalized else ()
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized and normalized not in items:
                items.append(normalized)
        return tuple(items)
    return ()


def _normalize_removed_item_policy(value: object) -> str:
    if not isinstance(value, str):
        return "archive"
    normalized = value.strip().lower()
    if normalized in {"archive", "remove"}:
        return normalized
    raise ValueError("sync.removed_item_policy must be 'archive' or 'remove'")


def _normalize_phase_zone_strategy(value: object, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError("object_strategies.phase_zone must be 'zone' or 'workstream_anchor'")
    normalized = value.strip().lower()
    aliases = {
        "frame": "zone",
        "frames": "zone",
        "zone": "zone",
        "workstream_anchor": "workstream_anchor",
        "workstream-anchor": "workstream_anchor",
        "workstream_only": "workstream_anchor",
        "workstream-only": "workstream_anchor",
    }
    if normalized in aliases:
        return aliases[normalized]
    raise ValueError("object_strategies.phase_zone must be 'zone' or 'workstream_anchor'")


def _normalize_story_summary_strategy(value: object, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError("object_strategies.story_summary must be 'table' or 'doc'")
    normalized = value.strip().lower()
    aliases = {
        "table": "table",
        "doc": "doc",
        "document": "doc",
    }
    if normalized in aliases:
        return aliases[normalized]
    raise ValueError("object_strategies.story_summary must be 'table' or 'doc'")


def _validate_repo_local_config_paths(config: SyncConfig, *, project_root: str | Path) -> None:
    root = Path(project_root).resolve()
    _validate_repo_local_path_setting(config.manifest_path, label="manifest_path", project_root=root)
    for index, source_path in enumerate(config.source_paths):
        _validate_repo_local_path_setting(
            source_path,
            label=f"discovery.source_paths[{index}]",
            project_root=root,
        )


def _validate_repo_local_path_setting(value: str, *, label: str, project_root: Path) -> None:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(
            f"{label} must stay inside the project root ({project_root}) and use a repo-local relative path: {path}"
        )
    resolved = (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root ({project_root}): {resolved}") from exc
