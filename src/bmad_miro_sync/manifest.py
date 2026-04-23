from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

_CONTENT_ITEM_TYPES = {"doc", "table"}
_STATE_VERSION = 3
_TERMINAL_EXECUTION_STATUSES = {"archived", "removed"}
_LAYOUT_SNAPSHOT_FIELDS = (
    "x",
    "y",
    "width",
    "height",
    "parent_item_id",
    "group_id",
)


@dataclass(slots=True)
class SyncManifest:
    version: int
    items: dict[str, dict[str, Any]]
    operations: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_run: dict[str, Any] = field(default_factory=dict)


def load_manifest(project_root: str | Path, manifest_path: str) -> SyncManifest:
    path = Path(project_root) / manifest_path
    if not path.exists():
        return SyncManifest(version=_STATE_VERSION, items={})
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = {
        artifact_id: _normalize_manifest_item(artifact_id, item)
        for artifact_id, item in payload.get("items", {}).items()
    }
    return SyncManifest(
        version=payload.get("version", _STATE_VERSION),
        items=items,
        operations=payload.get("operations", {}),
        last_run=payload.get("last_run", {}),
    )


def save_manifest(project_root: str | Path, manifest_path: str, manifest: SyncManifest) -> Path:
    path = Path(project_root) / manifest_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": manifest.version,
        "items": manifest.items,
        "operations": manifest.operations,
        "last_run": manifest.last_run,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def apply_results(
    manifest: SyncManifest,
    results: dict[str, Any],
    *,
    plan: dict[str, Any] | None = None,
    plan_path: str | Path | None = None,
    results_path: str | Path | None = None,
) -> SyncManifest:
    if plan is not None:
        return _apply_results_with_plan(
            manifest,
            results,
            plan,
            plan_path=plan_path,
            results_path=results_path,
        )

    items = dict(manifest.items)
    for entry in results.get("items", []):
        _store_item_entry(
            items,
            entry,
            execution_status=entry.get("execution_status"),
            results=results,
        )
    return SyncManifest(
        version=max(manifest.version, _STATE_VERSION),
        items=items,
        operations=dict(manifest.operations),
        last_run=dict(manifest.last_run),
    )


def _apply_results_with_plan(
    manifest: SyncManifest,
    results: dict[str, Any],
    plan: dict[str, Any],
    *,
    plan_path: str | Path | None,
    results_path: str | Path | None,
) -> SyncManifest:
    items = dict(manifest.items)
    artifact_index = {artifact["artifact_id"]: artifact for artifact in plan.get("artifacts", [])}
    result_index = _index_results(results.get("items", []))
    operations: dict[str, dict[str, Any]] = {}

    executed_operation_count = 0
    pending_operation_count = 0
    failed_operation_count = 0

    for operation in plan.get("operations", []):
        artifact = artifact_index.get(operation["artifact_id"])
        existing_item = _operation_existing_item(items, operation)
        result_entry = _match_result_entry(result_index, operation)

        if result_entry is not None:
            execution_status = result_entry.get("execution_status") or _default_execution_status(operation)
            executed_operation_count += 1
            if execution_status == "failed":
                failed_operation_count += 1
            if execution_status != "failed":
                _store_item_entry(
                    items,
                    result_entry,
                    operation=operation,
                    artifact=artifact,
                    existing_item=existing_item,
                    execution_status=execution_status,
                    results=results,
                )
            else:
                _preserve_unfinished_replacement_item(
                    items,
                    operation,
                    existing_item,
                    execution_status=execution_status,
                    results=results,
                )
        else:
            execution_status = "unchanged" if operation.get("action") == "skip" or operation.get("status") == "unchanged" else "pending"
            if execution_status == "unchanged":
                executed_operation_count += 1
            elif execution_status == "pending":
                pending_operation_count += 1
                _preserve_unfinished_replacement_item(
                    items,
                    operation,
                    existing_item,
                    execution_status=execution_status,
                    results=results,
                )

        operations[operation["op_id"]] = _build_operation_state(
            operation,
            artifact=artifact,
            result_entry=result_entry,
            existing_item=existing_item,
            execution_status=execution_status,
            results=results,
        )

    last_run = {
        "run_status": _run_status(
            results.get("run_status"),
            pending_operation_count=pending_operation_count,
            failed_operation_count=failed_operation_count,
        ),
        "sync_timestamp": results.get("executed_at"),
        "plan_path": _inspectable_path(plan_path),
        "results_path": _inspectable_path(results_path),
        "total_operation_count": len(plan.get("operations", [])),
        "executed_operation_count": executed_operation_count,
        "pending_operation_count": pending_operation_count,
        "warnings": _combined_warnings(plan.get("warnings"), results.get("warnings")),
        "object_strategies": _combined_object_strategies(
            plan.get("object_strategies"),
            results.get("object_strategies"),
        ),
    }

    return SyncManifest(
        version=max(manifest.version, _STATE_VERSION),
        items=items,
        operations=operations,
        last_run=last_run,
    )


