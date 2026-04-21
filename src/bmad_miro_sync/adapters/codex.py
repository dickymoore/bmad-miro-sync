from __future__ import annotations

from pathlib import Path

from ..host_exports import CODEX_BUNDLE_FILENAME, export_host_bundle


def export_bundle(project_root: str | Path, config_path: str | Path, output_dir: str | Path) -> Path:
    paths = export_host_bundle(
        project_root,
        config_path,
        output_dir,
        host="codex",
        bundle_aliases=(CODEX_BUNDLE_FILENAME,),
    )
    return Path(paths["output_dir"])
