from __future__ import annotations

from datetime import UTC, datetime
import html
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib import error, parse, request

from .config import LayoutConfig
from .miro_auth import DEFAULT_AUTH_PATH, load_repo_auth_token


DEFAULT_API_BASE_URL = "https://api.miro.com"
DEFAULT_TOKEN_ENV = "MIRO_API_TOKEN"
DEFAULT_RESULTS_PATH = ".bmad-miro-sync/run/results.json"
_BULK_CREATE_LIMIT = 20
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_HOST_ITEM_TYPES = {
    "doc": "text",
    "table": "text",
    "zone": "shape",
    "workstream_anchor": "shape",
}
class MiroApiError(RuntimeError):
    pass


def load_miro_token(token_env: str = DEFAULT_TOKEN_ENV) -> str:
    token = os.environ.get(token_env, "").strip()
    if token:
        return token
    raise MiroApiError(f"Missing Miro API token. Set {token_env} in the environment before running publish-direct.")


def load_miro_token_for_project(project_root: str | Path, token_env: str = DEFAULT_TOKEN_ENV) -> str:
    token = os.environ.get(token_env, "").strip()
    if token:
        return token
    try:
        repo_token = load_repo_auth_token(project_root, DEFAULT_AUTH_PATH)
    except Exception as exc:  # pragma: no cover - converted below for CLI consistency
        raise MiroApiError(str(exc)) from exc
    if repo_token:
        return repo_token
    raise MiroApiError(
        f"Missing Miro API token. Set {token_env} in the environment or configure repo-local REST auth in {DEFAULT_AUTH_PATH}."
    )


