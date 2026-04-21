from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .config import load_config
from .models import SyncPlan
from .planner import build_sync_plan


PLAN_FILENAME = "plan.json"
PUBLISH_BUNDLE_FILENAME = "publish-bundle.json"
CODEX_BUNDLE_FILENAME = "codex-bundle.json"
INSTRUCTIONS_FILENAME = "instructions.md"
RESULTS_TEMPLATE_FILENAME = "results.template.json"


def render_host_instructions(plan: SyncPlan, host: str) -> str:
    host_name = host.lower()
    if host_name not in {"codex", "claude-code", "gemini-cli", "generic"}:
        raise ValueError(f"Unsupported host: {host}")

    plan_path = "plan.json"
    lines = [
        f"Host: {host}",
        f"Board: {plan.board_url}",
        "",
        "Run the exported operations in order.",
        "Use the board URL from the plan and preserve target_key values in your execution record.",
        "Respect phase_zone, workstream, collaboration_intent, deterministic_order, layout_policy, layout_snapshot, preferred_item_type, resolved_item_type, and degraded-mode metadata exactly as exported.",
        "Use `container_target_key` as the deterministic lane hint for create and ensure operations. For `layout_policy = preserve`, keep the existing parent or group from `layout_snapshot` instead of reparenting the item back to `container_target_key`.",
        "If the run stops part-way through, return the operations you actually executed and set run_status to partial. The local state file will keep unreturned operations pending for retry.",
        "For repeat-sync lifecycle operations, return `execution_status` as `archived` or `removed` and keep the last known identity metadata in the result entry.",
        "If the plan exports degraded-mode warnings or object strategies, preserve them in the results file so local state keeps the fallback decisions inspectable.",
        "",
        "Expected result format:",
        json.dumps(
            {
                "run_status": "complete",
                "executed_at": "2026-04-17T22:40:00Z",
                "warnings": ["Preferred story summary tables are unavailable; story summaries will be published as readable docs."],
                "object_strategies": [
                    {
                        "object_family": "story_summary",
                        "preferred_item_type": "table",
                        "resolved_item_type": "doc",
                        "degraded": True,
                        "fallback_reason": "Configured object strategy resolved story summaries to docs.",
                        "degraded_warning": "Preferred story summary tables are unavailable; story summaries will be published as readable docs.",
                    }
                ],
                "items": [
                    {
                        "op_id": "doc:_bmad-output/planning-artifacts/prd.md#overview",
                        "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
                        "artifact_sha256": "<sha256 from plan artifact; null for zone/workstream scaffolding>",
                        "item_type": "doc",
                        "item_id": "<host item id>",
                        "miro_url": "<full miro item url>",
                        "title": "PRD / Overview",
                        "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#overview",
                        "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                        "phase_zone": "planning",
                        "workstream": "product",
                        "collaboration_intent": "anchor",
                        "container_target_key": "workstream:planning:product",
                        "layout_policy": "preserve",
                        "layout_snapshot": {
                            "x": 120,
                            "y": 240,
                            "width": 360,
                            "height": 180,
                            "parent_item_id": "frame-1",
                            "group_id": "group-1"
                        },
                        "object_family": "artifact_content",
                        "preferred_item_type": "doc",
                        "resolved_item_type": "doc",
                        "degraded": False,
                        "fallback_reason": None,
                        "degraded_warning": None,
                        "heading_level": 0,
                        "parent_artifact_id": None,
                        "section_path": ["overview"],
                        "section_title_path": ["Overview"],
                        "section_slug": "overview",
                        "section_sibling_index": 1,
                        "lineage_key": "<stable lineage key>",
                        "lineage_status": "new",
                        "previous_artifact_id": None,
                        "previous_parent_artifact_id": None,
                        "lifecycle_state": "active",
                        "execution_status": "created",
                        "error": None,
                        "updated_at": "2026-04-14T15:00:00Z",
                    }
                ]
            },
            indent=2,
        ),
        "",
        f"The plan file is expected to be saved as {plan_path}.",
    ]

    if host_name == "codex":
        lines.extend(
            [
                "",
                "Codex usage:",
                "- Load the plan JSON.",
                "- Execute orientation scaffolding before content objects, preserving deterministic_order.",
                "- Map `ensure_zone` and `ensure_workstream_anchor` to the best available host-native containers without changing their exported target keys.",
                "- If the available Miro tools cannot create board-level containers for `ensure_zone`, set `[object_strategies].phase_zone = \"workstream_anchor\"` in the repo config, regenerate the bundle, and continue from the regenerated plan instead of asking the user to choose a partial sync.",
                "- For doc operations, create or update one Miro doc item per exported markdown section.",
                "- For table operations, create or update a Miro table with the supplied columns and rows.",
                "- When an operation is degraded, treat `resolved_item_type` as the execution target and preserve `preferred_item_type`, `fallback_reason`, and `degraded_warning` in the returned result entry.",
                "- For `update_*` operations with `layout_policy = preserve`, update content in place and do not reapply automatic placement; treat `layout_snapshot.parent_item_id` and `layout_snapshot.group_id` as the live parent and grouping context, and return a refreshed `layout_snapshot` if the item was manually moved, resized, regrouped, or reparented.",
                "- For `create_*` operations with `layout_policy = auto`, apply the normal deterministic placement flow for new items only.",
                "- For `archive_*` or `remove_*` operations, archive or remove the existing Miro item referenced by the operation and report `execution_status` as `archived` or `removed`.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Generic MCP host usage:",
                "- Translate each operation into your host's Miro MCP tool calls.",
                "- Preserve deterministic operation order and group content under the exported phase_zone and workstream scaffolding.",
                "- If your host cannot execute `ensure_zone`, set `[object_strategies].phase_zone = \"workstream_anchor\"` in the repo config, regenerate the bundle, and proceed from the regenerated plan.",
                "- When an operation is degraded, execute `resolved_item_type`, not `preferred_item_type`, and preserve the fallback metadata in your results JSON.",
                "- For `update_*` operations with `layout_policy = preserve`, update the mapped item in place and do not reapply automatic placement; treat `layout_snapshot.parent_item_id` and `layout_snapshot.group_id` as the live parent and grouping context, and return a refreshed `layout_snapshot` if the item was manually moved, resized, regrouped, or reparented.",
                "- For `create_*` operations with `layout_policy = auto`, apply the normal deterministic placement flow for new items only.",
                "- For repeat-sync lifecycle operations, return `archived` or `removed` outcomes through the same results JSON contract.",
                "- Persist the execution results in a JSON file matching the expected result format.",
            ]
        )

    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def build_results_template() -> dict:
    return {
        "run_status": "<complete|partial|failed>",
        "executed_at": "<ISO-8601 timestamp>",
        "warnings": ["<optional degraded-mode warning>"],
        "object_strategies": [
            {
                "object_family": "<strategy family>",
                "preferred_item_type": "<preferred item type>",
                "resolved_item_type": "<resolved item type>",
                "degraded": "<true|false>",
                "fallback_reason": "<optional fallback reason or null>",
                "degraded_warning": "<optional degraded-mode warning or null>",
            }
        ],
        "items": [
            {
                "op_id": "<operation id>",
                "artifact_id": "<artifact id from operation>",
                "artifact_sha256": "<sha256 from matching artifact; null for zone/workstream scaffolding>",
                "item_type": "<doc|table|zone|workstream_anchor>",
                "item_id": "<miro item id>",
                "miro_url": "<full miro item url>",
                "title": "<created or updated title>",
                "target_key": "<operation target key>",
                "source_artifact_id": "<source markdown file path>",
                "phase_zone": "<operation phase zone>",
                "workstream": "<operation workstream>",
                "collaboration_intent": "<operation collaboration intent>",
                "container_target_key": "<workstream or zone target key>",
                "layout_policy": "<auto|preserve>",
                "layout_snapshot": {
                    "x": "<number or null>",
                    "y": "<number or null>",
                    "width": "<number or null>",
                    "height": "<number or null>",
                    "parent_item_id": "<container item id or null>",
                    "group_id": "<group id or null>",
                },
                "object_family": "<artifact_content|story_summary|phase_zone_scaffolding|workstream_anchor>",
                "preferred_item_type": "<preferred item type>",
                "resolved_item_type": "<resolved item type>",
                "degraded": "<true|false>",
                "fallback_reason": "<optional fallback reason or null>",
                "degraded_warning": "<optional degraded-mode warning or null>",
                "heading_level": "<integer>",
                "parent_artifact_id": "<parent section id or null>",
                "section_path": ["<stable section path segments>"],
                "section_title_path": ["<section title path>"],
                "section_slug": "<stable section slug>",
                "section_sibling_index": "<integer>",
                "lineage_key": "<stable lineage key>",
                "lineage_status": "<new|changed|unchanged>",
                "previous_artifact_id": "<prior artifact id or null>",
                "previous_parent_artifact_id": "<prior parent artifact id or null>",
                "lifecycle_state": "<active|archived|removed>",
                "execution_status": "<created|updated|unchanged|archived|removed|failed>",
                "error": "<optional error summary or null>",
                "updated_at": "<ISO-8601 timestamp>",
            }
        ],
    }