def _build_operation_state(
    operation: dict[str, Any],
    *,
    artifact: dict[str, Any] | None,
    result_entry: dict[str, Any] | None,
    existing_item: dict[str, Any] | None,
    execution_status: str,
    results: dict[str, Any],
) -> dict[str, Any]:
    result_source = result_entry or {}
    existing_source = existing_item or {}
    identity_source = dict(existing_source)
    identity_source.update(result_source)
    content_fingerprint = _artifact_sha256_for_entry(
        result_source,
        operation["item_type"],
        artifact,
        fallback_source=existing_source,
    )
    sync_timestamp = _operation_sync_timestamp(
        result_source,
        existing_source,
        results,
        execution_status=execution_status,
    )
    last_attempted_at = results.get("executed_at") if result_entry is not None else None
    lifecycle_state = _lifecycle_state(
        result_source,
        operation=operation,
        existing_item=existing_source,
        execution_status=execution_status,
    )

    return {
        "op_id": operation["op_id"],
        "planned_action": operation.get("action"),
        "plan_status": operation.get("status"),
        "execution_status": execution_status,
        "artifact_id": operation["artifact_id"],
        "source_artifact_id": operation.get("source_artifact_id"),
        "target_key": operation.get("target_key"),
        "item_type": operation.get("item_type"),
        "host_item_type": _metadata_from_sources("host_item_type", result_source, operation, existing_source),
        "title": operation.get("title") or result_source.get("title") or (artifact or {}).get("title") or existing_source.get("title"),
        "phase": operation.get("phase"),
        "phase_zone": operation.get("phase_zone") or result_source.get("phase_zone") or existing_source.get("phase_zone"),
        "workstream": operation.get("workstream") or result_source.get("workstream") or existing_source.get("workstream"),
        "collaboration_intent": operation.get("collaboration_intent") or result_source.get("collaboration_intent") or existing_source.get("collaboration_intent"),
        "container_target_key": operation.get("container_target_key") or result_source.get("container_target_key") or existing_source.get("container_target_key"),
        "layout_policy": _layout_policy_value(result_source, operation, existing_source),
        "layout_snapshot": _layout_snapshot_value(result_source, operation, existing_source),
        "object_family": _metadata_from_sources("object_family", result_source, operation, existing_source),
        "preferred_item_type": _metadata_from_sources("preferred_item_type", result_source, operation, existing_source),
        "resolved_item_type": _metadata_from_sources("resolved_item_type", result_source, operation, existing_source),
        "degraded": bool(_metadata_from_sources("degraded", result_source, operation, existing_source, default=False)),
        "fallback_reason": _metadata_from_sources("fallback_reason", result_source, operation, existing_source),
        "degraded_warning": _metadata_from_sources("degraded_warning", result_source, operation, existing_source),
        "heading_level": result_source.get("heading_level", operation.get("heading_level", existing_source.get("heading_level"))),
        "parent_artifact_id": result_source.get("parent_artifact_id", operation.get("parent_artifact_id", existing_source.get("parent_artifact_id"))),
        "section_path": _metadata_value("section_path", result_source, artifact, default=[], fallback_source=existing_source),
        "section_title_path": _metadata_value(
            "section_title_path",
            result_source,
            artifact,
            default=[],
            fallback_source=existing_source,
        ),
        "section_slug": _metadata_value("section_slug", result_source, artifact, default="", fallback_source=existing_source),
        "section_sibling_index": _metadata_value(
            "section_sibling_index",
            result_source,
            artifact,
            default=0,
            fallback_source=existing_source,
        ),
        "lineage_key": _metadata_value("lineage_key", result_source, artifact, default="", fallback_source=existing_source),
        "lineage_status": _metadata_value(
            "lineage_status",
            result_source,
            artifact,
            default="",
            fallback_source=existing_source,
        ),
        "previous_artifact_id": _metadata_value(
            "previous_artifact_id",
            result_source,
            artifact,
            default=None,
            fallback_source=existing_source,
        ),
        "previous_parent_artifact_id": _metadata_value(
            "previous_parent_artifact_id",
            result_source,
            artifact,
            default=None,
            fallback_source=existing_source,
        ),
        "content_fingerprint": content_fingerprint,
        "lifecycle_state": lifecycle_state,
        "removal_policy": operation.get("removal_policy") or existing_source.get("removal_policy"),
        "lifecycle_transitioned_at": _lifecycle_transitioned_at(
            existing_source,
            result_source,
            results,
            execution_status=execution_status,
        ),
        "item_id": identity_source.get("item_id"),
        "miro_url": identity_source.get("miro_url"),
        "sync_timestamp": sync_timestamp,
        "last_attempted_at": last_attempted_at,
        "deterministic_order": operation.get("deterministic_order"),
        "error": result_entry.get("error") if result_entry else None,
    }


