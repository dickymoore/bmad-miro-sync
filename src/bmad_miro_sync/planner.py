from __future__ import annotations

from pathlib import Path

from .config import SyncConfig
from .discovery import discover_artifacts
from .manifest import load_manifest
from .models import PublishOperation, SyncPlan


PHASE_FLAGS = {
    "analysis": "publish_analysis",
    "planning": "publish_planning",
    "solutioning": "publish_solutioning",
    "implementation": "publish_implementation",
}


def build_sync_plan(
    project_root: str | Path,
    config_path: str | Path,
    config: SyncConfig,
) -> SyncPlan:
    root = Path(project_root)
    artifacts = discover_artifacts(root, config.source_root)
    manifest = load_manifest(root, config.manifest_path)

    plan = SyncPlan(
        board_url=config.board_url,
        project_root=str(root),
        config_path=str(Path(config_path)),
        artifacts=artifacts,
    )

    if not artifacts:
        plan.warnings.append(f"No markdown artifacts found under {config.source_root}.")
        return plan

    if config.create_phase_frames:
        for phase in _enabled_phases(config):
            plan.operations.append(
                PublishOperation(
                    op_id=f"frame:{phase}",
                    action="ensure_frame",
                    item_type="frame",
                    title=phase.title(),
                    phase=phase,
                    artifact_id=f"phase:{phase}",
                    source_artifact_id=f"phase:{phase}",
                    target_key=f"frame:{phase}",
                )
            )

    stories_rows: list[dict[str, str]] = []
    story_rows_seen: set[str] = set()
    for artifact in artifacts:
        if not getattr(config, PHASE_FLAGS.get(artifact.phase, "publish_planning"), True):
            continue

        existing_item = manifest.items.get(artifact.artifact_id)
        if existing_item and existing_item.get("artifact_sha256") == artifact.sha256:
            action = "skip"
            status = "unchanged"
        elif existing_item:
            action = "update_doc"
            status = "pending"
        else:
            action = "create_doc"
            status = "pending"

        plan.operations.append(
            PublishOperation(
                op_id=f"doc:{artifact.artifact_id}",
                action=action,
                item_type="doc",
                title=artifact.title,
                phase=artifact.phase,
                artifact_id=artifact.artifact_id,
                source_artifact_id=artifact.source_artifact_id,
                target_key=f"section:{artifact.artifact_id}",
                content=artifact.content,
                existing_item=existing_item,
                status=status,
                heading_level=artifact.heading_level,
                parent_artifact_id=artifact.parent_artifact_id,
            )
        )

        if artifact.kind == "story" and artifact.source_artifact_id not in story_rows_seen:
            story_rows_seen.add(artifact.source_artifact_id)
            stories_rows.append(
                {
                    "Story": artifact.title.split(" / ", 1)[0],
                    "Artifact ID": artifact.source_artifact_id,
                    "Path": artifact.relative_path,
                }
            )

    if config.publish_stories_table and stories_rows:
        story_key = "table:implementation-stories"
        existing_item = manifest.items.get(story_key)
        action = "update_table" if existing_item else "create_table"
        plan.operations.append(
            PublishOperation(
                op_id=story_key,
                action=action,
                item_type="table",
                title="Implementation Stories",
                phase="implementation",
                artifact_id=story_key,
                source_artifact_id=story_key,
                target_key=story_key,
                columns=[
                    {"column_type": "text", "column_title": "Story"},
                    {"column_type": "text", "column_title": "Artifact ID"},
                    {"column_type": "text", "column_title": "Path"},
                ],
                rows=[{"cells": [{"columnTitle": key, "value": value} for key, value in row.items()]} for row in stories_rows],
                existing_item=existing_item,
            )
        )

    return plan


def _enabled_phases(config: SyncConfig) -> list[str]:
    phases: list[str] = []
    for phase, attr_name in PHASE_FLAGS.items():
        if getattr(config, attr_name):
            phases.append(phase)
    return phases
