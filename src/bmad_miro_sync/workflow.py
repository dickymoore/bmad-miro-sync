from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .comments import DEFAULT_COMMENTS_OUTPUT, ingest_comments
from .config import load_config
from .decisions import (
    DEFAULT_DECISION_RECORDS_OUTPUT,
    decision_result_from_dict,
    triage_feedback,
    write_decision_records,
    write_decision_sidecar,
)
from .manifest import apply_results, load_manifest, save_manifest
from .readiness import (
    DEFAULT_READINESS_HANDOFF_OUTPUT,
    DEFAULT_READINESS_SUMMARY_OUTPUT,
    aggregate_readiness,
    render_handoff_output,
    render_readiness_summary,
)
from .host_exports import (
    CODEX_BUNDLE_FILENAME,
    INSTRUCTIONS_FILENAME,
    PLAN_FILENAME,
    PUBLISH_BUNDLE_FILENAME,
    RESULTS_TEMPLATE_FILENAME,
    export_host_bundle,
)


DEFAULT_RUNTIME_DIR = ".bmad-miro-sync/run"
DEFAULT_RESULTS_PATH = f"{DEFAULT_RUNTIME_DIR}/results.json"
DEFAULT_COMMENTS_PATH = f"{DEFAULT_RUNTIME_DIR}/comments.json"
DEFAULT_REVIEW_INPUT_PATH = f"{DEFAULT_RUNTIME_DIR}/review-input.json"
DEFAULT_COLLABORATION_REPORT_PATH = f"{DEFAULT_RUNTIME_DIR}/collaboration-run.json"
WORKFLOW_STAGES: tuple[str, ...] = (
    "publish",
    "apply-results",
    "ingest-comments",
    "triage-feedback",
    "summarize-readiness",
)