def _store_item_entry(
    items: dict[str, dict[str, Any]],
    entry: dict[str, Any],
    *,
    operation: dict[str, Any] | None = None,
    artifact: dict[str, Any] | None = None,
    existing_item: dict[str, Any] | None = None,
    execution_status: str | None,
    results: dict[str, Any],
) -> None:
    artifact_id = entry.get("artifact_id") or (operation or {})["artifact_id"]
    existing_source = existing_item or items.get(artifact_id, {})
    item_type = entry.get("item_type") or (operation or {}).get("item_type") or existing_source.get("item_type")
    previous_artifact_id = _metadata_value(
        "previous_artifact_id",
        entry,
        artifact,
        default=None,
        fallback_source=existing_source,
    )
    if previous_artifact_id and previous_artifact_id != artifact_id:
        items.pop(previous_artifact_id, None)

    artifact_sha256 = _artifact_sha256_for_entry(entry, item_type, artifact, fallback_source=existing_source)
    sync_timestamp = _sync_timestamp(entry, results)
    lifecycle_state = _lifecycle_state(
        entry,
        operation=operation,
        existing_item=existing_source,
        execution_status=execution_status,
    )
    items[artifact_id] = {
        "artifact_id": artifact_id,
        "artifact_sha256": artifact_sha256,
        "content_fingerprint": artifact_sha256,
        "item_type": item_type,
        "host_item_type": _metadata_from_sources("host_item_type", entry, operation or {}, existing_source),
        "item_id": entry.get("item_id") or existing_source.get("item_id"),
        "miro_url": entry.get("miro_url") or existing_source.get("miro_url"),
        "title": entry.get("title") or (operation or {}).get("title") or (artifact or {}).get("title") or existing_source.get("title"),
        "updated_at": sync_timestamp,
        "sync_timestamp": sync_timestamp,
        "execution_status": execution_status,
        "lifecycle_state": lifecycle_state,
        "removal_policy": (operation or {}).get("removal_policy") or existing_source.get("removal_policy"),
        "lifecycle_transitioned_at": _lifecycle_transitioned_at(
            existing_source,
            entry,
            results,
            execution_status=execution_status,
        ),
        "target_key": entry.get("target_key") or (operation or {}).get("target_key") or existing_source.get("target_key"),
        "source_artifact_id": entry.get("source_artifact_id") or (operation or {}).get("source_artifact_id") or existing_source.get("source_artifact_id"),
        "phase_zone": entry.get("phase_zone") or (operation or {}).get("phase_zone") or existing_source.get("phase_zone"),
        "workstream": entry.get("workstream") or (operation or {}).get("workstream") or existing_source.get("workstream"),
        "collaboration_intent": entry.get("collaboration_intent") or (operation or {}).get("collaboration_intent") or existing_source.get("collaboration_intent"),
        "container_target_key": entry.get("container_target_key") or (operation or {}).get("container_target_key") or existing_source.get("container_target_key"),
        "layout_policy": _layout_policy_value(entry, operation or {}, existing_source),
        "layout_snapshot": _layout_snapshot_value(entry, operation or {}, existing_source),
        "object_family": _metadata_from_sources("object_family", entry, operation or {}, existing_source),
        "preferred_item_type": _metadata_from_sources("preferred_item_type", entry, operation or {}, existing_source),
        "resolved_item_type": _metadata_from_sources("resolved_item_type", entry, operation or {}, existing_source),
        "degraded": bool(_metadata_from_sources("degraded", entry, operation or {}, existing_source, default=False)),
        "fallback_reason": _metadata_from_sources("fallback_reason", entry, operation or {}, existing_source),
        "degraded_warning": _metadata_from_sources("degraded_warning", entry, operation or {}, existing_source),
        "heading_level": entry.get("heading_level", (operation or {}).get("heading_level", existing_source.get("heading_level"))),
        "parent_artifact_id": entry.get("parent_artifact_id", (operation or {}).get("parent_artifact_id", existing_source.get("parent_artifact_id"))),
        "section_path": _metadata_value("section_path", entry, artifact, default=[], fallback_source=existing_source),
        "section_title_path": _metadata_value("section_title_path", entry, artifact, default=[], fallback_source=existing_source),
        "section_slug": _metadata_value("section_slug", entry, artifact, default="", fallback_source=existing_source),
        "section_sibling_index": _metadata_value("section_sibling_index", entry, artifact, default=0, fallback_source=existing_source),
        "lineage_key": _metadata_value("lineage_key", entry, artifact, default="", fallback_source=existing_source),
        "lineage_status": _metadata_value("lineage_status", entry, artifact, default="", fallback_source=existing_source),
        "previous_artifact_id": previous_artifact_id,
        "previous_parent_artifact_id": _metadata_value(
            "previous_parent_artifact_id",
            entry,
            artifact,
            default=None,
            fallback_source=existing_source,
        ),
    }


