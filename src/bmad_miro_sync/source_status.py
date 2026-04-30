from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import SyncManifest
from .models import SourceGroup, SourcePublishStatus, SourceStatusLedger, SyncPlan


DEFAULT_SOURCE_STATUS_PATH = ".bmad-miro-sync/source-status.json"
_SOURCE_STATUS_VERSION = 1
_TERMINAL_LIFECYCLE_STATES = {"archived", "removed"}
CHANGED_SOURCE_STATUSES = ("not_published", "partially_published", "out_of_date", "failed")


def load_source_status(
    project_root: str | Path,
    path: str = DEFAULT_SOURCE_STATUS_PATH,
) -> SourceStatusLedger:
    ledger_path = Path(project_root) / path
    if not ledger_path.exists():
        return SourceStatusLedger(version=_SOURCE_STATUS_VERSION)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    sources = {
        source_artifact_id: _source_publish_status_from_dict(status_payload)
        for source_artifact_id, status_payload in payload.get("sources", {}).items()
    }
    return SourceStatusLedger(
        version=int(payload.get("version", _SOURCE_STATUS_VERSION) or _SOURCE_STATUS_VERSION),
        sources=sources,
    )


def save_source_status(
    project_root: str | Path,
    ledger: SourceStatusLedger,
    path: str = DEFAULT_SOURCE_STATUS_PATH,
) -> Path:
    ledger_path = Path(project_root) / path
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ledger_path


def build_source_groups(plan: SyncPlan | dict[str, Any]) -> list[SourceGroup]:
    if isinstance(plan, SyncPlan):
        return list(plan.source_groups)
    return [_source_group_from_dict(payload) for payload in plan.get("source_groups", [])]


def build_source_status_ledger(
    plan: SyncPlan | dict[str, Any],
    manifest: SyncManifest,
    results: dict[str, Any] | None = None,
    previous_ledger: SourceStatusLedger | None = None,
) -> SourceStatusLedger:
    source_groups = build_source_groups(plan)
    artifacts_by_id = _artifacts_by_id(plan)
    result_index = _results_by_source(results)
    previous_sources = previous_ledger.sources if previous_ledger is not None else {}

    sources: dict[str, SourcePublishStatus] = {}
    for source_group in source_groups:
        previous = previous_sources.get(source_group.source_artifact_id)
        sources[source_group.source_artifact_id] = _source_status_for_group(
            source_group,
            artifacts_by_id=artifacts_by_id,
            manifest=manifest,
            results_by_source=result_index,
            results=results,
            previous=previous,
        )

    return SourceStatusLedger(version=_SOURCE_STATUS_VERSION, sources=sources)


def select_source_ids(
    ledger: SourceStatusLedger,
    *,
    changed_only: bool = False,
    source_status: str | None = None,
) -> list[str]:
    allowed_statuses = {source_status} if source_status else set()
    if changed_only:
        allowed_statuses.update(CHANGED_SOURCE_STATUSES)
    if not allowed_statuses:
        return list(ledger.sources.keys())
    return [
        source_artifact_id
        for source_artifact_id, status in ledger.sources.items()
        if status.status in allowed_statuses
    ]