def board_id_from_url(board_url: str) -> str:
    parsed = parse.urlparse(board_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    try:
        board_index = segments.index("board")
    except ValueError as exc:
        raise MiroApiError(f"Unsupported Miro board URL: {board_url}") from exc
    if board_index + 1 >= len(segments):
        raise MiroApiError(f"Unsupported Miro board URL: {board_url}")
    return segments[board_index + 1]


def execute_publish_plan(
    plan: dict[str, Any],
    *,
    token: str,
    layout: LayoutConfig | None = None,
    api_base_url: str = DEFAULT_API_BASE_URL,
    stop_on_error: bool = True,
) -> dict[str, Any]:
    resolved_layout = layout or LayoutConfig()
    board_url = _require_str(plan.get("board_url"), "plan.board_url")
    board_id = board_id_from_url(board_url)
    client = MiroApiClient(api_base_url=api_base_url, token=token)
    artifact_index = {artifact["artifact_id"]: artifact for artifact in plan.get("artifacts", []) if isinstance(artifact, dict)}
    executed_items: list[dict[str, Any]] = []
    successful_count = 0
    warnings = list(plan.get("warnings", [])) if isinstance(plan.get("warnings"), list) else []
    operations = _apply_layout_positions(
        [operation for operation in plan.get("operations", []) if isinstance(operation, dict)],
        resolved_layout,
    )
    create_ops: list[dict[str, Any]] = []

    def flush_create_ops() -> tuple[bool, str | None]:
        nonlocal create_ops
        nonlocal successful_count
        if not create_ops:
            return True, None
        ok, error_message, created_items = _execute_create_batch(
            client,
            board_id=board_id,
            board_url=board_url,
            operations=create_ops,
            artifact_index=artifact_index,
            layout=resolved_layout,
        )
        if created_items:
            executed_items.extend(created_items)
            if ok:
                successful_count += len(created_items)
        create_ops = []
        return ok, error_message

    for operation in operations:
        action = operation.get("action")
        if isinstance(action, str) and action.startswith(("create_", "ensure_")):
            create_ops.append(operation)
            if len(create_ops) >= _BULK_CREATE_LIMIT:
                ok, error_message = flush_create_ops()
                if not ok and stop_on_error:
                    return _build_run_results(
                        plan,
                        items=executed_items,
                        warnings=warnings,
                        run_status="partial" if successful_count else "failed",
                        error_message=error_message,
                    )
            continue

        ok, error_message = flush_create_ops()
        if not ok and stop_on_error:
            return _build_run_results(
                plan,
                items=executed_items,
                warnings=warnings,
                run_status="partial" if successful_count else "failed",
                error_message=error_message,
            )

        try:
            result_entry = _execute_single_operation(
                client,
                board_id=board_id,
                board_url=board_url,
                operation=operation,
                artifact=artifact_index.get(operation.get("artifact_id")),
                layout=resolved_layout,
            )
        except MiroApiError as exc:
            executed_items.append(_failed_result_entry(plan, operation, artifact_index.get(operation.get("artifact_id")), str(exc)))
            if stop_on_error:
                return _build_run_results(
                    plan,
                    items=executed_items,
                    warnings=warnings,
                    run_status="partial" if successful_count else "failed",
                    error_message=str(exc),
                )
        else:
            executed_items.append(result_entry)
            successful_count += 1

    ok, error_message = flush_create_ops()
    if not ok and stop_on_error:
        return _build_run_results(
            plan,
            items=executed_items,
            warnings=warnings,
            run_status="partial" if successful_count else "failed",
            error_message=error_message,
        )

    return _build_run_results(plan, items=executed_items, warnings=warnings, run_status="complete")


class MiroApiClient:
    def __init__(self, *, api_base_url: str, token: str) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token

    def bulk_create_items(self, board_id: str, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        response = self._request_json("POST", f"/v2/boards/{board_id}/items/bulk", payload)
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            return [item for item in response["data"] if isinstance(item, dict)]
        raise MiroApiError("Unexpected Miro bulk-create response shape.")

    def create_text(self, board_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request_json("POST", f"/v2/boards/{board_id}/texts", payload)
        if isinstance(response, dict):
            return response
        raise MiroApiError("Unexpected Miro text-create response shape.")

    def update_text(self, board_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request_json("PATCH", f"/v2/boards/{board_id}/texts/{item_id}", payload)
        if isinstance(response, dict):
            return response
        raise MiroApiError("Unexpected Miro text-update response shape.")

    def create_shape(self, board_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request_json("POST", f"/v2/boards/{board_id}/shapes", payload)
        if isinstance(response, dict):
            return response
        raise MiroApiError("Unexpected Miro shape-create response shape.")

    def update_shape(self, board_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request_json("PATCH", f"/v2/boards/{board_id}/shapes/{item_id}", payload)
        if isinstance(response, dict):
            return response
        raise MiroApiError("Unexpected Miro shape-update response shape.")

    def delete_item(self, board_id: str, item_id: str) -> None:
        self._request_json("DELETE", f"/v2/boards/{board_id}/items/{item_id}", None)

    def _request_json(self, method: str, path: str, payload: Any) -> Any:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = f"{self.api_base_url}{path}"

        for attempt in range(_MAX_RETRIES):
            req = request.Request(url, data=body, method=method, headers=headers)
            try:
                with request.urlopen(req) as response:
                    raw = response.read()
            except error.HTTPError as exc:
                if exc.code in _RETRY_STATUSES and attempt + 1 < _MAX_RETRIES:
                    time.sleep(_retry_delay(exc.headers.get("Retry-After"), attempt))
                    continue
                raw = exc.read().decode("utf-8", errors="replace")
                raise MiroApiError(f"Miro API {method} {path} failed with {exc.code}: {raw}") from exc
            except error.URLError as exc:
                if attempt + 1 < _MAX_RETRIES:
                    time.sleep(_retry_delay(None, attempt))
                    continue
                raise MiroApiError(f"Miro API {method} {path} failed: {exc.reason}") from exc

            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise MiroApiError(f"Miro API {method} {path} returned invalid JSON.") from exc

        raise MiroApiError(f"Miro API {method} {path} exhausted retries.")


def _execute_create_batch(
    client: MiroApiClient,
    *,
    board_id: str,
    board_url: str,
    operations: list[dict[str, Any]],
    artifact_index: dict[str, dict[str, Any]],
    layout: LayoutConfig,
) -> tuple[bool, str | None, list[dict[str, Any]]]:
    payload = [_create_payload_for_operation(operation, layout=layout, index=index) for index, operation in enumerate(operations)]
    try:
        response_items = client.bulk_create_items(board_id, payload)
    except MiroApiError as exc:
        failed = [_failed_result_entry({}, operation, artifact_index.get(operation.get("artifact_id")), str(exc)) for operation in operations]
        return False, str(exc), failed

    if len(response_items) != len(operations):
        message = (
            "Miro bulk create returned a different number of items than requested: "
            f"requested {len(operations)}, received {len(response_items)}."
        )
        failed = [_failed_result_entry({}, operation, artifact_index.get(operation.get("artifact_id")), message) for operation in operations]
        return False, message, failed

    results = [
        _result_entry_from_response(
            operation,
            artifact_index.get(operation.get("artifact_id")),
            response_item,
            board_url=board_url,
            execution_status="created",
        )
        for operation, response_item in zip(operations, response_items)
    ]
    return True, None, results


def _execute_single_operation(
    client: MiroApiClient,
    *,
    board_id: str,
    board_url: str,
    operation: dict[str, Any],
    artifact: dict[str, Any] | None,
    layout: LayoutConfig,
) -> dict[str, Any]:
    action = _require_str(operation.get("action"), "operation.action")
    existing_item = operation.get("existing_item") if isinstance(operation.get("existing_item"), dict) else {}
    host_item_type = _host_item_type(operation, existing_item)

    if action == "skip":
        return _unchanged_result_entry(operation, artifact, existing_item, board_url=board_url)

    if action.startswith("update_"):
        item_id = _require_str(existing_item.get("item_id"), f"{action} existing_item.item_id")
        payload = _update_payload_for_operation(operation, layout=layout)
        if host_item_type == "text":
            response = client.update_text(board_id, item_id, payload)
        elif host_item_type == "shape":
            response = client.update_shape(board_id, item_id, payload)
        else:
            raise MiroApiError(f"Unsupported host item type for update: {host_item_type}")
        return _result_entry_from_response(operation, artifact, response, board_url=board_url, execution_status="updated")

    if action.startswith(("archive_", "remove_")):
        item_id = _require_str(existing_item.get("item_id"), f"{action} existing_item.item_id")
        client.delete_item(board_id, item_id)
        return _deleted_result_entry(
            operation,
            artifact,
            existing_item,
            board_url=board_url,
            execution_status="archived" if action.startswith("archive_") else "removed",
        )

    if action.startswith(("create_", "ensure_")):
        payload = _create_payload_for_operation(operation, layout=layout)
        if host_item_type == "text":
            response = client.create_text(board_id, payload)
        elif host_item_type == "shape":
            response = client.create_shape(board_id, payload)
        else:
            raise MiroApiError(f"Unsupported host item type for create: {host_item_type}")
        return _result_entry_from_response(operation, artifact, response, board_url=board_url, execution_status="created")

    raise MiroApiError(f"Unsupported publish action: {action}")


def _create_payload_for_operation(operation: dict[str, Any], *, layout: LayoutConfig, index: int = 0) -> dict[str, Any]:
    host_item_type = _host_item_type(operation, {})
    if host_item_type == "text":
        payload = {
            "type": "text",
            "data": {"content": _operation_content_html(operation)},
            "position": _position_payload(operation, layout=layout, index=index),
            "geometry": {"width": _content_width(operation, layout=layout)},
            "style": {
                "textAlign": "left",
                "fillOpacity": "0.0",
                "fontSize": "14",
            },
        }
        return payload

    if host_item_type == "shape":
        payload = {
            "type": "shape",
            "data": {
                "content": _shape_content_html(operation),
                "shape": "round_rectangle",
            },
            "position": _position_payload(operation, layout=layout, index=index),
            "geometry": _shape_geometry(operation),
            "style": _shape_style(operation, layout=layout),
        }
        return payload

    raise MiroApiError(f"Unsupported host item type for create payload: {host_item_type}")


def _update_payload_for_operation(operation: dict[str, Any], *, layout: LayoutConfig) -> dict[str, Any]:
    existing_item = operation.get("existing_item") if isinstance(operation.get("existing_item"), dict) else {}
    host_item_type = _host_item_type(operation, existing_item)
    if host_item_type == "text":
        payload = {
            "data": {"content": _operation_content_html(operation)},
            "geometry": {"width": _content_width(operation, layout=layout, existing_item=existing_item)},
        }
        return payload

    if host_item_type == "shape":
        payload = {
            "data": {
                "content": _shape_content_html(operation),
                "shape": "round_rectangle",
            },
            "geometry": _shape_geometry(operation, existing_item),
            "style": _shape_style(operation, layout=layout),
        }
        return payload

    raise MiroApiError(f"Unsupported host item type for update payload: {host_item_type}")


def _build_run_results(
    plan: dict[str, Any],
    *,
    items: list[dict[str, Any]],
    warnings: list[str],
    run_status: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_status": run_status,
        "executed_at": _iso_now(),
        "warnings": warnings,
        "object_strategies": plan.get("object_strategies", []),
        "items": items,
    }
    if error_message:
        payload["error"] = error_message
    return payload


def _result_entry_from_response(
    operation: dict[str, Any],
    artifact: dict[str, Any] | None,
    response_item: dict[str, Any],
    *,
    board_url: str,
    execution_status: str,
) -> dict[str, Any]:
    host_item_type = _host_item_type(operation, operation.get("existing_item") if isinstance(operation.get("existing_item"), dict) else {})
    item_id = _require_str(response_item.get("id"), "response.id")
    position = response_item.get("position") if isinstance(response_item.get("position"), dict) else {}
    geometry = response_item.get("geometry") if isinstance(response_item.get("geometry"), dict) else {}
    parent = response_item.get("parent") if isinstance(response_item.get("parent"), dict) else {}
    links = response_item.get("links") if isinstance(response_item.get("links"), dict) else {}
    return {
        "op_id": operation.get("op_id"),
        "artifact_id": operation.get("artifact_id"),
        "artifact_sha256": _artifact_sha256(operation, artifact),
        "item_type": operation.get("item_type"),
        "host_item_type": host_item_type,
        "item_id": item_id,
        "miro_url": links.get("self") or _item_url(board_url, item_id),
        "title": operation.get("title"),
        "target_key": operation.get("target_key"),
        "source_artifact_id": operation.get("source_artifact_id"),
        "phase_zone": operation.get("phase_zone"),
        "workstream": operation.get("workstream"),
        "collaboration_intent": operation.get("collaboration_intent"),
        "container_target_key": operation.get("container_target_key"),
        "layout_policy": operation.get("layout_policy"),
        "layout_snapshot": {
            "x": position.get("x"),
            "y": position.get("y"),
            "width": geometry.get("width"),
            "height": geometry.get("height"),
            "parent_item_id": parent.get("id"),
            "group_id": None,
        },
        "object_family": operation.get("object_family"),
        "preferred_item_type": operation.get("preferred_item_type"),
        "resolved_item_type": operation.get("resolved_item_type"),
        "degraded": bool(operation.get("degraded", False)),
        "fallback_reason": operation.get("fallback_reason"),
        "degraded_warning": operation.get("degraded_warning"),
        "heading_level": operation.get("heading_level", 0),
        "parent_artifact_id": operation.get("parent_artifact_id"),
        "section_path": list((artifact or {}).get("section_path", [])),
        "section_title_path": list((artifact or {}).get("section_title_path", [])),
        "section_slug": (artifact or {}).get("section_slug", ""),
        "section_sibling_index": (artifact or {}).get("section_sibling_index", 0),
        "lineage_key": (artifact or {}).get("lineage_key", ""),
        "lineage_status": (artifact or {}).get("lineage_status", ""),
        "previous_artifact_id": (artifact or {}).get("previous_artifact_id"),
        "previous_parent_artifact_id": (artifact or {}).get("previous_parent_artifact_id"),
        "lifecycle_state": operation.get("lifecycle_state", "active"),
        "execution_status": execution_status,
        "error": None,
        "updated_at": response_item.get("modifiedAt") or response_item.get("createdAt") or _iso_now(),
    }


def _failed_result_entry(
    plan: dict[str, Any],
    operation: dict[str, Any],
    artifact: dict[str, Any] | None,
    error_message: str,
) -> dict[str, Any]:
    existing_item = operation.get("existing_item") if isinstance(operation.get("existing_item"), dict) else {}
    return {
        "op_id": operation.get("op_id"),
        "artifact_id": operation.get("artifact_id"),
        "artifact_sha256": _artifact_sha256(operation, artifact, existing_item),
        "item_type": operation.get("item_type"),
        "host_item_type": _host_item_type(operation, existing_item),
        "item_id": existing_item.get("item_id"),
        "miro_url": existing_item.get("miro_url"),
        "title": operation.get("title") or existing_item.get("title"),
        "target_key": operation.get("target_key"),
        "source_artifact_id": operation.get("source_artifact_id"),
        "phase_zone": operation.get("phase_zone"),
        "workstream": operation.get("workstream"),
        "collaboration_intent": operation.get("collaboration_intent"),
        "container_target_key": operation.get("container_target_key"),
        "layout_policy": operation.get("layout_policy"),
        "layout_snapshot": operation.get("layout_snapshot") or existing_item.get("layout_snapshot"),
        "object_family": operation.get("object_family"),
        "preferred_item_type": operation.get("preferred_item_type"),
        "resolved_item_type": operation.get("resolved_item_type"),
        "degraded": bool(operation.get("degraded", False)),
        "fallback_reason": operation.get("fallback_reason"),
        "degraded_warning": operation.get("degraded_warning"),
        "heading_level": operation.get("heading_level", 0),
        "parent_artifact_id": operation.get("parent_artifact_id"),
        "section_path": list((artifact or {}).get("section_path", [])),
        "section_title_path": list((artifact or {}).get("section_title_path", [])),
        "section_slug": (artifact or {}).get("section_slug", ""),
        "section_sibling_index": (artifact or {}).get("section_sibling_index", 0),
        "lineage_key": (artifact or {}).get("lineage_key", ""),
        "lineage_status": (artifact or {}).get("lineage_status", ""),
        "previous_artifact_id": (artifact or {}).get("previous_artifact_id"),
        "previous_parent_artifact_id": (artifact or {}).get("previous_parent_artifact_id"),
        "lifecycle_state": operation.get("lifecycle_state", "active"),
        "execution_status": "failed",
        "error": error_message,
        "updated_at": _iso_now(),
    }


def _unchanged_result_entry(
    operation: dict[str, Any],
    artifact: dict[str, Any] | None,
    existing_item: dict[str, Any],
    *,
    board_url: str,
) -> dict[str, Any]:
    item_id = existing_item.get("item_id")
    return {
        "op_id": operation.get("op_id"),
        "artifact_id": operation.get("artifact_id"),
        "artifact_sha256": _artifact_sha256(operation, artifact, existing_item),
        "item_type": operation.get("item_type"),
        "host_item_type": _host_item_type(operation, existing_item),
        "item_id": item_id,
        "miro_url": existing_item.get("miro_url") or (_item_url(board_url, item_id) if item_id else None),
        "title": operation.get("title") or existing_item.get("title"),
        "target_key": operation.get("target_key"),
        "source_artifact_id": operation.get("source_artifact_id"),
        "phase_zone": operation.get("phase_zone"),
        "workstream": operation.get("workstream"),
        "collaboration_intent": operation.get("collaboration_intent"),
        "container_target_key": operation.get("container_target_key"),
        "layout_policy": operation.get("layout_policy"),
        "layout_snapshot": operation.get("layout_snapshot") or existing_item.get("layout_snapshot"),
        "object_family": operation.get("object_family"),
        "preferred_item_type": operation.get("preferred_item_type"),
        "resolved_item_type": operation.get("resolved_item_type"),
        "degraded": bool(operation.get("degraded", False)),
        "fallback_reason": operation.get("fallback_reason"),
        "degraded_warning": operation.get("degraded_warning"),
        "heading_level": operation.get("heading_level", 0),
        "parent_artifact_id": operation.get("parent_artifact_id"),
        "section_path": list((artifact or {}).get("section_path", existing_item.get("section_path", []))),
        "section_title_path": list((artifact or {}).get("section_title_path", existing_item.get("section_title_path", []))),
        "section_slug": (artifact or {}).get("section_slug", existing_item.get("section_slug", "")),
        "section_sibling_index": (artifact or {}).get("section_sibling_index", existing_item.get("section_sibling_index", 0)),
        "lineage_key": (artifact or {}).get("lineage_key", existing_item.get("lineage_key", "")),
        "lineage_status": (artifact or {}).get("lineage_status", existing_item.get("lineage_status", "")),
        "previous_artifact_id": (artifact or {}).get("previous_artifact_id", existing_item.get("previous_artifact_id")),
        "previous_parent_artifact_id": (artifact or {}).get("previous_parent_artifact_id", existing_item.get("previous_parent_artifact_id")),
        "lifecycle_state": operation.get("lifecycle_state", "active"),
        "execution_status": "unchanged",
        "error": None,
        "updated_at": existing_item.get("updated_at") or _iso_now(),
    }


def _deleted_result_entry(
    operation: dict[str, Any],
    artifact: dict[str, Any] | None,
    existing_item: dict[str, Any],
    *,
    board_url: str,
    execution_status: str,
) -> dict[str, Any]:
    item_id = existing_item.get("item_id")
    return {
        "op_id": operation.get("op_id"),
        "artifact_id": operation.get("artifact_id"),
        "artifact_sha256": _artifact_sha256(operation, artifact, existing_item),
        "item_type": operation.get("item_type"),
        "host_item_type": _host_item_type(operation, existing_item),
        "item_id": item_id,
        "miro_url": existing_item.get("miro_url") or (_item_url(board_url, item_id) if item_id else None),
        "title": operation.get("title") or existing_item.get("title"),
        "target_key": operation.get("target_key"),
        "source_artifact_id": operation.get("source_artifact_id"),
        "phase_zone": operation.get("phase_zone"),
        "workstream": operation.get("workstream"),
        "collaboration_intent": operation.get("collaboration_intent"),
        "container_target_key": operation.get("container_target_key"),
        "layout_policy": operation.get("layout_policy"),
        "layout_snapshot": existing_item.get("layout_snapshot"),
        "object_family": operation.get("object_family"),
        "preferred_item_type": operation.get("preferred_item_type"),
        "resolved_item_type": operation.get("resolved_item_type"),
        "degraded": bool(operation.get("degraded", False)),
        "fallback_reason": operation.get("fallback_reason"),
        "degraded_warning": operation.get("degraded_warning"),
        "heading_level": operation.get("heading_level", 0),
        "parent_artifact_id": operation.get("parent_artifact_id"),
        "section_path": list((artifact or {}).get("section_path", existing_item.get("section_path", []))),
        "section_title_path": list((artifact or {}).get("section_title_path", existing_item.get("section_title_path", []))),
        "section_slug": (artifact or {}).get("section_slug", existing_item.get("section_slug", "")),
        "section_sibling_index": (artifact or {}).get("section_sibling_index", existing_item.get("section_sibling_index", 0)),
        "lineage_key": (artifact or {}).get("lineage_key", existing_item.get("lineage_key", "")),
        "lineage_status": (artifact or {}).get("lineage_status", existing_item.get("lineage_status", "")),
        "previous_artifact_id": (artifact or {}).get("previous_artifact_id", existing_item.get("previous_artifact_id")),
        "previous_parent_artifact_id": (artifact or {}).get("previous_parent_artifact_id", existing_item.get("previous_parent_artifact_id")),
        "lifecycle_state": execution_status,
        "execution_status": execution_status,
        "error": None,
        "updated_at": _iso_now(),
    }


def _host_item_type(operation: dict[str, Any], existing_item: dict[str, Any]) -> str:
    host_item_type = existing_item.get("host_item_type")
    if isinstance(host_item_type, str) and host_item_type:
        return host_item_type
    item_type = operation.get("item_type")
    if isinstance(item_type, str) and item_type in _HOST_ITEM_TYPES:
        return _HOST_ITEM_TYPES[item_type]
    raise MiroApiError(f"Unsupported planned item type: {item_type}")


def _artifact_sha256(
    operation: dict[str, Any],
    artifact: dict[str, Any] | None,
    existing_item: dict[str, Any] | None = None,
) -> str | None:
    if artifact is not None:
        return artifact.get("sha256")
    if existing_item is not None:
        return existing_item.get("artifact_sha256") or existing_item.get("content_fingerprint")
    if operation.get("item_type") in {"doc", "table"}:
        raise MiroApiError(f"Missing artifact sha256 for content operation {operation.get('op_id')}.")
    return None


def _position_payload(operation: dict[str, Any], *, layout: LayoutConfig, index: int) -> dict[str, Any]:
    x, y = _planned_position(operation, layout=layout, index=index)
    return {
        "origin": "center",
        "x": x,
        "y": y,
    }


def _planned_position(operation: dict[str, Any], *, layout: LayoutConfig, index: int) -> tuple[float, float]:
    planned = operation.get("planned_position")
    if isinstance(planned, dict) and planned.get("x") is not None and planned.get("y") is not None:
        return float(planned["x"]), float(planned["y"])
    phase = str(operation.get("phase_zone") or "planning")
    workstream = str(operation.get("workstream") or "general")
    base_x = layout.workstream_x.get(workstream, 0.0)
    base_y = layout.phase_y.get(phase, 0.0)
    action = operation.get("action")
    if action == "ensure_zone":
        return 0.0, base_y
    if action == "ensure_workstream_anchor":
        return base_x, base_y
    artifact_index = _deterministic_index(operation)
    return base_x, base_y + layout.content_start_y + (artifact_index * (layout.min_card_height + layout.content_gap_y))


def _deterministic_index(operation: dict[str, Any]) -> int:
    deterministic_order = operation.get("deterministic_order")
    if not isinstance(deterministic_order, dict):
        return 0
    artifact_rank = deterministic_order.get("artifact_rank") or 0
    section_rank = deterministic_order.get("section_rank") or 0
    return int(artifact_rank) * 10 + int(section_rank)


def _apply_layout_positions(operations: list[dict[str, Any]], layout: LayoutConfig) -> list[dict[str, Any]]:
    lane_y: dict[tuple[str, str], float] = {}
    planned_operations: list[dict[str, Any]] = []

    for operation in operations:
        planned = dict(operation)
        action = str(planned.get("action") or "")
        phase_zone = str(planned.get("phase_zone") or "planning")
        workstream = str(planned.get("workstream") or "general")
        phase_y = layout.phase_y.get(phase_zone, 0.0)
        workstream_x = layout.workstream_x.get(workstream, 0.0)

        if action == "ensure_zone":
            planned["planned_position"] = {"x": 0.0, "y": phase_y}
        elif action == "ensure_workstream_anchor":
            planned["planned_position"] = {"x": workstream_x, "y": phase_y}
        elif action.startswith(("create_", "ensure_")) and planned.get("item_type") in {"doc", "table"}:
            lane_key = (phase_zone, workstream)
            current_y = lane_y.get(lane_key, phase_y + layout.content_start_y)
            current_x = workstream_x
            if _is_split_fragment(planned):
                current_x += layout.fragment_indent_x
            planned["planned_position"] = {"x": current_x, "y": current_y}
            estimated_height = _estimated_content_height(planned, layout=layout)
            lane_y[lane_key] = current_y + estimated_height + (
                layout.fragment_gap_y if _is_split_fragment(planned) else layout.content_gap_y
            )
        planned_operations.append(planned)

    return planned_operations


def _is_split_fragment(operation: dict[str, Any]) -> bool:
    artifact_id = operation.get("artifact_id")
    if isinstance(artifact_id, str) and "::part-" in artifact_id:
        return True
    return False


def _estimated_content_height(operation: dict[str, Any], *, layout: LayoutConfig) -> float:
    if operation.get("item_type") == "table":
        rows = operation.get("rows") if isinstance(operation.get("rows"), list) else []
        return max(layout.min_card_height, 120.0 + (len(rows) * 44.0))

    content_html = _operation_content_html(operation)
    plain_text = re.sub(r"<[^>]+>", " ", content_html)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    estimated_lines = max(
        3,
        int(max(len(plain_text), 1) / max(layout.chars_per_line, 20.0)),
    )
    return max(layout.min_card_height, 100.0 + (estimated_lines * 24.0))


def _content_width(
    operation: dict[str, Any],
    *,
    layout: LayoutConfig,
    existing_item: dict[str, Any] | None = None,
) -> float:
    if existing_item:
        snapshot = existing_item.get("layout_snapshot")
        if isinstance(snapshot, dict) and snapshot.get("width") is not None:
            return float(snapshot["width"])
    if operation.get("item_type") == "table":
        return layout.table_width
    return layout.doc_width


def _shape_geometry(operation: dict[str, Any], existing_item: dict[str, Any] | None = None) -> dict[str, float]:
    if existing_item:
        snapshot = existing_item.get("layout_snapshot")
        if isinstance(snapshot, dict) and snapshot.get("width") is not None and snapshot.get("height") is not None:
            return {
                "width": float(snapshot["width"]),
                "height": float(snapshot["height"]),
            }
    if operation.get("item_type") == "zone":
        return {"width": 2400.0, "height": 180.0}
    return {"width": 360.0, "height": 120.0}


def _shape_style(operation: dict[str, Any], *, layout: LayoutConfig) -> dict[str, Any]:
    phase_zone = str(operation.get("phase_zone") or "planning")
    return {
        "fillColor": layout.phase_colors.get(phase_zone, "#f5f6f8"),
        "fillOpacity": "1.0",
        "borderColor": "#1a1a1a",
        "borderStyle": "normal",
        "borderWidth": "2.0",
        "textAlign": "center",
        "textAlignVertical": "middle",
        "fontSize": "18",
    }


def _shape_content_html(operation: dict[str, Any]) -> str:
    title = html.escape(str(operation.get("title") or operation.get("target_key") or ""))
    phase = html.escape(str(operation.get("phase_zone") or ""))
    workstream = html.escape(str(operation.get("workstream") or ""))
    lines = [f"<p><strong>{title}</strong></p>"]
    if operation.get("item_type") == "zone":
        lines.append(f"<p>{phase.title()} phase</p>")
    elif workstream and workstream != "general":
        lines.append(f"<p>{phase.title()} / {workstream.title()}</p>")
    return "".join(lines)


def _operation_content_html(operation: dict[str, Any]) -> str:
    if operation.get("item_type") == "table":
        return _table_operation_html(operation)
    return _markdown_to_simple_html(str(operation.get("content") or ""))


def _table_operation_html(operation: dict[str, Any]) -> str:
    columns = operation.get("columns") if isinstance(operation.get("columns"), list) else []
    rows = operation.get("rows") if isinstance(operation.get("rows"), list) else []
    title = html.escape(str(operation.get("title") or ""))
    lines = [f"<p><strong>{title}</strong></p>"]
    if columns:
        lines.append("<p><strong>Columns:</strong> " + ", ".join(html.escape(str(column.get("column_title") or "")) for column in columns) + "</p>")
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = [html.escape(str(value)) for value in row.values()]
        lines.append("<p>- " + " | ".join(values) + "</p>")
    return "".join(lines) or f"<p><strong>{title}</strong></p>"


def _markdown_to_simple_html(content: str) -> str:
    paragraphs: list[str] = []
    buffer: list[str] = []
    in_code = False

    def flush() -> None:
        nonlocal buffer
        if buffer:
            paragraphs.append("<p>" + "<br/>".join(buffer) + "</p>")
            buffer = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                paragraphs.append("<pre>" + "\n".join(buffer) + "</pre>")
                buffer = []
                in_code = False
            else:
                flush()
                in_code = True
            continue
        escaped = html.escape(line)
        if in_code:
            buffer.append(escaped)
            continue
        if not line.strip():
            flush()
            continue
        if line.lstrip().startswith("#"):
            flush()
            heading = escaped.lstrip("#").strip() or escaped
            paragraphs.append(f"<p><strong>{heading}</strong></p>")
            continue
        if line.lstrip().startswith(("- ", "* ")):
            buffer.append("&bull; " + escaped[2:])
            continue
        buffer.append(escaped)

    if in_code:
        paragraphs.append("<pre>" + "\n".join(buffer) + "</pre>")
    else:
        flush()

    return "".join(paragraphs) or "<p></p>"


def _item_url(board_url: str, item_id: str) -> str:
    return f"{board_url}?moveToWidget={parse.quote(item_id)}"


def _require_str(value: Any, label: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise MiroApiError(f"Missing required string field: {label}")


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
    return min(2**attempt, 8)


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