def _preserve_unfinished_replacement_item(
    items: dict[str, dict[str, Any]],
    operation: dict[str, Any],
    existing_item: dict[str, Any] | None,
    *,
    execution_status: str,
    results: dict[str, Any],
) -> None:
    if not _is_replacement_lifecycle_operation(operation, existing_item, execution_status):
        return

    placeholder_entry = dict(existing_item)
    placeholder_entry["artifact_id"] = operation["artifact_id"]
    placeholder_entry["target_key"] = operation.get("target_key") or existing_item.get("target_key")
    placeholder_entry["title"] = operation.get("title") or existing_item.get("title")
    placeholder_entry["lifecycle_state"] = existing_item.get("lifecycle_state", "active")
    _store_item_entry(
        items,
        placeholder_entry,
        operation=operation,
        existing_item=existing_item,
        execution_status=execution_status,
        results=results,
    )


def _is_replacement_lifecycle_operation(
    operation: dict[str, Any],
    existing_item: dict[str, Any] | None,
    execution_status: str,
) -> bool:
    if existing_item is None:
        return False
    if execution_status in _TERMINAL_EXECUTION_STATUSES:
        return False
    if not operation.get("action", "").startswith(("archive_", "remove_")):
        return False
    return operation.get("artifact_id") != existing_item.get("artifact_id")