class WorkflowStageError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def run_codex_collaboration_workflow(
    project_root: str | Path,
    config_path: str | Path,
    *,
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    report_path: str | Path = DEFAULT_COLLABORATION_REPORT_PATH,
    start_at: str = "publish",
    stop_after: str | None = None,
) -> dict[str, Any]:
    _validate_stage_value(start_at, "start_at")
    if stop_after is not None:
        _validate_stage_value(stop_after, "stop_after")
    if stop_after is not None and WORKFLOW_STAGES.index(stop_after) < WORKFLOW_STAGES.index(start_at):
        raise ValueError("stop_after must be the same stage as start_at or a later stage.")

    root = Path(project_root).resolve()
    resolved_config_path = _resolve_project_path(root, config_path)
    resolved_runtime_dir = _resolve_repo_local_path(root, runtime_dir, "runtime_dir")
    resolved_report_path = _resolve_repo_local_path(root, report_path, "report_path")
    config = load_config(resolved_config_path, project_root=root)
    _prepare_workflow_filesystem_targets(root, resolved_runtime_dir, resolved_report_path)

    artifacts = _artifact_contract(root, resolved_runtime_dir, resolved_report_path, config.manifest_path)
    report = _initial_report(
        root,
        resolved_config_path,
        resolved_runtime_dir,
        resolved_report_path,
        artifacts,
    )

    start_index = WORKFLOW_STAGES.index(start_at)
    stop_index = WORKFLOW_STAGES.index(stop_after) if stop_after is not None else len(WORKFLOW_STAGES) - 1

    if start_index > 0:
        _preserve_resumed_stage_history(resolved_report_path, report, start_index)

    for stage_name in WORKFLOW_STAGES[start_index : stop_index + 1]:
        stage_report = report["stages"][stage_name]
        stage_report["status"] = "running"
        stage_report["started_at"] = _now_timestamp()
        _write_report(resolved_report_path, report)
        try:
            if stage_name == "publish":
                export_paths = export_host_bundle(
                    root,
                    resolved_config_path,
                    resolved_runtime_dir,
                    host="codex",
                    bundle_aliases=(CODEX_BUNDLE_FILENAME,),
                )
                output_dir = Path(export_paths["output_dir"])
                stage_report["outputs"] = [
                    _display_path(output_dir / PLAN_FILENAME, root),
                    _display_path(output_dir / PUBLISH_BUNDLE_FILENAME, root),
                    *[_display_path(Path(alias_path), root) for alias_path in export_paths["bundle_aliases"]],
                    _display_path(output_dir / INSTRUCTIONS_FILENAME, root),
                    _display_path(output_dir / RESULTS_TEMPLATE_FILENAME, root),
                ]
                stage_report["message"] = "Exported the Codex publish bundle and stage instructions."
            elif stage_name == "apply-results":
                _run_apply_results_stage(root, resolved_config_path, resolved_runtime_dir)
                stage_report["message"] = "Applied results.json into the repo-local sync manifest."
            elif stage_name == "ingest-comments":
                _run_ingest_comments_stage(root, resolved_config_path, artifacts)
                stage_report["message"] = "Normalized comments into the repo-local review artifact."
            elif stage_name == "triage-feedback":
                _run_triage_feedback_stage(root, resolved_config_path, artifacts)
                stage_report["message"] = "Generated decision records and the canonical decision sidecar."
            else:
                _run_summarize_readiness_stage(root, artifacts)
                stage_report["message"] = "Generated implementation readiness and handoff outputs."
            stage_report["status"] = "completed"
            stage_report["completed_at"] = _now_timestamp()
            report["current_stage"] = stage_name
            report["next_stage"] = _next_stage_name(stage_name)
            _write_report(resolved_report_path, report)
        except WorkflowStageError as exc:
            stage_report["status"] = "failed"
            stage_report["completed_at"] = _now_timestamp()
            stage_report["message"] = exc.message
            report["run_status"] = "failed"
            report["failed_stage"] = exc.stage
            report["current_stage"] = exc.stage
            report["next_stage"] = exc.stage
            report["error"] = exc.message
            _write_report(resolved_report_path, report)
            return report
        except Exception as exc:
            stage_report["status"] = "failed"
            stage_report["completed_at"] = _now_timestamp()
            stage_report["message"] = str(exc)
            report["run_status"] = "failed"
            report["failed_stage"] = stage_name
            report["current_stage"] = stage_name
            report["next_stage"] = stage_name
            report["error"] = str(exc)
            _write_report(resolved_report_path, report)
            return report

    last_stage = WORKFLOW_STAGES[stop_index]
    report["current_stage"] = last_stage
    report["next_stage"] = _next_stage_name(last_stage)
    report["run_status"] = "partial" if stop_index < len(WORKFLOW_STAGES) - 1 else "completed"
    _write_report(resolved_report_path, report)
    return report


def _run_apply_results_stage(project_root: Path, config_path: Path, runtime_dir: Path) -> None:
    config = load_config(config_path, project_root=project_root)
    manifest = load_manifest(project_root, config.manifest_path)
    results_path = runtime_dir / "results.json"
    plan_path = runtime_dir / "plan.json"
    if not results_path.exists():
        raise WorkflowStageError(
            "apply-results",
            f"Missing required repo-local input: {_display_path(results_path, project_root)}. "
            "Execute the exported publish plan and write results.json before resuming at apply-results.",
        )
    try:
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowStageError("apply-results", f"Invalid JSON in {_display_path(results_path, project_root)}: {exc}") from exc

    if not plan_path.exists():
        raise WorkflowStageError(
            "apply-results",
            f"Missing required repo-local input: {_display_path(plan_path, project_root)}. "
            "Re-run the publish stage before resuming at apply-results so pending operations remain inspectable.",
        )
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowStageError("apply-results", f"Invalid JSON in {_display_path(plan_path, project_root)}: {exc}") from exc
    try:
        _validate_apply_results_contract(
            plan,
            config_path=config_path,
            manifest_path=config.manifest_path,
        )
    except ValueError as exc:
        raise WorkflowStageError("apply-results", str(exc)) from exc
    try:
        updated = apply_results(
            manifest,
            results,
            plan=plan,
            plan_path=_display_path(plan_path, project_root),
            results_path=_display_path(results_path, project_root),
        )
    except ValueError as exc:
        raise WorkflowStageError("apply-results", str(exc)) from exc
    save_manifest(project_root, config.manifest_path, updated)


