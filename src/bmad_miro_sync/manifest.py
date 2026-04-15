from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SyncManifest:
    version: int
    items: dict[str, dict[str, Any]]


def load_manifest(project_root: str | Path, manifest_path: str) -> SyncManifest:
    path = Path(project_root) / manifest_path
    if not path.exists():
        return SyncManifest(version=2, items={})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SyncManifest(version=payload.get("version", 2), items=payload.get("items", {}))


def save_manifest(project_root: str | Path, manifest_path: str, manifest: SyncManifest) -> Path:
    path = Path(project_root) / manifest_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": manifest.version, "items": manifest.items}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def apply_results(
    manifest: SyncManifest,
    results: dict[str, Any],
) -> SyncManifest:
    items = dict(manifest.items)
    for entry in results.get("items", []):
        artifact_id = entry["artifact_id"]
        items[artifact_id] = {
            "artifact_sha256": entry["artifact_sha256"],
            "item_type": entry["item_type"],
            "item_id": entry.get("item_id"),
            "miro_url": entry.get("miro_url"),
            "title": entry.get("title"),
            "updated_at": entry.get("updated_at"),
            "target_key": entry.get("target_key"),
            "source_artifact_id": entry.get("source_artifact_id"),
            "heading_level": entry.get("heading_level"),
            "parent_artifact_id": entry.get("parent_artifact_id"),
        }
    return SyncManifest(version=max(manifest.version, 2), items=items)