def filter_plan_to_sources(
    plan: dict[str, Any],
    source_artifact_ids: list[str] | tuple[str, ...] | set[str],
) -> dict[str, Any]:
    selected_sources = {source_artifact_id for source_artifact_id in source_artifact_ids if source_artifact_id}
    if not selected_sources:
        return {
            **plan,
            "artifacts": [],
            "source_groups": [],
            "operations": [],
            "selection": {"source_artifact_ids": []},
        }

    artifacts = [artifact for artifact in plan.get("artifacts", []) if artifact.get("source_artifact_id") in selected_sources]
    source_groups = [group for group in plan.get("source_groups", []) if group.get("source_artifact_id") in selected_sources]
    required_zones = {
        str(artifact.get("phase_zone") or "")
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("phase_zone")
    }
    required_workstreams = {
        (str(artifact.get("phase_zone") or ""), str(artifact.get("workstream") or ""))
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("phase_zone") and artifact.get("workstream")
    }

    operations: list[dict[str, Any]] = []
    for operation in plan.get("operations", []):
        if not isinstance(operation, dict):
            continue
        source_artifact_id = operation.get("source_artifact_id")
        action = operation.get("action")
        if source_artifact_id in selected_sources:
            operations.append(operation)
            continue
        if action == "ensure_zone" and str(operation.get("phase_zone") or "") in required_zones:
            operations.append(operation)
            continue
        if action == "ensure_workstream_anchor":
            key = (str(operation.get("phase_zone") or ""), str(operation.get("workstream") or ""))
            if key in required_workstreams:
                operations.append(operation)

    filtered_plan = dict(plan)
    filtered_plan["artifacts"] = artifacts
    filtered_plan["source_groups"] = source_groups
    filtered_plan["operations"] = operations
    filtered_plan["selection"] = {"source_artifact_ids": sorted(selected_sources)}
    return filtered_plan


def _source_status_for_group(
    source_group: SourceGroup,
    *,
    artifacts_by_id: dict[str, dict[str, Any]],
    manifest: SyncManifest,
    results_by_source: dict[str, list[dict[str, Any]]],
    results: dict[str, Any] | None,
    previous: SourcePublishStatus | None,
) -> SourcePublishStatus:
    current_artifact_ids = tuple(source_group.section_artifact_ids)
    derived_section_count = len(current_artifact_ids)
    published_section_count = 0
    stale_section_count = 0
    successful_timestamps: list[str] = []

    for artifact_id in current_artifact_ids:
        item = manifest.items.get(artifact_id)
        artifact = artifacts_by_id.get(artifact_id, {})
        if not _is_active_manifest_item(item):
            continue
        if _manifest_item_matches_current_artifact(item, artifact):
            published_section_count += 1
            timestamp = item.get("updated_at") or item.get("sync_timestamp")
            if isinstance(timestamp, str) and timestamp:
                successful_timestamps.append(timestamp)
        else:
            stale_section_count += 1

    source_results = results_by_source.get(source_group.source_artifact_id, [])
    failed_entries = [entry for entry in source_results if entry.get("execution_status") == "failed"]
    failed_section_count = len({entry.get("artifact_id") for entry in failed_entries if entry.get("artifact_id")})
    pending_section_count = max(derived_section_count - published_section_count, 0)

    current_result_error = next((entry.get("error") for entry in failed_entries if entry.get("error")), None)
    attempted_now = bool(source_results)
    attempted_at = results.get("executed_at") if results else None

    current_hash = source_group.source_sha256
    previous_hash = previous.published_source_sha256 if previous is not None else None
    stale_from_previous_hash = bool(previous_hash and previous_hash != current_hash)
    preserve_failed = bool(
        previous is not None
        and previous.status == "failed"
        and previous.source_sha256 == current_hash
        and published_section_count < derived_section_count
    )
    preserve_partial = bool(
        previous is not None
        and previous.status == "partially_published"
        and previous.source_sha256 == current_hash
        and published_section_count < derived_section_count
    )

    if failed_section_count > 0 or preserve_failed:
        status = "failed"
    elif derived_section_count > 0 and published_section_count == derived_section_count:
        status = "published"
    elif published_section_count > 0 or preserve_partial:
        status = "partially_published"
    elif stale_section_count > 0 or stale_from_previous_hash:
        status = "out_of_date"
    else:
        status = "not_published"

    last_successful_publish_at = previous.last_successful_publish_at if previous is not None else None
    published_source_sha256 = previous.published_source_sha256 if previous is not None else None
    if status == "published":
        published_source_sha256 = current_hash
        if successful_timestamps:
            last_successful_publish_at = max(successful_timestamps)
        elif attempted_now and isinstance(attempted_at, str) and attempted_at:
            last_successful_publish_at = attempted_at

    last_attempted_publish_at = previous.last_attempted_publish_at if previous is not None else None
    if attempted_now and isinstance(attempted_at, str) and attempted_at:
        last_attempted_publish_at = attempted_at

    last_failed_publish_at = previous.last_failed_publish_at if previous is not None else None
    if failed_section_count > 0 and isinstance(attempted_at, str) and attempted_at:
        last_failed_publish_at = attempted_at

    last_error = previous.last_error if previous is not None else None
    if current_result_error:
        last_error = current_result_error
    elif status == "published":
        last_error = None

    return SourcePublishStatus(
        source_artifact_id=source_group.source_artifact_id,
        relative_path=source_group.relative_path,
        artifact_class=source_group.artifact_class,
        source_sha256=current_hash,
        published_source_sha256=published_source_sha256,
        status=status,
        derived_section_count=derived_section_count,
        published_section_count=published_section_count,
        failed_section_count=failed_section_count,
        pending_section_count=pending_section_count,
        section_artifact_ids=current_artifact_ids,
        last_successful_publish_at=last_successful_publish_at,
        last_attempted_publish_at=last_attempted_publish_at,
        last_failed_publish_at=last_failed_publish_at,
        last_error=last_error,
    )