def build_publish_bundle(plan: SyncPlan) -> dict:
    return {
        "board_url": plan.board_url,
        "project_root": plan.project_root,
        "config_path": plan.config_path,
        "manifest_path": plan.manifest_path,
        "warnings": list(plan.warnings),
        "discovery": plan.discovery.to_dict(),
        "object_strategies": [strategy.to_dict() for strategy in plan.object_strategies],
        "operations": [asdict(operation) for operation in plan.operations],
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "source_artifact_id": artifact.source_artifact_id,
                "title": artifact.title,
                "kind": artifact.kind,
                "phase": artifact.phase,
                "phase_zone": artifact.phase_zone,
                "workstream": artifact.workstream,
                "collaboration_intent": artifact.collaboration_intent,
                "relative_path": artifact.relative_path,
                "sha256": artifact.sha256,
                "source_type": artifact.source_type,
                "heading_level": artifact.heading_level,
                "parent_artifact_id": artifact.parent_artifact_id,
                "section_path": artifact.section_path,
                "section_title_path": artifact.section_title_path,
                "section_slug": artifact.section_slug,
                "section_sibling_index": artifact.section_sibling_index,
                "lineage_key": artifact.lineage_key,
                "lineage_status": artifact.lineage_status,
                "previous_artifact_id": artifact.previous_artifact_id,
                "previous_parent_artifact_id": artifact.previous_parent_artifact_id,
            }
            for artifact in plan.artifacts
        ],
        "results_template": build_results_template(),
    }