def _run_ingest_comments_stage(project_root: Path, config_path: Path, artifacts: dict[str, Any]) -> None:
    config = load_config(config_path, project_root=project_root)
    manifest = load_manifest(project_root, config.manifest_path)
    comments_path = project_root / artifacts["runtime"]["comments"]
    output_path = project_root / artifacts["feedback"]["miro_comments"]
    if not comments_path.exists():
        raise WorkflowStageError(
            "ingest-comments",
            f"Missing required repo-local input: {_display_path(comments_path, project_root)}. "
            "Fetch and normalize Miro comments before resuming at ingest-comments.",
        )
    try:
        comments_payload = json.loads(comments_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowStageError(
            "ingest-comments",
            f"Invalid JSON in {_display_path(comments_path, project_root)}: {exc}",
        ) from exc
    try:
        ingest_comments(manifest, comments_payload, output_path=output_path)
    except ValueError as exc:
        raise WorkflowStageError("ingest-comments", str(exc)) from exc


def _run_triage_feedback_stage(project_root: Path, config_path: Path, artifacts: dict[str, Any]) -> None:
    config = load_config(config_path, project_root=project_root)
    manifest = load_manifest(project_root, config.manifest_path)
    review_input_path = project_root / artifacts["runtime"]["review_input"]
    output_path = project_root / artifacts["feedback"]["decision_records"]
    sidecar_path = project_root / artifacts["feedback"]["decision_sidecar"]
    if not review_input_path.exists():
        raise WorkflowStageError(
            "triage-feedback",
            f"Missing required repo-local input: {_display_path(review_input_path, project_root)}. "
            "Add explicit triage assignments before resuming at triage-feedback.",
        )
    try:
        review_input = json.loads(review_input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowStageError(
            "triage-feedback",
            f"Invalid JSON in {_display_path(review_input_path, project_root)}: {exc}",
        ) from exc
    try:
        triage_result = triage_feedback(manifest, review_input)
    except ValueError as exc:
        raise WorkflowStageError("triage-feedback", str(exc)) from exc
    write_decision_records(triage_result, output_path=output_path)
    write_decision_sidecar(triage_result, output_path=sidecar_path)


def _run_summarize_readiness_stage(project_root: Path, artifacts: dict[str, Any]) -> None:
    input_path = project_root / artifacts["feedback"]["decision_sidecar"]
    output_path = project_root / artifacts["readiness"]["summary"]
    handoff_output_path = project_root / artifacts["readiness"]["handoff"]
    if not input_path.exists():
        raise WorkflowStageError(
            "summarize-readiness",
            f"Missing required repo-local input: {_display_path(input_path, project_root)}. "
            "Generate decision records before resuming at summarize-readiness.",
        )
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        decision_result = decision_result_from_dict(payload)
    except json.JSONDecodeError as exc:
        raise WorkflowStageError(
            "summarize-readiness",
            f"Invalid JSON in {_display_path(input_path, project_root)}: {exc}",
        ) from exc
    except ValueError as exc:
        raise WorkflowStageError("summarize-readiness", str(exc)) from exc
    aggregate = aggregate_readiness(decision_result.records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_readiness_summary(aggregate), encoding="utf-8")
    handoff_output_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_output_path.write_text(render_handoff_output(aggregate), encoding="utf-8")


def _artifact_contract(project_root: Path, runtime_dir: Path, report_path: Path, manifest_path: str) -> dict[str, Any]:
    runtime_relative = _display_path(runtime_dir, project_root)
    publish = {
        "plan": f"{runtime_relative}/{PLAN_FILENAME}",
        "bundle": f"{runtime_relative}/{PUBLISH_BUNDLE_FILENAME}",
        "bundle_aliases": [f"{runtime_relative}/{CODEX_BUNDLE_FILENAME}"],
        "instructions": f"{runtime_relative}/{INSTRUCTIONS_FILENAME}",
        "results_template": f"{runtime_relative}/{RESULTS_TEMPLATE_FILENAME}",
    }
    runtime = {
        "results": f"{runtime_relative}/results.json",
        "comments": f"{runtime_relative}/comments.json",
        "review_input": f"{runtime_relative}/review-input.json",
        "report": _display_path(report_path, project_root),
        "state": _display_path(_resolve_project_path(project_root, manifest_path), project_root),
    }
    feedback = {
        "miro_comments": DEFAULT_COMMENTS_OUTPUT,
        "decision_records": DEFAULT_DECISION_RECORDS_OUTPUT,
        "decision_sidecar": str(Path(DEFAULT_DECISION_RECORDS_OUTPUT).with_suffix(".json")).replace("\\", "/"),
    }
    readiness = {
        "summary": DEFAULT_READINESS_SUMMARY_OUTPUT,
        "handoff": DEFAULT_READINESS_HANDOFF_OUTPUT,
    }
    return {
        "publish": publish,
        "runtime": runtime,
        "feedback": feedback,
        "readiness": readiness,
    }


def _initial_report(
    project_root: Path,
    config_path: Path,
    runtime_dir: Path,
    report_path: Path,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    stages = {
        "publish": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "inputs": [
                _display_path(config_path, project_root),
            ],
            "outputs": [
                artifacts["publish"]["plan"],
                artifacts["publish"]["bundle"],
                *artifacts["publish"]["bundle_aliases"],
                artifacts["publish"]["instructions"],
                artifacts["publish"]["results_template"],
            ],
            "message": "",
        },
        "apply-results": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "inputs": [
                artifacts["publish"]["plan"],
                artifacts["runtime"]["results"],
            ],
            "outputs": [
                artifacts["runtime"]["state"],
            ],
            "message": "",
        },
        "ingest-comments": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "inputs": [
                artifacts["runtime"]["state"],
                artifacts["runtime"]["comments"],
            ],
            "outputs": [
                artifacts["feedback"]["miro_comments"],
            ],
            "message": "",
        },
        "triage-feedback": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "inputs": [
                artifacts["runtime"]["state"],
                artifacts["runtime"]["review_input"],
            ],
            "outputs": [
                artifacts["feedback"]["decision_records"],
                artifacts["feedback"]["decision_sidecar"],
            ],
            "message": "",
        },
        "summarize-readiness": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "inputs": [
                artifacts["feedback"]["decision_sidecar"],
            ],
            "outputs": [
                artifacts["readiness"]["summary"],
                artifacts["readiness"]["handoff"],
            ],
            "message": "",
        },
    }
    return {
        "run_status": "pending",
        "failed_stage": None,
        "error": None,
        "project_root": str(project_root),
        "config_path": _display_path(config_path, project_root),
        "runtime_dir": _display_path(runtime_dir, project_root),
        "report_path": _display_path(report_path, project_root),
        "stage_order": list(WORKFLOW_STAGES),
        "current_stage": None,
        "next_stage": WORKFLOW_STAGES[0],
        "artifacts": artifacts,
        "stages": stages,
    }


