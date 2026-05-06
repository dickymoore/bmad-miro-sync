from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


@dataclass(slots=True, frozen=True)
class ObjectStrategyConfig:
    phase_zone: str = "zone"
    story_summary: str = "table"


@dataclass(slots=True, frozen=True)
class LayoutConfig:
    phase_y: dict[str, float] = field(
        default_factory=lambda: {
            "analysis": -1800.0,
            "planning": -600.0,
            "solutioning": 600.0,
            "implementation": 1800.0,
            "implementation_readiness": 1800.0,
            "delivery_feedback": 2400.0,
        }
    )
    workstream_x: dict[str, float] = field(
        default_factory=lambda: {
            "general": -2400.0,
            "product": -1200.0,
            "ux": 0.0,
            "architecture": 1200.0,
            "delivery": 2400.0,
        }
    )
    phase_colors: dict[str, str] = field(
        default_factory=lambda: {
            "analysis": "#d8f0dc",
            "planning": "#dbe7ff",
            "solutioning": "#fff0c9",
            "implementation": "#f8d9dc",
            "implementation_readiness": "#f8d9dc",
            "delivery_feedback": "#eadcff",
        }
    )
    workstream_colors: dict[str, str] = field(
        default_factory=lambda: {
            "general": "#6b7280",
            "product": "#2563eb",
            "ux": "#d97706",
            "architecture": "#059669",
            "delivery": "#7c3aed",
        }
    )
    doc_width: float = 460.0
    table_width: float = 760.0
    content_start_y: float = 220.0
    content_gap_y: float = 72.0
    content_gap_x: float = 56.0
    source_gap_y: float = 64.0
    source_header_width: float = 1180.0
    source_header_height: float = 144.0
    source_content_indent_x: float = 0.0
    source_columns: float = 2.0
    fragment_indent_x: float = 150.0
    fragment_gap_y: float = 56.0
    min_card_height: float = 184.0
    chars_per_line: float = 44.0
    zone_width: float = 520.0
    zone_height: float = 84.0
    phase_gap_y: float = 340.0
    workstream_header_width: float = 1180.0
    workstream_header_height: float = 108.0
    zone_title_font_size: float = 22.0
    workstream_title_font_size: float = 24.0
    source_title_font_size: float = 24.0
    doc_font_size: float = 16.0
    summary_paragraph_chars: float = 240.0
    summary_max_bullets: float = 4.0
    summary_bullet_chars: float = 88.0


@dataclass(slots=True)
class SyncConfig:
    board_url: str
    source_root: str = "_bmad-output"
    source_paths: tuple[str, ...] = ("_bmad-output",)
    required_artifact_classes: tuple[str, ...] = ()
    manifest_path: str = ".bmad-miro-sync/state.json"
    object_strategies: ObjectStrategyConfig = ObjectStrategyConfig()
    create_phase_frames: bool = True
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    publish_analysis: bool = True
    publish_planning: bool = True
    publish_solutioning: bool = True
    publish_implementation: bool = True
    publish_stories_table: bool = True
    publish_max_heading_level: int = 2
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
        layout=_resolve_layout_config(layout),
        publish_analysis=publish.get("analysis", True),
        publish_planning=publish.get("planning", True),
        publish_solutioning=publish.get("solutioning", True),
        publish_implementation=publish.get("implementation", True),
        publish_stories_table=resolved_strategies.story_summary == "table",
        publish_max_heading_level=_normalize_int_value(publish.get("max_heading_level"), 2, label="publish.max_heading_level"),
        removed_item_policy=_normalize_removed_item_policy(sync.get("removed_item_policy", "archive")),
    )
    if project_root is not None:
        _validate_repo_local_config_paths(config, project_root=project_root)
    return config


