from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib

from .comments import DEFAULT_COMMENTS_OUTPUT, ingest_comments
from .config import load_config
from .decisions import (
    DEFAULT_DECISION_RECORDS_OUTPUT,
    DEFAULT_DECISION_RECORDS_SIDECAR_OUTPUT,
    decision_result_from_dict,
    triage_feedback,
    write_decision_records,
    write_decision_sidecar,
)
from .host_exports import CODEX_BUNDLE_FILENAME, export_host_bundle, render_host_instructions, write_json
from .installer import install_project
from .manifest import apply_results, load_manifest, save_manifest
from .planner import build_sync_plan
from .readiness import (
    DEFAULT_READINESS_HANDOFF_OUTPUT,
    DEFAULT_READINESS_SUMMARY_OUTPUT,
    aggregate_readiness,
    render_handoff_output,
    render_readiness_summary,
)
from .workflow import (
    DEFAULT_COLLABORATION_REPORT_PATH,
    DEFAULT_RUNTIME_DIR,
    WORKFLOW_STAGES,
    WorkflowStageError,
    run_codex_collaboration_workflow,
)

DEFAULT_RUNTIME_PLAN_PATH = ".bmad-miro-sync/run/plan.json"


def main() -> int:
    parser = argparse.ArgumentParser(prog="bmad-miro-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Build a sync plan from BMad outputs.")
    _add_common_args(plan_parser)
    plan_parser.add_argument("--output", help="Write the plan JSON to this path.")

    prompt_parser = subparsers.add_parser("render-host-instructions", help="Render host instructions for a plan.")
    _add_common_args(prompt_parser)
    prompt_parser.add_argument("--host", default="codex", help="Host name: codex, claude-code, gemini-cli, generic.")
    prompt_parser.add_argument("--output", help="Write the rendered instructions to this path.")

    bundle_parser = subparsers.add_parser("export-codex-bundle", help="Export a Codex plan bundle and instructions.")
    _add_common_args(bundle_parser)
    bundle_parser.add_argument("--output-dir", required=True, help="Directory to write plan, instructions, and results template.")

    install_parser = subparsers.add_parser("install", help="Install bmad-miro-sync into a target project.")
    install_parser.add_argument("--project-root", default=".", help="Target project root.")
    install_parser.add_argument("--board-url", required=True, help="Miro board URL.")
    install_parser.add_argument(
        "--sync-src",
        default=str(Path(__file__).resolve().parents[2] / "src"),
        help="Path to the bmad_miro_sync source directory used for PYTHONPATH in generated docs/skills.",
    )
    install_parser.add_argument(
        "--no-patch-bmad-skills",
        action="store_true",
        help="Do not patch existing BMad skill headers with the sync policy.",
    )

    results_parser = subparsers.add_parser("apply-results", help="Apply execution results to the local manifest.")
    _add_common_args(results_parser)
    results_parser.add_argument("--results", required=True, help="JSON file with execution results.")
    results_parser.add_argument(
        "--plan",
        default=DEFAULT_RUNTIME_PLAN_PATH,
        help="JSON plan file used to reconcile executed and pending operations.",
    )

    comments_parser = subparsers.add_parser("ingest-comments", help="Convert normalized Miro comments into a BMAD review artifact.")
    _add_common_args(comments_parser)
    comments_parser.add_argument("--comments", required=True, help="JSON file with normalized Miro comments.")
    comments_parser.add_argument(
        "--output",
        default=DEFAULT_COMMENTS_OUTPUT,
        help="Markdown output path relative to the project root.",
    )

    triage_parser = subparsers.add_parser(
        "triage-feedback",
        help="Produce decision records from normalized review input and explicit triage metadata.",
    )
    _add_common_args(triage_parser)
    triage_parser.add_argument("--input", required=True, help="JSON file with normalized comments plus triage assignments.")
    triage_parser.add_argument(
        "--output",
        default=DEFAULT_DECISION_RECORDS_OUTPUT,
        help="Markdown output path relative to the project root.",
    )

    readiness_parser = subparsers.add_parser(
        "summarize-readiness",
        help="Generate implementation-readiness and handoff outputs from canonical decision data.",
    )
    _add_common_args(readiness_parser)
    readiness_parser.add_argument(
        "--input",
        default=DEFAULT_DECISION_RECORDS_SIDECAR_OUTPUT,
        help="JSON file with canonical decision-record sidecar data.",
    )
    readiness_parser.add_argument(
        "--output",
        default=DEFAULT_READINESS_SUMMARY_OUTPUT,
        help="Markdown output path for the board-facing readiness summary.",
    )
    readiness_parser.add_argument(
        "--handoff-output",
        default=DEFAULT_READINESS_HANDOFF_OUTPUT,
        help="Markdown output path for the BMAD-facing handoff artifact.",
    )

    workflow_parser = subparsers.add_parser(
        "run-codex-collaboration-workflow",
        help="Run the repo-local Codex collaboration workflow across publish, ingest, triage, and readiness stages.",
    )
    _add_common_args(workflow_parser)
    workflow_parser.add_argument(
        "--runtime-dir",
        default=DEFAULT_RUNTIME_DIR,
        help="Repo-local runtime directory for bundle exports, staged inputs, and run reports.",
    )
    workflow_parser.add_argument(
        "--report",
        default=DEFAULT_COLLABORATION_REPORT_PATH,
        help="Repo-local JSON run report path.",
    )
    workflow_parser.add_argument(
        "--start-at",
        choices=WORKFLOW_STAGES,
        default="publish",
        help="Resume the collaboration workflow from a specific stage.",
    )
    workflow_parser.add_argument(
        "--stop-after",
        choices=WORKFLOW_STAGES,
        help="Stop after the specified stage and persist a partial run report.",
    )

    args = parser.parse_args()

    if args.command == "plan":
        project_root = Path(args.project_root).resolve()
        try:
            config_path, config = _load_cli_config(project_root, args.config)
            output_path = _optional_repo_local_path(project_root, args.output, "--output")
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        plan = build_sync_plan(project_root, config_path, config)
        payload = plan.to_dict()
        if output_path is not None:
            write_json(output_path, payload)
        else:
            json.dump(payload, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        return 0

    if args.command == "render-host-instructions":
        project_root = Path(args.project_root).resolve()
        try:
            config_path, config = _load_cli_config(project_root, args.config)
            output_path = _optional_repo_local_path(project_root, args.output, "--output")
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        plan = build_sync_plan(project_root, config_path, config)
        output = render_host_instructions(plan, args.host)
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0

    if args.command == "export-codex-bundle":
        project_root = Path(args.project_root).resolve()
        try:
            config_path, _config = _load_cli_config(project_root, args.config)
            output_dir = _resolve_repo_local_path(project_root, args.output_dir, "--output-dir")
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        export_host_bundle(
            project_root,
            config_path,
            output_dir,
            host="codex",
            bundle_aliases=(CODEX_BUNDLE_FILENAME,),
        )
        return 0

    if args.command == "install":
        result = install_project(
            args.project_root,
            args.board_url,
            sync_src=args.sync_src,
            patch_bmad_skills=not args.no_patch_bmad_skills,
        )
        payload = {
            "project_root": str(result.project_root),
            "written_files": [str(path) for path in result.written_files],
            "backup_files": [str(path) for path in result.backup_files],
            "patched_skills": [str(path) for path in result.patched_skills],
            "skipped_skills": [str(path) for path in result.skipped_skills],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if args.command == "apply-results":
        project_root = Path(args.project_root).resolve()
        try:
            config_path, config = _load_cli_config(project_root, args.config)
            manifest = load_manifest(project_root, config.manifest_path)
            results_path = _resolve_repo_local_path(project_root, args.results, "--results")
            plan_path = _resolve_repo_local_path(project_root, args.plan, "--plan")
            results = json.loads(results_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            sys.stderr.write(f"Results file not found: {args.results}\n")
            return 1
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"Invalid results JSON in {args.results}: {exc}\n")
            return 1
        except OSError as exc:
            sys.stderr.write(f"Unable to read results file {args.results}: {exc}\n")
            return 1
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1

        if not plan_path.exists():
            if args.plan != DEFAULT_RUNTIME_PLAN_PATH:
                sys.stderr.write(f"Plan file not found: {args.plan}\n")
                return 1
            try:
                updated = apply_results(manifest, results)
            except (KeyError, TypeError, ValueError) as exc:
                sys.stderr.write(
                    f"Invalid results data in {args.results}: {exc}. "
                    "Legacy results-only reconciliation still requires complete item metadata for content objects.\n"
                )
                return 1
            sys.stderr.write(
                f"Plan file not found: {args.plan}. "
                "Falling back to legacy results-only reconciliation; pending operations will not be tracked. "
                "Re-run export-codex-bundle or the publish stage to restore inspectable retry state.\n"
            )
        else:
            try:
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                sys.stderr.write(f"Invalid plan JSON in {args.plan}: {exc}\n")
                return 1
            except OSError as exc:
                sys.stderr.write(f"Unable to read plan file {args.plan}: {exc}\n")
                return 1

            try:
                _validate_apply_results_contract(
                    plan,
                    config_path=config_path,
                    manifest_path=config.manifest_path,
                )
                updated = apply_results(
                    manifest,
                    results,
                    plan=plan,
                    plan_path=_display_path(plan_path, project_root),
                    results_path=_display_path(results_path, project_root),
                )
            except ValueError as exc:
                sys.stderr.write(f"{exc}\n")
                return 1
        save_manifest(project_root, config.manifest_path, updated)
        return 0

    if args.command == "ingest-comments":
        project_root = Path(args.project_root).resolve()
        try:
            config_path, config = _load_cli_config(project_root, args.config)
            manifest = load_manifest(project_root, config.manifest_path)
            comments_path = _resolve_repo_local_path(project_root, args.comments, "--comments")
            output_target = _resolve_repo_local_path(project_root, args.output, "--output")
            comments = json.loads(comments_path.read_text(encoding="utf-8"))
            output_path = ingest_comments(
                manifest,
                comments,
                output_path=output_target,
            )
        except FileNotFoundError:
            sys.stderr.write(f"Comments file not found: {args.comments}\n")
            return 1
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"Invalid comments JSON in {args.comments}: {exc}\n")
            return 1
        except OSError as exc:
            sys.stderr.write(f"Unable to read or write comment artifacts: {exc}\n")
            return 1
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        json.dump({"output_path": str(output_path)}, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if args.command == "triage-feedback":
        project_root = Path(args.project_root).resolve()
        try:
            config_path, config = _load_cli_config(project_root, args.config)
            manifest = load_manifest(project_root, config.manifest_path)
            input_path = _resolve_repo_local_path(project_root, args.input, "--input")
            output_path = _resolve_repo_local_path(project_root, args.output, "--output")
            sidecar_output_path = output_path.with_suffix(".json")
            _ensure_distinct_paths(
                {
                    "--output": output_path,
                    "derived sidecar output": sidecar_output_path,
                }
            )
            review_input = json.loads(input_path.read_text(encoding="utf-8"))
            triage_result = triage_feedback(manifest, review_input)
            written_path = write_decision_records(triage_result, output_path=output_path)
            sidecar_path = write_decision_sidecar(triage_result, output_path=sidecar_output_path)
        except FileNotFoundError:
            sys.stderr.write(f"Review input file not found: {args.input}\n")
            return 1
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"Invalid review input JSON in {args.input}: {exc}\n")
            return 1
        except OSError as exc:
            sys.stderr.write(f"Unable to read review input {args.input}: {exc}\n")
            return 1
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        json.dump(
            {
                "output_path": str(written_path),
                "sidecar_path": str(sidecar_path),
            },
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
        return 0

    if args.command == "summarize-readiness":
        project_root = Path(args.project_root).resolve()
        try:
            input_path = _resolve_repo_local_path(project_root, args.input, "--input")
            output_path = _resolve_repo_local_path(project_root, args.output, "--output")
            handoff_output_path = _resolve_repo_local_path(project_root, args.handoff_output, "--handoff-output")
            _ensure_distinct_paths(
                {
                    "--input": input_path,
                    "--output": output_path,
                    "--handoff-output": handoff_output_path,
                }
            )
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            decision_result = decision_result_from_dict(payload)
            aggregate = aggregate_readiness(decision_result.records)
            summary_content = render_readiness_summary(aggregate)
            handoff_content = render_handoff_output(aggregate)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(summary_content, encoding="utf-8")
            handoff_output_path.parent.mkdir(parents=True, exist_ok=True)
            handoff_output_path.write_text(handoff_content, encoding="utf-8")
        except FileNotFoundError:
            sys.stderr.write(f"Decision input file not found: {args.input}\n")
            return 1
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"Invalid decision input JSON in {args.input}: {exc}\n")
            return 1
        except OSError as exc:
            sys.stderr.write(f"Unable to read or write readiness artifacts: {exc}\n")
            return 1
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        json.dump(
            {
                "input_path": str(input_path),
                "output_path": str(output_path),
                "handoff_output_path": str(handoff_output_path),
                "overall_state": aggregate.overall_state,
            },
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
        return 0

    if args.command == "run-codex-collaboration-workflow":
        try:
            project_root = Path(args.project_root).resolve()
            runtime_dir = _resolve_repo_local_path(project_root, args.runtime_dir, "--runtime-dir")
            report_path = _resolve_repo_local_path(project_root, args.report, "--report")
            report = run_codex_collaboration_workflow(
                args.project_root,
                args.config,
                runtime_dir=runtime_dir,
                report_path=report_path,
                start_at=args.start_at,
                stop_after=args.stop_after,
            )
        except WorkflowStageError as exc:
            sys.stderr.write(f"{exc.message}\n")
            return 1
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1 if report["run_status"] == "failed" else 0

    return 1


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", default=".", help="Project root containing BMad outputs.")
    parser.add_argument("--config", default=".bmad-miro.toml", help="Path to the TOML sync config.")


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def _load_cli_config(project_root: Path, value: str) -> tuple[Path, object]:
    config_path = _resolve_project_path(project_root, value)
    try:
        config = load_config(config_path, project_root=project_root)
    except FileNotFoundError as exc:
        raise ValueError(f"Config file not found: {value}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in {value}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read config file {value}: {exc}") from exc
    return config_path, config


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _optional_repo_local_path(project_root: Path, value: str | None, label: str) -> Path | None:
    if value is None:
        return None
    return _resolve_repo_local_path(project_root, value, label)


def _resolve_repo_local_path(project_root: Path, value: str, label: str) -> Path:
    path = _resolve_project_path(project_root, value)
    _require_repo_local_path(project_root, path, label)
    return path


def _require_repo_local_path(project_root: Path, path: Path, label: str) -> None:
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root ({project_root}): {path}") from exc


def _ensure_distinct_paths(paths: dict[str, Path]) -> None:
    seen: dict[Path, str] = {}
    for label, path in paths.items():
        other = seen.get(path)
        if other is not None:
            raise ValueError(f"Output path collision: {other} and {label} both resolve to {path}.")
        seen[path] = label


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
                f"plan.json was exported from {plan_config_path}, but apply-results is using {config_path}."
            )

    plan_manifest_path = plan.get("manifest_path")
    if not isinstance(plan_manifest_path, str) or not plan_manifest_path:
        raise ValueError(
            "Plan/runtime contract is missing manifest_path. Re-run export-codex-bundle or the publish stage "
            "before applying results so the manifest target can be validated."
        )
    if plan_manifest_path != manifest_path:
        raise ValueError(
            "Plan/runtime manifest mismatch: "
            f"plan.json targets {plan_manifest_path}, but the current config resolves to {manifest_path}. "
            "Re-run the publish stage with the intended config before applying results."
        )


if __name__ == "__main__":
    raise SystemExit(main())