def _next_stage_name(stage_name: str) -> str | None:
    index = WORKFLOW_STAGES.index(stage_name)
    if index >= len(WORKFLOW_STAGES) - 1:
        return None
    return WORKFLOW_STAGES[index + 1]


def _resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _resolve_repo_local_path(project_root: Path, value: str | Path, label: str) -> Path:
    path = _resolve_project_path(project_root, value)
    _require_repo_local_path(project_root, path, label)
    return path


def _require_repo_local_path(project_root: Path, path: Path, label: str) -> None:
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root ({project_root}): {path}") from exc


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_workflow_filesystem_targets(project_root: Path, runtime_dir: Path, report_path: Path) -> None:
    _ensure_directory_target(
        project_root,
        runtime_dir,
        label="runtime_dir",
        guidance="Choose a repo-local directory path for --runtime-dir before running the publish stage.",
    )
    _ensure_parent_directory_target(
        project_root,
        report_path,
        label="report_path",
        guidance="Choose a repo-local file path for --report before running the publish stage.",
    )
    if report_path.exists() and report_path.is_dir():
        raise WorkflowStageError(
            "publish",
            f"Invalid repo-local report path: {_display_path(report_path, project_root)} is a directory. "
            "Choose a repo-local file path for --report before running the publish stage.",
        )