def _source_group_from_dict(payload: dict[str, Any]) -> SourceGroup:
    return SourceGroup(
        source_artifact_id=payload["source_artifact_id"],
        relative_path=payload["relative_path"],
        artifact_class=payload["artifact_class"],
        phase_zones=tuple(payload.get("phase_zones", [])),
        workstreams=tuple(payload.get("workstreams", [])),
        section_artifact_ids=tuple(payload.get("section_artifact_ids", [])),
        operation_ids=tuple(payload.get("operation_ids", [])),
        source_sha256=payload.get("source_sha256", ""),
        pending_operation_count=int(payload.get("pending_operation_count", 0) or 0),
    )


def _source_publish_status_from_dict(payload: dict[str, Any]) -> SourcePublishStatus:
    return SourcePublishStatus(
        source_artifact_id=payload["source_artifact_id"],
        relative_path=payload["relative_path"],
        artifact_class=payload["artifact_class"],
        source_sha256=payload["source_sha256"],
        published_source_sha256=payload.get("published_source_sha256"),
        status=payload.get("status", "not_published"),
        derived_section_count=int(payload.get("derived_section_count", 0) or 0),
        published_section_count=int(payload.get("published_section_count", 0) or 0),
        failed_section_count=int(payload.get("failed_section_count", 0) or 0),
        pending_section_count=int(payload.get("pending_section_count", 0) or 0),
        section_artifact_ids=tuple(payload.get("section_artifact_ids", [])),
        last_successful_publish_at=payload.get("last_successful_publish_at"),
        last_attempted_publish_at=payload.get("last_attempted_publish_at"),
        last_failed_publish_at=payload.get("last_failed_publish_at"),
        last_error=payload.get("last_error"),
    )


def _artifacts_by_id(plan: SyncPlan | dict[str, Any]) -> dict[str, dict[str, Any]]:
    if isinstance(plan, SyncPlan):
        return {artifact.artifact_id: artifact.to_dict() for artifact in plan.artifacts}
    return {artifact["artifact_id"]: artifact for artifact in plan.get("artifacts", [])}


def _results_by_source(results: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(results, dict):
        return grouped
    for entry in results.get("items", []):
        source_artifact_id = entry.get("source_artifact_id")
        if not isinstance(source_artifact_id, str) or not source_artifact_id:
            continue
        grouped.setdefault(source_artifact_id, []).append(entry)
    return grouped


def _is_active_manifest_item(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict):
        return False
    return item.get("lifecycle_state", "active") not in _TERMINAL_LIFECYCLE_STATES


def _manifest_item_matches_current_artifact(item: dict[str, Any], artifact: dict[str, Any]) -> bool:
    item_hash = item.get("artifact_sha256") or item.get("content_fingerprint")
    artifact_hash = artifact.get("sha256")
    return bool(item_hash and artifact_hash and item_hash == artifact_hash)
