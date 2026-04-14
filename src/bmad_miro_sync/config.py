from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class SyncConfig:
    board_url: str
    source_root: str = "_bmad-output"
    manifest_path: str = ".bmad-miro-sync/state.json"
    create_phase_frames: bool = True
    publish_analysis: bool = True
    publish_planning: bool = True
    publish_solutioning: bool = True
    publish_implementation: bool = True
    publish_stories_table: bool = True


def load_config(config_path: str | Path) -> SyncConfig:
    path = Path(config_path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    layout = data.get("layout", {})
    publish = data.get("publish", {})
    board_url = data["board_url"]
    return SyncConfig(
        board_url=board_url,
        source_root=data.get("source_root", "_bmad-output"),
        manifest_path=data.get("manifest_path", ".bmad-miro-sync/state.json"),
        create_phase_frames=layout.get("create_phase_frames", True),
        publish_analysis=publish.get("analysis", True),
        publish_planning=publish.get("planning", True),
        publish_solutioning=publish.get("solutioning", True),
        publish_implementation=publish.get("implementation", True),
        publish_stories_table=publish.get("stories_table", True),
    )
