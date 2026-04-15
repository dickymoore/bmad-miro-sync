from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .templates import (
    ensure_gitignore_entries,
    insert_sync_policy,
    render_comment_ingest_skill,
    render_config,
    render_doc,
    render_skill,
    skill_files,
)


@dataclass(slots=True)
class InstallResult:
    project_root: Path
    written_files: list[Path]
    patched_skills: list[Path]
    skipped_skills: list[Path]


def install_project(
    project_root: str | Path,
    board_url: str,
    *,
    sync_src: str | Path,
    patch_bmad_skills: bool = True,
) -> InstallResult:
    root = Path(project_root).resolve()
    sync_src = str(Path(sync_src).resolve())
    project_name = root.name
    config_path = root / ".bmad-miro.toml"
    runtime_dir = root / ".bmad-miro-sync" / "run"
    skill_path = root / ".agents" / "skills" / "bmad-miro-auto-sync" / "SKILL.md"
    comment_skill_path = root / ".agents" / "skills" / "bmad-ingest-miro-comments" / "SKILL.md"
    doc_path = root / "docs" / "miro-sync.md"
    gitignore_path = root / ".gitignore"

    written_files: list[Path] = []
    patched_skills: list[Path] = []
    skipped_skills: list[Path] = []

    skill_path.parent.mkdir(parents=True, exist_ok=True)
    comment_skill_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)

    config_path.write_text(render_config(board_url), encoding="utf-8")
    written_files.append(config_path)

    skill_path.write_text(
        render_skill(str(root), sync_src, str(config_path), str(runtime_dir), project_name),
        encoding="utf-8",
    )
    written_files.append(skill_path)

    comment_skill_path.write_text(
        render_comment_ingest_skill(str(root), sync_src, str(config_path), str(runtime_dir), project_name),
        encoding="utf-8",
    )
    written_files.append(comment_skill_path)

    doc_path.write_text(
        render_doc(str(root), sync_src, str(config_path), str(runtime_dir), board_url),
        encoding="utf-8",
    )
    written_files.append(doc_path)

    existing_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    updated_gitignore = ensure_gitignore_entries(existing_gitignore)
    if updated_gitignore != existing_gitignore:
        gitignore_path.write_text(updated_gitignore, encoding="utf-8")
        written_files.append(gitignore_path)

    if patch_bmad_skills:
        for skill_file in skill_files(root):
            original = skill_file.read_text(encoding="utf-8")
            updated = insert_sync_policy(original)
            if updated != original:
                skill_file.write_text(updated, encoding="utf-8")
                patched_skills.append(skill_file)
            else:
                skipped_skills.append(skill_file)

    return InstallResult(
        project_root=root,
        written_files=written_files,
        patched_skills=patched_skills,
        skipped_skills=skipped_skills,
    )