def _resolve_layout_config(layout: object) -> LayoutConfig:
    if not isinstance(layout, dict):
        return LayoutConfig()
    defaults = LayoutConfig()
    return LayoutConfig(
        phase_y=_normalize_float_mapping(layout.get("phase_y"), defaults.phase_y),
        workstream_x=_normalize_float_mapping(layout.get("workstream_x"), defaults.workstream_x),
        phase_colors=_normalize_string_mapping(layout.get("phase_colors"), defaults.phase_colors),
        workstream_colors=_normalize_string_mapping(layout.get("workstream_colors"), defaults.workstream_colors),
        doc_width=_normalize_float_value(layout.get("doc_width"), defaults.doc_width, label="layout.doc_width"),
        table_width=_normalize_float_value(layout.get("table_width"), defaults.table_width, label="layout.table_width"),
        content_start_y=_normalize_float_value(layout.get("content_start_y"), defaults.content_start_y, label="layout.content_start_y"),
        content_gap_y=_normalize_float_value(layout.get("content_gap_y"), defaults.content_gap_y, label="layout.content_gap_y"),
        content_gap_x=_normalize_float_value(layout.get("content_gap_x"), defaults.content_gap_x, label="layout.content_gap_x"),
        source_gap_y=_normalize_float_value(layout.get("source_gap_y"), defaults.source_gap_y, label="layout.source_gap_y"),
        source_header_width=_normalize_float_value(layout.get("source_header_width"), defaults.source_header_width, label="layout.source_header_width"),
        source_header_height=_normalize_float_value(layout.get("source_header_height"), defaults.source_header_height, label="layout.source_header_height"),
        source_content_indent_x=_normalize_float_value(layout.get("source_content_indent_x"), defaults.source_content_indent_x, label="layout.source_content_indent_x"),
        source_columns=_normalize_float_value(layout.get("source_columns"), defaults.source_columns, label="layout.source_columns"),
        fragment_indent_x=_normalize_float_value(layout.get("fragment_indent_x"), defaults.fragment_indent_x, label="layout.fragment_indent_x"),
        fragment_gap_y=_normalize_float_value(layout.get("fragment_gap_y"), defaults.fragment_gap_y, label="layout.fragment_gap_y"),
        min_card_height=_normalize_float_value(layout.get("min_card_height"), defaults.min_card_height, label="layout.min_card_height"),
        chars_per_line=_normalize_float_value(layout.get("chars_per_line"), defaults.chars_per_line, label="layout.chars_per_line"),
        zone_width=_normalize_float_value(layout.get("zone_width"), defaults.zone_width, label="layout.zone_width"),
        zone_height=_normalize_float_value(layout.get("zone_height"), defaults.zone_height, label="layout.zone_height"),
        phase_gap_y=_normalize_float_value(layout.get("phase_gap_y"), defaults.phase_gap_y, label="layout.phase_gap_y"),
        workstream_header_width=_normalize_float_value(layout.get("workstream_header_width"), defaults.workstream_header_width, label="layout.workstream_header_width"),
        workstream_header_height=_normalize_float_value(layout.get("workstream_header_height"), defaults.workstream_header_height, label="layout.workstream_header_height"),
        zone_title_font_size=_normalize_float_value(layout.get("zone_title_font_size"), defaults.zone_title_font_size, label="layout.zone_title_font_size"),
        workstream_title_font_size=_normalize_float_value(layout.get("workstream_title_font_size"), defaults.workstream_title_font_size, label="layout.workstream_title_font_size"),
        source_title_font_size=_normalize_float_value(layout.get("source_title_font_size"), defaults.source_title_font_size, label="layout.source_title_font_size"),
        doc_font_size=_normalize_float_value(layout.get("doc_font_size"), defaults.doc_font_size, label="layout.doc_font_size"),
        summary_paragraph_chars=_normalize_float_value(layout.get("summary_paragraph_chars"), defaults.summary_paragraph_chars, label="layout.summary_paragraph_chars"),
        summary_max_bullets=_normalize_float_value(layout.get("summary_max_bullets"), defaults.summary_max_bullets, label="layout.summary_max_bullets"),
        summary_bullet_chars=_normalize_float_value(layout.get("summary_bullet_chars"), defaults.summary_bullet_chars, label="layout.summary_bullet_chars"),
    )


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


def _normalize_float_mapping(value: object, defaults: dict[str, float]) -> dict[str, float]:
    result = dict(defaults)
    if value is None:
        return result
    if not isinstance(value, dict):
        raise ValueError("layout mappings must be TOML tables with numeric values.")
    for key, raw in value.items():
        if not isinstance(key, str) or not key.strip():
            continue
        result[key.strip()] = _normalize_float_value(raw, result.get(key.strip(), 0.0), label=f"layout.{key.strip()}")
    return result


def _normalize_string_mapping(value: object, defaults: dict[str, str]) -> dict[str, str]:
    result = dict(defaults)
    if value is None:
        return result
    if not isinstance(value, dict):
        raise ValueError("layout mappings must be TOML tables with string values.")
    for key, raw in value.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"layout.{key.strip()} must be a non-empty string")
        result[key.strip()] = raw.strip()
    return result


def _normalize_float_value(value: object, default: float, *, label: str) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{label} must be a number")


def _normalize_int_value(value: object, default: int, *, label: str) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    raise ValueError(f"{label} must be an integer")


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
