from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import SyncPlan


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
        "",
        "Expected result format:",
        json.dumps(
            {
                "items": [
                    {
                        "artifact_id": "_bmad-output/planning-artifacts/prd.md",
                        "artifact_sha256": "<sha256 from plan artifact>",
                        "item_type": "doc",
                        "item_id": "<host item id>",
                        "miro_url": "<full miro item url>",
                        "title": "PRD",
                        "target_key": "doc:_bmad-output/planning-artifacts/prd.md",
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
                "- For frame operations, use the Miro frame/doc/table creation tools as needed.",
                "- For doc operations, create or update a Miro doc item with the markdown content.",
                "- For table operations, create or update a Miro table with the supplied columns and rows.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Generic MCP host usage:",
                "- Translate each operation into your host's Miro MCP tool calls.",
                "- Persist the execution results in a JSON file matching the expected result format.",
            ]
        )

    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def build_codex_bundle(plan: SyncPlan) -> dict:
    return {
        "board_url": plan.board_url,
        "project_root": plan.project_root,
        "config_path": plan.config_path,
        "warnings": list(plan.warnings),
        "operations": [asdict(operation) for operation in plan.operations],
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "title": artifact.title,
                "kind": artifact.kind,
                "phase": artifact.phase,
                "relative_path": artifact.relative_path,
                "sha256": artifact.sha256,
            }
            for artifact in plan.artifacts
        ],
        "results_template": {
            "items": [
                {
                    "artifact_id": "<artifact id from operation>",
                    "artifact_sha256": "<sha256 from matching artifact>",
                    "item_type": "<doc|table|frame>",
                    "item_id": "<miro item id>",
                    "miro_url": "<full miro item url>",
                    "title": "<created or updated title>",
                    "target_key": "<operation target key>",
                    "updated_at": "<ISO-8601 timestamp>",
                }
            ]
        },
    }