def _artifact_sha256_for_entry(
    entry: dict[str, Any],
    item_type: str,
    artifact: dict[str, Any] | None = None,
    fallback_source: dict[str, Any] | None = None,
) -> str | None:
    artifact_sha256 = entry.get("artifact_sha256")
    if artifact_sha256 is None and artifact is not None:
        artifact_sha256 = artifact.get("sha256")
    if artifact_sha256 is None and fallback_source is not None:
        artifact_sha256 = fallback_source.get("artifact_sha256") or fallback_source.get("content_fingerprint")
    if item_type in _CONTENT_ITEM_TYPES and not artifact_sha256:
        raise KeyError("artifact_sha256")
    return artifact_sha256


def _default_execution_status(operation: dict[str, Any]) -> str:
    action = operation.get("action", "")
    if action.startswith("create_") or action.startswith("ensure_"):
        return "created"
    if action.startswith("update_"):
        return "updated"
    if action.startswith("archive_"):
        return "archived"
    if action.startswith("remove_"):
        return "removed"
    if action == "skip":
        return "unchanged"
    return "completed"


def _default_run_status(pending_operation_count: int) -> str:
    return "partial" if pending_operation_count else "complete"


def _run_status(
    reported_status: Any,
    *,
    pending_operation_count: int,
    failed_operation_count: int,
) -> str:
    if reported_status == "failed":
        return "failed"
    if failed_operation_count:
        return "failed"
    if pending_operation_count:
        return "partial"
    if reported_status in {"complete", "partial"}:
        return "complete"
    return _default_run_status(pending_operation_count)


def _sync_timestamp(entry: dict[str, Any], results: dict[str, Any]) -> str | None:
    return entry.get("updated_at") or entry.get("sync_timestamp") or results.get("executed_at")


def _operation_sync_timestamp(
    result_source: dict[str, Any],
    existing_source: dict[str, Any],
    results: dict[str, Any],
    *,
    execution_status: str,
) -> str | None:
    if execution_status == "pending":
        return None
    if execution_status == "failed":
        return existing_source.get("sync_timestamp") or existing_source.get("updated_at")
    return _sync_timestamp(result_source or existing_source, results)


def _metadata_value(
    key: str,
    entry: dict[str, Any],
    artifact: dict[str, Any] | None,
    *,
    default: Any,
    fallback_source: dict[str, Any] | None = None,
) -> Any:
    value = entry.get(key)
    if value is None and artifact is not None:
        value = artifact.get(key)
    if value is None and fallback_source is not None:
        value = fallback_source.get(key)
    if value is None:
        value = default
    if key in {"section_path", "section_title_path"}:
        return list(value)
    return value


def _lifecycle_state(
    entry: dict[str, Any],
    *,
    operation: dict[str, Any] | None,
    existing_item: dict[str, Any] | None,
    execution_status: str | None,
) -> str:
    if execution_status in _TERMINAL_EXECUTION_STATUSES:
        return execution_status
    for source in (entry, operation or {}, existing_item or {}):
        lifecycle_state = source.get("lifecycle_state")
        if lifecycle_state:
            return lifecycle_state
    return "active"


def _lifecycle_transitioned_at(
    existing_item: dict[str, Any],
    entry: dict[str, Any],
    results: dict[str, Any],
    *,
    execution_status: str | None,
) -> str | None:
    if execution_status in _TERMINAL_EXECUTION_STATUSES:
        return _sync_timestamp(entry, results)
    return existing_item.get("lifecycle_transitioned_at")


