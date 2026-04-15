from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .comments import DEFAULT_COMMENTS_OUTPUT, ingest_comments
from .config import load_config
from .host_exports import build_codex_bundle, render_host_instructions, write_json
from .installer import install_project
from .manifest import apply_results, load_manifest, save_manifest
from .planner import build_sync_plan


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

    comments_parser = subparsers.add_parser("ingest-comments", help="Convert normalized Miro comments into a BMAD review artifact.")
    _add_common_args(comments_parser)
    comments_parser.add_argument("--comments", required=True, help="JSON file with normalized Miro comments.")
    comments_parser.add_argument(
        "--output",
        default=DEFAULT_COMMENTS_OUTPUT,
        help="Markdown output path relative to the project root.",
    )

    args = parser.parse_args()

    if args.command == "plan":
        project_root = Path(args.project_root).resolve()
        config_path = Path(args.config).resolve()
        config = load_config(config_path)
        plan = build_sync_plan(project_root, config_path, config)
        payload = plan.to_dict()
        if args.output:
            write_json(args.output, payload)
        else:
            json.dump(payload, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        return 0

    if args.command == "render-host-instructions":
        project_root = Path(args.project_root).resolve()
        config_path = Path(args.config).resolve()
        config = load_config(config_path)
        plan = build_sync_plan(project_root, config_path, config)
        output = render_host_instructions(plan, args.host)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0

    if args.command == "export-codex-bundle":
        project_root = Path(args.project_root).resolve()
        config_path = Path(args.config).resolve()
        config = load_config(config_path)
        plan = build_sync_plan(project_root, config_path, config)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "plan.json", plan.to_dict())
        write_json(output_dir / "codex-bundle.json", build_codex_bundle(plan))
        (output_dir / "instructions.md").write_text(render_host_instructions(plan, "codex"), encoding="utf-8")
        write_json(
            output_dir / "results.template.json",
            build_codex_bundle(plan)["results_template"],
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
        config_path = Path(args.config).resolve()
        config = load_config(config_path)
        manifest = load_manifest(project_root, config.manifest_path)
        results = json.loads(Path(args.results).read_text(encoding="utf-8"))
        updated = apply_results(manifest, results)
        save_manifest(project_root, config.manifest_path, updated)
        return 0

    if args.command == "ingest-comments":
        project_root = Path(args.project_root).resolve()
        config_path = Path(args.config).resolve()
        config = load_config(config_path)
        manifest = load_manifest(project_root, config.manifest_path)
        comments = json.loads(Path(args.comments).read_text(encoding="utf-8"))
        output_path = ingest_comments(
            manifest,
            comments,
            output_path=project_root / args.output,
        )
        json.dump({"output_path": str(output_path)}, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    return 1


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", default=".", help="Project root containing BMad outputs.")
    parser.add_argument("--config", default=".bmad-miro.toml", help="Path to the TOML sync config.")


if __name__ == "__main__":
    raise SystemExit(main())