def _ensure_directory_target(project_root: Path, path: Path, *, label: str, guidance: str) -> None:
    if path.exists() and not path.is_dir():
        raise WorkflowStageError(
            "publish",
            f"Invalid repo-local {label}: {_display_path(path, project_root)} exists as a file. {guidance}",
        )
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowStageError(
            "publish",
            f"Unable to prepare repo-local {label} at {_display_path(path, project_root)}: {exc}. {guidance}",
        ) from exc


def _ensure_parent_directory_target(project_root: Path, path: Path, *, label: str, guidance: str) -> None:
    parent = path.parent
    if parent.exists() and not parent.is_dir():
        raise WorkflowStageError(
            "publish",
            f"Invalid repo-local parent for {label}: {_display_path(parent, project_root)} exists as a file. {guidance}",
        )
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowStageError(
            "publish",
            f"Unable to prepare repo-local parent for {label} at {_display_path(parent, project_root)}: {exc}. {guidance}",
        ) from exc


def _preserve_resumed_stage_history(path: Path, report: dict[str, Any], start_index: int) -> None:
    previous_report = _load_report(path)
    previous_stages = previous_report.get("stages") if isinstance(previous_report, dict) else None
    if not isinstance(previous_stages, dict):
        previous_stages = {}

    for stage_name in WORKFLOW_STAGES[:start_index]:
        stage_report = report["stages"][stage_name]
        previous_stage = previous_stages.get(stage_name)
        if isinstance(previous_stage, dict) and previous_stage.get("status") == "completed":
            stage_report.update(previous_stage)
            continue
        stage_report["status"] = "skipped"
        stage_report["message"] = "Skipped in this resumed run."


def _load_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _validate_stage_value(value: str, label: str) -> None:
    if value not in WORKFLOW_STAGES:
        choices = ", ".join(WORKFLOW_STAGES)
        raise ValueError(f"{label} must be one of: {choices}")


def _validate_apply_results_contract(
    plan: dict[str, object],
    *,
    config_path: Path,
    manifest_path: str,
) -> None:
    plan_config_path = plan.get("config_path")
    if isinstance(plan_config_path, str) and plan_config_path:
        if Path(plan_config_path).resolve() != config_path.resolve():
            raise ValueError(
                "Plan/config mismatch: "
                f"plan.json was exported from {plan_config_path}, but the workflow resume is using {config_path}."
            )

    plan_manifest_path = plan.get("manifest_path")
    if not isinstance(plan_manifest_path, str) or not plan_manifest_path:
        raise ValueError(
            "Plan/runtime contract is missing manifest_path. Re-run the publish stage before resuming at apply-results "
            "so the manifest target can be validated."
        )
    if plan_manifest_path != manifest_path:
        raise ValueError(
            "Plan/runtime manifest mismatch: "
            f"plan.json targets {plan_manifest_path}, but the current config resolves to {manifest_path}. "
            "Re-run the publish stage with the intended config before resuming at apply-results."
        )