def build_codex_bundle(plan: SyncPlan) -> dict:
    return build_publish_bundle(plan)


def export_host_bundle(
    project_root: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
    *,
    host: str,
    bundle_aliases: tuple[str, ...] = (),
) -> dict[str, Path | list[Path]]:
    project_root = Path(project_root).resolve()
    config_path = Path(config_path).resolve()
    output_dir = Path(output_dir).resolve()
    config = load_config(config_path, project_root=project_root)
    plan = build_sync_plan(project_root, config_path, config)
    bundle = build_publish_bundle(plan)
    output_dir.mkdir(parents=True, exist_ok=True)

    plan_path = write_json(output_dir / PLAN_FILENAME, plan.to_dict())
    bundle_path = write_json(output_dir / PUBLISH_BUNDLE_FILENAME, bundle)
    alias_paths: list[Path] = []
    for alias in bundle_aliases:
        alias_paths.append(write_json(output_dir / alias, bundle))
    instructions_path = output_dir / INSTRUCTIONS_FILENAME
    instructions_path.write_text(render_host_instructions(plan, host), encoding="utf-8")
    results_template_path = write_json(output_dir / RESULTS_TEMPLATE_FILENAME, bundle["results_template"])

    return {
        "output_dir": output_dir,
        "plan": plan_path,
        "bundle": bundle_path,
        "bundle_aliases": alias_paths,
        "instructions": instructions_path,
        "results_template": results_template_path,
    }
