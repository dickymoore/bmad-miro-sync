from __future__ import annotations

from pathlib import Path

from ..config import load_config
from ..host_exports import build_codex_bundle, render_host_instructions, write_json
from ..planner import build_sync_plan


def export_bundle(project_root: str | Path, config_path: str | Path, output_dir: str | Path) -> Path:
    project_root = Path(project_root).resolve()
    config_path = Path(config_path).resolve()
    output_dir = Path(output_dir).resolve()
    config = load_config(config_path)
    plan = build_sync_plan(project_root, config_path, config)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "plan.json", plan.to_dict())
    write_json(output_dir / "codex-bundle.json", build_codex_bundle(plan))
    (output_dir / "instructions.md").write_text(render_host_instructions(plan, "codex"), encoding="utf-8")
    write_json(output_dir / "results.template.json", build_codex_bundle(plan)["results_template"])
    return output_dir
