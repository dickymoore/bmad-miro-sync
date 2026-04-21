from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from .config import SyncConfig
from .classifier import canonical_source_name, classify_artifact, title_from_path
from .manifest import load_manifest
from .markdown import split_markdown_sections
from .models import (
    ArtifactDiscoveryResult,
    ArtifactRecord,
    DiscoveryMissingArtifactClass,
    DiscoverySelection,
    DiscoverySkippedCandidate,
)


def discover_artifacts(
    project_root: str | Path,
    config: SyncConfig,
    *,
    config_path: str | Path = ".bmad-miro.toml",
) -> ArtifactDiscoveryResult:
    root = Path(project_root)
    candidates = _collect_candidates(root, config.source_paths)
    selected_candidates, skipped = _select_canonical_candidates(candidates)

    selected = [
        DiscoverySelection(
            artifact_class=candidate.artifact_class,
            phase=candidate.phase,
            phase_zone=candidate.phase_zone,
            workstream=candidate.workstream,
            collaboration_intent=candidate.collaboration_intent,
            relative_path=candidate.relative_path,
            source_path=candidate.source_path,
            source_variant=candidate.source_variant,
        )
        for candidate in selected_candidates
    ]

    warnings: list[str] = []
    missing_required: list[DiscoveryMissingArtifactClass] = []
    selected_classes = {item.artifact_class for item in selected}
    for artifact_class in config.required_artifact_classes:
        if artifact_class in selected_classes:
            continue
        warning = (
            f"Required artifact class '{artifact_class}' was not found in configured discovery source paths: "
            + ", ".join(config.source_paths)
            + "."
        )
        missing_required.append(
            DiscoveryMissingArtifactClass(
                artifact_class=artifact_class,
                search_paths=list(config.source_paths),
                warning=warning,
            )
            )
        warnings.append(warning)

    previous_artifacts = _load_previous_artifacts(root, config, config_path=config_path)
    artifacts: list[ArtifactRecord] = []
    for selection in selected:
        path = root / selection.relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        file_title = title_from_path(selection.relative_path, content)
        sections = split_markdown_sections(content)
        if not sections:
            continue
        slug_to_id = {section.slug: f"{selection.relative_path}#{section.slug}" for section in sections}
        current_artifacts: list[ArtifactRecord] = []
        for section in sections:
            section_title = f"{file_title} / {section.title}"
            current_artifacts.append(
                ArtifactRecord(
                    artifact_id=slug_to_id[section.slug],
                    source_artifact_id=selection.relative_path,
                    kind=selection.artifact_class,
                    title=section_title,
                    phase=selection.phase,
                    phase_zone=selection.phase_zone,
                    workstream=selection.workstream,
                    collaboration_intent=selection.collaboration_intent,
                    relative_path=selection.relative_path,
                    content=section.content,
                    sha256=sha256(section.content.encode("utf-8")).hexdigest(),
                    source_type="section",
                    heading_level=section.heading_level,
                    parent_artifact_id=slug_to_id.get(section.parent_slug) if section.parent_slug else None,
                    section_path=section.path,
                    section_title_path=section.title_path,
                    section_slug=section.node_slug,
                    section_sibling_index=section.sibling_index,
                    lineage_key=section.lineage_key,
                )
            )
        _apply_lineage(current_artifacts, previous_artifacts.get(selection.relative_path, []))
        artifacts.extend(current_artifacts)

    return ArtifactDiscoveryResult(
        artifacts=artifacts,
        selected=selected,
        skipped=skipped,
        missing_required=missing_required,
        warnings=warnings,
    )


class _DiscoveryCandidate:
    __slots__ = (
        "artifact_class",
        "phase",
        "phase_zone",
        "workstream",
        "collaboration_intent",
        "relative_path",
        "source_path",
        "source_variant",
    )

    def __init__(
        self,
        artifact_class: str,
        phase: str,
        phase_zone: str,
        workstream: str,
        collaboration_intent: str,
        relative_path: str,
        source_path: str,
        source_variant: str,
    ) -> None:
        self.artifact_class = artifact_class
        self.phase = phase
        self.phase_zone = phase_zone
        self.workstream = workstream
        self.collaboration_intent = collaboration_intent
        self.relative_path = relative_path
        self.source_path = source_path
        self.source_variant = source_variant