def _index_results(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    seen: dict[str, tuple[int, str]] = {}
    for entry_index, entry in enumerate(entries):
        row_keys: dict[str, str] = {}
        for field_name in ("op_id", "target_key", "artifact_id"):
            key = entry.get(field_name)
            if key and key not in row_keys:
                row_keys[key] = field_name
        for key, field_name in row_keys.items():
            previous = seen.get(key)
            if previous is not None:
                previous_index, previous_field = previous
                raise ValueError(
                    "Duplicate results entry key "
                    f"{key!r}: items[{previous_index}].{previous_field} and items[{entry_index}].{field_name} "
                    "must be unique within one results file."
                )
            seen[key] = (entry_index, field_name)
            index[key] = entry
    return index


def _match_result_entry(result_index: dict[str, dict[str, Any]], operation: dict[str, Any]) -> dict[str, Any] | None:
    for key in (operation.get("op_id"), operation.get("target_key"), operation.get("artifact_id")):
        if key and key in result_index:
            return result_index[key]
    return None


def _operation_existing_item(items: dict[str, dict[str, Any]], operation: dict[str, Any]) -> dict[str, Any] | None:
    return items.get(operation["artifact_id"]) or operation.get("existing_item")


def _inspectable_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    parts = Path(path).parts
    for marker in (".bmad-miro-sync", "_bmad-output"):
        if marker in parts:
            return Path(*parts[parts.index(marker) :]).as_posix()
    return Path(path).as_posix()


def _metadata_from_sources(key: str, *sources: dict[str, Any], default: Any = None) -> Any:
    for source in sources:
        if not source:
            continue
        value = source.get(key)
        if value is not None:
            return value
    return default


def _combined_warnings(*warning_sets: Any) -> list[str]:
    warnings: list[str] = []
    for warning_set in warning_sets:
        if not isinstance(warning_set, list):
            continue
        for warning in warning_set:
            if not isinstance(warning, str):
                continue
            normalized = warning.strip()
            if normalized and normalized not in warnings:
                warnings.append(normalized)
    return warnings


def _normalize_object_strategies(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append(dict(item))
    return normalized


def _combined_object_strategies(*strategy_sets: Any) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    by_family: dict[str, dict[str, Any]] = {}

    for strategy_set in strategy_sets:
        for strategy in _normalize_object_strategies(strategy_set):
            object_family = strategy.get("object_family")
            if isinstance(object_family, str) and object_family:
                existing = by_family.get(object_family)
                if existing is None:
                    merged = dict(strategy)
                    combined.append(merged)
                    by_family[object_family] = merged
                else:
                    existing.update(strategy)
                continue
            if strategy not in combined:
                combined.append(dict(strategy))

    return combined


def _normalize_manifest_item(artifact_id: str, item: Any) -> dict[str, Any]:
    payload = dict(item) if isinstance(item, dict) else {}
    payload.setdefault("artifact_id", artifact_id)
    if "content_fingerprint" not in payload and payload.get("artifact_sha256") is not None:
        payload["content_fingerprint"] = payload["artifact_sha256"]
    payload.setdefault("lifecycle_state", "active")
    if "sync_timestamp" not in payload and payload.get("updated_at") is not None:
        payload["sync_timestamp"] = payload["updated_at"]
    layout_snapshot = _normalize_layout_snapshot(payload)
    if layout_snapshot is not None:
        payload["layout_snapshot"] = layout_snapshot
    return payload


def _layout_policy_value(*sources: dict[str, Any]) -> str | None:
    for source in sources:
        if not source:
            continue
        value = source.get("layout_policy")
        if value is not None:
            return value
    return None


def _layout_snapshot_value(*sources: dict[str, Any]) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    for source in reversed(sources):
        if not source:
            continue
        snapshot = _normalize_layout_snapshot(source)
        if snapshot is not None:
            merged.update(snapshot)
    return merged or None


def _normalize_layout_snapshot(source: dict[str, Any]) -> dict[str, Any] | None:
    raw_snapshot = source.get("layout_snapshot")
    if isinstance(raw_snapshot, dict):
        return dict(raw_snapshot)

    snapshot: dict[str, Any] = {}
    for key in _LAYOUT_SNAPSHOT_FIELDS:
        value = source.get(key)
        if value is not None:
            snapshot[key] = value
    return snapshot or None