def _collect_candidates(project_root: Path, source_paths: tuple[str, ...]) -> list[_DiscoveryCandidate]:
    candidates: list[_DiscoveryCandidate] = []
    seen_paths: set[str] = set()
    for source_path in source_paths:
        source_root = project_root / source_path
        if not source_root.exists():
            continue
        for path in sorted(source_root.rglob("*.md")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(project_root).as_posix()
            if relative_path in seen_paths:
                continue
            seen_paths.add(relative_path)
            classification = classify_artifact(relative_path)
            candidates.append(
                _DiscoveryCandidate(
                    artifact_class=classification.kind,
                    phase=classification.phase,
                    phase_zone=classification.phase_zone,
                    workstream=classification.workstream,
                    collaboration_intent=classification.collaboration_intent,
                    relative_path=relative_path,
                    source_path=source_path,
                    source_variant=_source_variant(path),
                )
            )
    return candidates


def _select_canonical_candidates(
    candidates: list[_DiscoveryCandidate],
) -> tuple[list[_DiscoveryCandidate], list[DiscoverySkippedCandidate]]:
    canonical: dict[tuple[str, str], _DiscoveryCandidate] = {}
    canonical_order: list[tuple[str, str]] = []
    skipped: list[DiscoverySkippedCandidate] = []

    for candidate in candidates:
        group_key = (candidate.artifact_class, _source_relative_artifact_key(candidate.relative_path, candidate.source_path))
        existing = canonical.get(group_key)
        if existing is None:
            canonical[group_key] = candidate
            canonical_order.append(group_key)
            continue
        if _candidate_priority(candidate) > _candidate_priority(existing):
            skipped.append(_skipped_candidate(existing, candidate))
            canonical[group_key] = candidate
            continue
        skipped.append(_skipped_candidate(candidate, existing))

    return [canonical[key] for key in canonical_order], skipped


def _candidate_priority(candidate: _DiscoveryCandidate) -> int:
    if candidate.source_variant == "whole_document":
        return 1
    return 0


def _skipped_candidate(candidate: _DiscoveryCandidate, selected: _DiscoveryCandidate) -> DiscoverySkippedCandidate:
    if candidate.source_variant == "sharded_index" and selected.source_variant == "whole_document":
        reason = (
            "Skipped sharded index because whole-document source "
            f"{selected.relative_path} exists for artifact class {candidate.artifact_class}."
        )
    else:
        reason = (
            f"Skipped duplicate {_source_variant_label(candidate.source_variant)} because canonical source "
            f"{selected.relative_path} was already selected for artifact class {candidate.artifact_class}."
        )
    return DiscoverySkippedCandidate(
        artifact_class=candidate.artifact_class,
        phase=candidate.phase,
        phase_zone=candidate.phase_zone,
        workstream=candidate.workstream,
        collaboration_intent=candidate.collaboration_intent,
        relative_path=candidate.relative_path,
        source_path=candidate.source_path,
        source_variant=candidate.source_variant,
        reason=reason,
    )


def _source_variant(path: Path) -> str:
    if path.name.lower() == "index.md":
        return "sharded_index"
    return "whole_document"


def _source_variant_label(source_variant: str) -> str:
    if source_variant == "sharded_index":
        return "sharded index"
    return "whole-document source"


def _source_relative_artifact_key(relative_path: str, source_path: str) -> str:
    relative = Path(relative_path)
    source_root = Path(source_path)
    source_relative = relative.relative_to(source_root)
    if source_relative.name.lower() == "index.md":
        return _canonicalize_source_relative_path(source_relative.parent)
    return _canonicalize_source_relative_path(source_relative.with_suffix(""))


def _canonicalize_source_relative_path(path: Path) -> str:
    parts = list(path.parts)
    if not parts:
        return ""
    parts[-1] = canonical_source_name(parts[-1])
    return Path(*parts).as_posix()


def _load_previous_artifacts(
    project_root: Path,
    config: SyncConfig,
    *,
    config_path: str | Path,
) -> dict[str, list[ArtifactRecord]]:
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = (project_root / config_path).resolve()
    else:
        config_path = config_path.resolve()
    manifest_path = (project_root / config.manifest_path).resolve()
    for relative_path in (
        ".bmad-miro-sync/run/plan.json",
        ".bmad-miro-sync/run/publish-bundle.json",
        ".bmad-miro-sync/run/codex-bundle.json",
    ):
        payload = _load_json(project_root / relative_path)
        if payload is None:
            continue
        if not _runtime_payload_matches_contract(
            payload,
            config_path=config_path,
            project_root=project_root,
            manifest_path=manifest_path,
        ):
            continue
        grouped = _group_previous_artifacts(payload.get("artifacts"))
        if grouped:
            return grouped

    manifest = load_manifest(project_root, config.manifest_path)
    return _group_previous_artifacts(manifest.items.values())


def _runtime_payload_matches_contract(
    payload: dict[str, object],
    *,
    config_path: Path,
    project_root: Path,
    manifest_path: Path,
) -> bool:
    payload_config_path = payload.get("config_path")
    if not isinstance(payload_config_path, str) or not payload_config_path:
        return False
    try:
        if Path(payload_config_path).resolve() != config_path:
            return False
    except OSError:
        return False

    payload_manifest_path = payload.get("manifest_path")
    if not isinstance(payload_manifest_path, str) or not payload_manifest_path:
        return False
    try:
        resolved_manifest_path = (project_root / payload_manifest_path).resolve()
    except OSError:
        return False
    return resolved_manifest_path == manifest_path


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _artifact_from_payload(payload: object) -> ArtifactRecord | None:
    if not isinstance(payload, dict):
        return None
    artifact_id = payload.get("artifact_id")
    source_artifact_id = payload.get("source_artifact_id")
    if not artifact_id or not source_artifact_id:
        return None
    classification = classify_artifact(str(payload.get("relative_path", source_artifact_id)))
    artifact_sha256 = payload.get("sha256")
    if artifact_sha256 is None:
        artifact_sha256 = payload.get("artifact_sha256")
    if artifact_sha256 is None:
        artifact_sha256 = payload.get("content_fingerprint")
    try:
        return ArtifactRecord(
            artifact_id=str(artifact_id),
            source_artifact_id=str(source_artifact_id),
            kind=str(payload.get("kind", "document")),
            title=str(payload.get("title", artifact_id)),
            phase=str(payload.get("phase", "planning")),
            phase_zone=str(payload.get("phase_zone", classification.phase_zone)),
            workstream=str(payload.get("workstream", classification.workstream)),
            collaboration_intent=str(payload.get("collaboration_intent", classification.collaboration_intent)),
            relative_path=str(payload.get("relative_path", source_artifact_id)),
            content="",
            sha256=str(artifact_sha256 or ""),
            source_type=str(payload.get("source_type", "section")),
            heading_level=int(payload.get("heading_level", 0) or 0),
            parent_artifact_id=payload.get("parent_artifact_id"),
            section_path=tuple(str(part) for part in payload.get("section_path", ()) or ()),
            section_title_path=tuple(str(part) for part in payload.get("section_title_path", ()) or ()),
            section_slug=str(payload.get("section_slug", "")),
            section_sibling_index=int(payload.get("section_sibling_index", 1) or 1),
            lineage_key=str(payload.get("lineage_key", "")),
            lineage_status=str(payload.get("lineage_status", "new")),
            previous_artifact_id=payload.get("previous_artifact_id"),
            previous_parent_artifact_id=payload.get("previous_parent_artifact_id"),
        )
    except (TypeError, ValueError):
        return None


def _group_previous_artifacts(artifacts_payload: object) -> dict[str, list[ArtifactRecord]]:
    if not isinstance(artifacts_payload, Iterable) or isinstance(artifacts_payload, (str, bytes, dict)):
        return {}
    grouped: dict[str, list[ArtifactRecord]] = defaultdict(list)
    for artifact_payload in artifacts_payload:
        artifact = _artifact_from_payload(artifact_payload)
        if artifact is None:
            continue
        grouped[artifact.source_artifact_id].append(artifact)
    return grouped


def _apply_lineage(current: list[ArtifactRecord], previous: list[ArtifactRecord]) -> None:
    current_by_path = {artifact.section_path: artifact for artifact in current}
    previous_by_id = {artifact.artifact_id: artifact for artifact in previous}
    used_previous_ids: set[str] = set()
    unmatched: list[ArtifactRecord] = []
    previous_by_unchanged_identity: dict[tuple[str, str, int, str | None], list[ArtifactRecord]] = defaultdict(list)

    for artifact in previous:
        previous_by_unchanged_identity[_unchanged_identity_key(artifact)].append(artifact)

    for artifact in current:
        prior = previous_by_id.get(artifact.artifact_id)
        if prior is None or not _exact_identity_matches(artifact, prior):
            unmatched.append(artifact)
            continue
        artifact.lineage_status = "unchanged"
        artifact.previous_artifact_id = prior.artifact_id
        artifact.previous_parent_artifact_id = prior.parent_artifact_id
        used_previous_ids.add(prior.artifact_id)

    for bucket in previous_by_unchanged_identity.values():
        bucket.sort(key=lambda artifact: artifact.artifact_id)

    changed_or_new: list[ArtifactRecord] = []
    for artifact in unmatched:
        prior = _match_unchanged_artifact(artifact, current_by_path, previous_by_unchanged_identity, used_previous_ids)
        if prior is None:
            changed_or_new.append(artifact)
            continue
        artifact.artifact_id = prior.artifact_id
        artifact.lineage_status = "unchanged"
        artifact.previous_artifact_id = prior.artifact_id
        artifact.previous_parent_artifact_id = prior.parent_artifact_id
        used_previous_ids.add(prior.artifact_id)

    remaining_previous = [artifact for artifact in previous if artifact.artifact_id not in used_previous_ids]
    previous_by_lineage_and_level: dict[tuple[str, int], list[ArtifactRecord]] = defaultdict(list)
    previous_by_lineage: dict[str, list[ArtifactRecord]] = defaultdict(list)
    previous_by_parent_and_level: dict[tuple[str | None, int], list[ArtifactRecord]] = defaultdict(list)
    previous_by_slug_and_level: dict[tuple[str, int], list[ArtifactRecord]] = defaultdict(list)
    for artifact in remaining_previous:
        if artifact.lineage_key:
            previous_by_lineage_and_level[(artifact.lineage_key, artifact.heading_level)].append(artifact)
            previous_by_lineage[artifact.lineage_key].append(artifact)
        previous_by_parent_and_level[(artifact.parent_artifact_id, artifact.heading_level)].append(artifact)
        if artifact.section_slug:
            previous_by_slug_and_level[(artifact.section_slug, artifact.heading_level)].append(artifact)

    for bucket in previous_by_lineage_and_level.values():
        bucket.sort(key=lambda artifact: artifact.artifact_id)
    for bucket in previous_by_lineage.values():
        bucket.sort(key=lambda artifact: artifact.artifact_id)
    for bucket in previous_by_parent_and_level.values():
        bucket.sort(key=lambda artifact: artifact.artifact_id)
    for bucket in previous_by_slug_and_level.values():
        bucket.sort(key=lambda artifact: artifact.artifact_id)

    for artifact in changed_or_new:
        prior = _match_previous_artifact(
            artifact,
            current_by_path,
            previous_by_lineage_and_level,
            previous_by_lineage,
            previous_by_parent_and_level,
            previous_by_slug_and_level,
            used_previous_ids,
        )
        if prior is None:
            artifact.lineage_status = "new"
            continue
        artifact.lineage_status = "changed"
        artifact.previous_artifact_id = prior.artifact_id
        artifact.previous_parent_artifact_id = prior.parent_artifact_id
        used_previous_ids.add(prior.artifact_id)

    _refresh_parent_artifact_ids(current)


def _exact_identity_matches(current: ArtifactRecord, previous: ArtifactRecord) -> bool:
    return (
        current.sha256 == previous.sha256
        and current.section_slug == previous.section_slug
        and current.heading_level == previous.heading_level
    )


def _unchanged_identity_key(artifact: ArtifactRecord) -> tuple[str, str, int, str | None]:
    return (
        artifact.sha256,
        artifact.section_slug,
        artifact.heading_level,
        artifact.parent_artifact_id,
    )


def _match_unchanged_artifact(
    artifact: ArtifactRecord,
    current_by_path: dict[tuple[str, ...], ArtifactRecord],
    previous_by_unchanged_identity: dict[tuple[str, str, int, str | None], list[ArtifactRecord]],
    used_previous_ids: set[str],
) -> ArtifactRecord | None:
    bucket = previous_by_unchanged_identity.get(_current_unchanged_identity_key(artifact, current_by_path), [])
    for candidate in bucket:
        if candidate.artifact_id not in used_previous_ids:
            return candidate
    return None


def _current_unchanged_identity_key(
    artifact: ArtifactRecord,
    current_by_path: dict[tuple[str, ...], ArtifactRecord],
) -> tuple[str, str, int, str | None]:
    parent_artifact_id = None
    if len(artifact.section_path) > 1:
        parent = current_by_path.get(artifact.section_path[:-1])
        if parent is not None:
            parent_artifact_id = parent.artifact_id
    return (
        artifact.sha256,
        artifact.section_slug,
        artifact.heading_level,
        parent_artifact_id,
    )


def _match_previous_artifact(
    artifact: ArtifactRecord,
    current_by_path: dict[tuple[str, ...], ArtifactRecord],
    previous_by_lineage_and_level: dict[tuple[str, int], list[ArtifactRecord]],
    previous_by_lineage: dict[str, list[ArtifactRecord]],
    previous_by_parent_and_level: dict[tuple[str | None, int], list[ArtifactRecord]],
    previous_by_slug_and_level: dict[tuple[str, int], list[ArtifactRecord]],
    used_previous_ids: set[str],
) -> ArtifactRecord | None:
    if artifact.lineage_key:
        exact_bucket = previous_by_lineage_and_level.get((artifact.lineage_key, artifact.heading_level), [])
        for candidate in exact_bucket:
            if candidate.artifact_id not in used_previous_ids:
                return candidate

        loose_bucket = previous_by_lineage.get(artifact.lineage_key, [])
        for candidate in loose_bucket:
            if candidate.artifact_id not in used_previous_ids:
                return candidate

    parent_bucket = previous_by_parent_and_level.get(
        (_current_parent_lineage_id(artifact, current_by_path), artifact.heading_level),
        [],
    )
    parent_candidate = _single_unused_candidate(parent_bucket, used_previous_ids)
    if parent_candidate is not None:
        return parent_candidate

    slug_bucket = previous_by_slug_and_level.get((artifact.section_slug, artifact.heading_level), [])
    slug_candidate = _single_unused_candidate(slug_bucket, used_previous_ids)
    if slug_candidate is not None:
        return slug_candidate

    return None


def _refresh_parent_artifact_ids(artifacts: list[ArtifactRecord]) -> None:
    artifact_ids_by_path = {artifact.section_path: artifact.artifact_id for artifact in artifacts}
    for artifact in artifacts:
        if len(artifact.section_path) > 1:
            artifact.parent_artifact_id = artifact_ids_by_path.get(artifact.section_path[:-1])
        else:
            artifact.parent_artifact_id = None


def _current_parent_lineage_id(
    artifact: ArtifactRecord,
    current_by_path: dict[tuple[str, ...], ArtifactRecord],
) -> str | None:
    if len(artifact.section_path) <= 1:
        return None
    parent = current_by_path.get(artifact.section_path[:-1])
    if parent is None:
        return None
    return parent.previous_artifact_id or parent.artifact_id


def _single_unused_candidate(
    candidates: list[ArtifactRecord],
    used_previous_ids: set[str],
) -> ArtifactRecord | None:
    unused = [candidate for candidate in candidates if candidate.artifact_id not in used_previous_ids]
    if len(unused) != 1:
        return None
    return unused[0]
