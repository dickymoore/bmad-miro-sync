from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
from pathlib import Path
import re

from .classifier import phase_zone_rank, workstream_rank
from .config import SyncConfig
from .discovery import discover_artifacts
from .manifest import load_manifest
from .models import ArtifactRecord, DeterministicOrder, ObjectStrategyDecision, PublishOperation, SyncPlan


PHASE_FLAGS = {
    "analysis": "publish_analysis",
    "planning": "publish_planning",
    "solutioning": "publish_solutioning",
    "implementation": "publish_implementation",
}

ZONE_TITLES = {
    "analysis": "Analysis",
    "planning": "Planning",
    "solutioning": "Solutioning",
    "implementation_readiness": "Implementation Readiness",
    "delivery_feedback": "Delivery Feedback",
}

WORKSTREAM_TITLES = {
    "product": "Product",
    "ux": "UX",
    "architecture": "Architecture",
    "delivery": "Delivery",
    "general": "General",
}

_CONTENT_ITEM_TYPES = {"doc", "table"}
_TERMINAL_LIFECYCLE_STATES = {"archived", "removed"}
_RETIRED_ARTIFACT_MARKER = "::retired::"
_PRESERVE_LAYOUT_ACTIONS = {"update_doc", "update_table", "skip"}
_OBJECT_FAMILY_ARTIFACT_CONTENT = "artifact_content"
_OBJECT_FAMILY_PHASE_ZONE = "phase_zone_scaffolding"
_OBJECT_FAMILY_STORY_SUMMARY = "story_summary"
_OBJECT_FAMILY_WORKSTREAM = "workstream_anchor"
_MAX_DOC_HTML_CHARS = 5800
_OVERSIZE_DOC_FALLBACK_REASON = (
    "Section content exceeded Miro's text-item size limit and was split into sequenced fragments."
)


@dataclass(slots=True, frozen=True)
class _SummaryTable:
    columns: list[dict[str, str]]
    rows: list[dict[str, list[dict[str, str]]]]


@dataclass(slots=True, frozen=True)
class _ResolvedArtifactOperation:
    item_type: str
    columns: list[dict[str, str]] | None
    rows: list[dict[str, list[dict[str, str]]]] | None
    strategy: ObjectStrategyDecision


def build_sync_plan(
    project_root: str | Path,
    config_path: str | Path,
    config: SyncConfig,
) -> SyncPlan:
    root = Path(project_root)
    discovery = discover_artifacts(root, config, config_path=config_path)
    manifest = load_manifest(root, config.manifest_path)
    object_strategies = _resolve_object_strategies(config)

    plan = SyncPlan(
        board_url=config.board_url,
        project_root=str(root),
        config_path=str(Path(config_path)),
        manifest_path=config.manifest_path,
        artifacts=discovery.artifacts,
        discovery=discovery.to_report(),
        object_strategies=list(object_strategies.values()),
    )
    plan.warnings.extend(discovery.warnings)

    if not discovery.artifacts:
        if _has_active_content_items(manifest):
            plan.warnings.append("No markdown artifacts were discovered, so the plan only contains retirements for previously synced content.")
            artifacts: list[ArtifactRecord] = []
        else:
            if not discovery.selected:
                joined_paths = ", ".join(config.source_paths)
                plan.warnings.append(f"No markdown artifacts found under configured discovery source paths: {joined_paths}.")
            else:
                plan.warnings.append("No reviewable markdown sections found in the selected discovery sources.")
            return plan
    else:
        artifacts = _enabled_artifacts(discovery.artifacts, config)
        if not artifacts:
            if not discovery.selected:
                joined_paths = ", ".join(config.source_paths)
                plan.warnings.append(f"No markdown artifacts found under configured discovery source paths: {joined_paths}.")
            else:
                plan.warnings.append("No reviewable markdown sections found in the selected discovery sources.")
            plan.warnings.append("Configured publish flags filtered every discovered artifact out of the board plan.")
            return plan

    ordered_artifacts = _expand_oversized_doc_artifacts(_sort_artifacts(artifacts), config, object_strategies, plan.warnings)
    plan.artifacts = ordered_artifacts
    used_zones = _ordered_unique([artifact.phase_zone for artifact in ordered_artifacts])
    used_workstreams = _ordered_unique((artifact.phase_zone, artifact.workstream) for artifact in ordered_artifacts)
    artifact_ranks = _artifact_ranks(ordered_artifacts)
    section_ranks = _section_ranks(ordered_artifacts)
    handled_manifest_ids: set[str] = set()
    replacement_operations: list[PublishOperation] = []

    if config.create_phase_frames:
        zone_strategy = object_strategies[_OBJECT_FAMILY_PHASE_ZONE]
        for phase_zone in used_zones:
            plan.operations.append(
                PublishOperation(
                    op_id=f"zone:{phase_zone}",
                    action="ensure_zone",
                    item_type="zone",
                    title=ZONE_TITLES.get(phase_zone, phase_zone.replace("_", " ").title()),
                    phase=_zone_phase(phase_zone),
                    phase_zone=phase_zone,
                    workstream="general",
                    collaboration_intent="orientation",
                    artifact_id=f"zone:{phase_zone}",
                    source_artifact_id=f"zone:{phase_zone}",
                    target_key=f"zone:{phase_zone}",
                    object_family=zone_strategy.object_family,
                    preferred_item_type=zone_strategy.preferred_item_type,
                    resolved_item_type=zone_strategy.resolved_item_type,
                    degraded=zone_strategy.degraded,
                    fallback_reason=zone_strategy.fallback_reason,
                    degraded_warning=zone_strategy.degraded_warning,
                    status="pending",
                    deterministic_order=DeterministicOrder(
                        zone_rank=phase_zone_rank(phase_zone),
                        workstream_rank=0,
                        object_rank=0,
                    ),
                )
            )

    for phase_zone, workstream in used_workstreams:
        workstream_strategy = _workstream_strategy()
        plan.operations.append(
            PublishOperation(
                op_id=f"workstream:{phase_zone}:{workstream}",
                action="ensure_workstream_anchor",
                item_type="workstream_anchor",
                title=WORKSTREAM_TITLES.get(workstream, workstream.title()),
                phase=_zone_phase(phase_zone),
                phase_zone=phase_zone,
                workstream=workstream,
                collaboration_intent="orientation",
                artifact_id=f"workstream:{phase_zone}:{workstream}",
                source_artifact_id=f"workstream:{phase_zone}:{workstream}",
                target_key=f"workstream:{phase_zone}:{workstream}",
                container_target_key=f"zone:{phase_zone}" if config.create_phase_frames else None,
                object_family=workstream_strategy.object_family,
                preferred_item_type=workstream_strategy.preferred_item_type,
                resolved_item_type=workstream_strategy.resolved_item_type,
                degraded=workstream_strategy.degraded,
                fallback_reason=workstream_strategy.fallback_reason,
                degraded_warning=workstream_strategy.degraded_warning,
                status="pending",
                deterministic_order=DeterministicOrder(
                    zone_rank=phase_zone_rank(phase_zone),
                    workstream_rank=workstream_rank(workstream),
                    object_rank=1,
                ),
            )
        )

    for artifact in ordered_artifacts:
        existing_item, reused_previous_identity = _resolve_existing_item(manifest, artifact)
        resolved_operation = _resolve_artifact_operation(artifact, config, object_strategies)
        operation_strategy = _artifact_operation_strategy(resolved_operation.strategy, artifact)
        item_type = resolved_operation.item_type
        action, status = _resolve_content_action(existing_item, reused_previous_identity, artifact.sha256, item_type)
        columns = resolved_operation.columns
        rows = resolved_operation.rows
        reusable_existing_item = _matching_existing_item(existing_item, item_type)
        if reusable_existing_item is not None:
            handled_manifest_ids.add(reusable_existing_item["artifact_id"])
        elif existing_item is not None:
            handled_manifest_ids.add(existing_item["artifact_id"])
            replacement_operations.append(
                _build_replacement_operation(
                    existing_item,
                    config.removed_item_policy,
                    strategy=resolved_operation.strategy,
                )
            )

        plan.operations.append(
            PublishOperation(
                op_id=f"{item_type}:{artifact.artifact_id}",
                action=action,
                item_type=item_type,
                title=artifact.title,
                phase=artifact.phase,
                phase_zone=artifact.phase_zone,
                workstream=artifact.workstream,
                collaboration_intent=artifact.collaboration_intent,
                artifact_id=artifact.artifact_id,
                source_artifact_id=artifact.source_artifact_id,
                target_key=f"artifact:{artifact.artifact_id}",
                container_target_key=_content_container_target_key(
                    action,
                    artifact.phase_zone,
                    artifact.workstream,
                    reusable_existing_item,
                ),
                content=artifact.content if item_type == "doc" else None,
                columns=columns,
                rows=rows,
                existing_item=reusable_existing_item,
                layout_policy=_content_layout_policy(action, reusable_existing_item),
                layout_snapshot=_layout_snapshot(reusable_existing_item) if action in _PRESERVE_LAYOUT_ACTIONS else None,
                object_family=operation_strategy.object_family,
                preferred_item_type=operation_strategy.preferred_item_type,
                resolved_item_type=operation_strategy.resolved_item_type,
                degraded=operation_strategy.degraded,
                fallback_reason=operation_strategy.fallback_reason,
                degraded_warning=operation_strategy.degraded_warning,
                status=status,
                lifecycle_state="active",
                heading_level=artifact.heading_level,
                parent_artifact_id=artifact.parent_artifact_id,
                deterministic_order=DeterministicOrder(
                    zone_rank=phase_zone_rank(artifact.phase_zone),
                    workstream_rank=workstream_rank(artifact.workstream),
                    object_rank=2,
                    artifact_rank=artifact_ranks[(artifact.phase_zone, artifact.workstream, artifact.source_artifact_id)],
                    section_rank=section_ranks[(artifact.source_artifact_id, artifact.artifact_id)],
                ),
            )
        )

    plan.operations.extend(replacement_operations)

    for missing_item in _sorted_missing_manifest_items(manifest, handled_manifest_ids):
        action, lifecycle_state = _resolve_removed_item_action(config.removed_item_policy, missing_item["item_type"])
        plan.operations.append(
            PublishOperation(
                op_id=f"{missing_item['item_type']}:{missing_item['artifact_id']}",
                action=action,
                item_type=missing_item["item_type"],
                title=missing_item.get("title") or missing_item["artifact_id"],
                phase=missing_item.get("phase") or _zone_phase(missing_item.get("phase_zone", "planning")),
                phase_zone=missing_item.get("phase_zone", "planning"),
                workstream=missing_item.get("workstream", "general"),
                collaboration_intent=missing_item.get("collaboration_intent", "anchor"),
                artifact_id=missing_item["artifact_id"],
                source_artifact_id=missing_item.get("source_artifact_id") or missing_item["artifact_id"],
                target_key=missing_item.get("target_key") or f"artifact:{missing_item['artifact_id']}",
                container_target_key=missing_item.get("container_target_key"),
                existing_item=missing_item,
                object_family=missing_item.get("object_family") or _OBJECT_FAMILY_ARTIFACT_CONTENT,
                preferred_item_type=missing_item.get("preferred_item_type") or missing_item["item_type"],
                resolved_item_type=missing_item.get("resolved_item_type") or missing_item["item_type"],
                degraded=bool(missing_item.get("degraded", False)),
                fallback_reason=missing_item.get("fallback_reason"),
                degraded_warning=missing_item.get("degraded_warning"),
                status="pending",
                lifecycle_state=lifecycle_state,
                removal_policy=config.removed_item_policy,
                heading_level=int(missing_item.get("heading_level", 0) or 0),
                parent_artifact_id=missing_item.get("parent_artifact_id"),
                deterministic_order=DeterministicOrder(
                    zone_rank=phase_zone_rank(missing_item.get("phase_zone", "planning")),
                    workstream_rank=workstream_rank(missing_item.get("workstream", "general")),
                    object_rank=3,
                ),
            )
        )

    plan.warnings.extend(_plan_object_strategy_warnings(plan.operations, object_strategies, used_zones=used_zones))
    return plan


def _enabled_artifacts(artifacts: list[ArtifactRecord], config: SyncConfig) -> list[ArtifactRecord]:
    enabled: list[ArtifactRecord] = []
    for artifact in artifacts:
        if getattr(config, PHASE_FLAGS.get(artifact.phase, "publish_planning"), True):
            enabled.append(artifact)
    return enabled


def _sort_artifacts(artifacts: list[ArtifactRecord]) -> list[ArtifactRecord]:
    return sorted(
        artifacts,
        key=lambda artifact: (
            phase_zone_rank(artifact.phase_zone),
            workstream_rank(artifact.workstream),
        ),
    )


def _expand_oversized_doc_artifacts(
    artifacts: list[ArtifactRecord],
    config: SyncConfig,
    object_strategies: dict[str, ObjectStrategyDecision],
    warnings: list[str],
) -> list[ArtifactRecord]:
    expanded: list[ArtifactRecord] = []

    for artifact in artifacts:
        resolved_operation = _resolve_artifact_operation(artifact, config, object_strategies)
        if resolved_operation.item_type != "doc":
            expanded.append(artifact)
            continue
        rendered_html_length = len(_markdown_to_simple_html(artifact.content))
        if rendered_html_length <= _MAX_DOC_HTML_CHARS:
            expanded.append(artifact)
            continue
        fragments = _split_oversized_doc_artifact(artifact)
        expanded.extend(fragments)
        warnings.append(
            f'Section "{artifact.title}" exceeded Miro text content limits ({rendered_html_length} rendered HTML chars) '
            f"and was split into {len(fragments)} sequenced fragments."
        )

    return expanded


def _ordered_unique(values: list[str] | list[tuple[str, str]]) -> list[str] | list[tuple[str, str]]:
    ordered: list[str] | list[tuple[str, str]] = []
    seen: set[str] | set[tuple[str, str]] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _artifact_ranks(artifacts: list[ArtifactRecord]) -> dict[tuple[str, str, str], int]:
    ranks: dict[tuple[str, str, str], int] = {}
    seen: list[tuple[str, str, str]] = []
    for artifact in artifacts:
        key = (artifact.phase_zone, artifact.workstream, artifact.source_artifact_id)
        if key in ranks:
            continue
        ranks[key] = len(seen)
        seen.append(key)
    return ranks


def _section_ranks(artifacts: list[ArtifactRecord]) -> dict[tuple[str, str], int]:
    ranks: dict[tuple[str, str], int] = {}
    per_source_counts: dict[str, int] = {}
    for artifact in artifacts:
        count = per_source_counts.get(artifact.source_artifact_id, 0)
        ranks[(artifact.source_artifact_id, artifact.artifact_id)] = count
        per_source_counts[artifact.source_artifact_id] = count + 1
    return ranks


def _has_active_content_items(manifest) -> bool:
    return any(
        item.get("item_type") in _CONTENT_ITEM_TYPES
        and item.get("lifecycle_state", "active") not in _TERMINAL_LIFECYCLE_STATES
        for item in manifest.items.values()
    )


def _resolve_existing_item(manifest, artifact: ArtifactRecord) -> tuple[dict | None, bool]:
    existing_item = manifest.items.get(artifact.artifact_id)
    if not _is_reusable_existing_item(existing_item):
        existing_item = None
    reused_previous_identity = False
    if existing_item is None and artifact.previous_artifact_id:
        previous_item = manifest.items.get(artifact.previous_artifact_id)
        existing_item = previous_item if _is_reusable_existing_item(previous_item) else None
        reused_previous_identity = existing_item is not None
    return existing_item, reused_previous_identity


def _resolve_content_action(
    existing_item: dict | None,
    reused_previous_identity: bool,
    artifact_sha256: str,
    item_type: str,
) -> tuple[str, str]:
    if (
        existing_item
        and not reused_previous_identity
        and existing_item.get("item_type") == item_type
        and existing_item.get("artifact_sha256") == artifact_sha256
    ):
        return "skip", "unchanged"
    if existing_item and existing_item.get("item_type") == item_type:
        return f"update_{item_type}", "pending"
    return f"create_{item_type}", "pending"


def _is_reusable_existing_item(existing_item: dict | None) -> bool:
    if existing_item is None:
        return False
    return existing_item.get("lifecycle_state", "active") not in _TERMINAL_LIFECYCLE_STATES


def _matching_existing_item(existing_item: dict | None, item_type: str) -> dict | None:
    if existing_item is None:
        return None
    if existing_item.get("item_type") != item_type:
        return None
    return existing_item


def _content_layout_policy(action: str, existing_item: dict | None) -> str | None:
    if action in _PRESERVE_LAYOUT_ACTIONS and existing_item is not None:
        return "preserve"
    if action.startswith("create_"):
        return "auto"
    return None


def _content_container_target_key(
    action: str,
    phase_zone: str,
    workstream: str,
    existing_item: dict | None,
) -> str:
    if action in _PRESERVE_LAYOUT_ACTIONS and existing_item is not None:
        existing_target = existing_item.get("container_target_key")
        if existing_target:
            return existing_target
    return f"workstream:{phase_zone}:{workstream}"


def _layout_snapshot(existing_item: dict | None) -> dict | None:
    if existing_item is None:
        return None
    snapshot = existing_item.get("layout_snapshot")
    if not isinstance(snapshot, dict):
        return None
    return dict(snapshot)


def _sorted_missing_manifest_items(manifest, claimed_manifest_ids: set[str]) -> list[dict]:
    items: list[dict] = []
    for artifact_id, item in manifest.items.items():
        if artifact_id in claimed_manifest_ids:
            continue
        if item.get("item_type") not in _CONTENT_ITEM_TYPES:
            continue
        if item.get("lifecycle_state", "active") in _TERMINAL_LIFECYCLE_STATES:
            continue
        items.append(item)
    return sorted(
        items,
        key=lambda item: (
            phase_zone_rank(item.get("phase_zone", "planning")),
            workstream_rank(item.get("workstream", "general")),
            item.get("source_artifact_id", item["artifact_id"]),
            item["artifact_id"],
        ),
    )


def _resolve_removed_item_action(policy: str, item_type: str) -> tuple[str, str]:
    if policy == "remove":
        return f"remove_{item_type}", "removed"
    return f"archive_{item_type}", "archived"


def _build_replacement_operation(
    existing_item: dict,
    policy: str,
    *,
    strategy: ObjectStrategyDecision | None = None,
) -> PublishOperation:
    artifact_id = _retired_artifact_id(existing_item)
    action, lifecycle_state = _resolve_removed_item_action(policy, existing_item["item_type"])
    phase_zone = existing_item.get("phase_zone", "planning")
    workstream = existing_item.get("workstream", "general")
    operation_strategy = strategy or ObjectStrategyDecision(
        object_family=existing_item.get("object_family") or _OBJECT_FAMILY_ARTIFACT_CONTENT,
        preferred_item_type=existing_item.get("preferred_item_type") or existing_item["item_type"],
        resolved_item_type=existing_item.get("resolved_item_type") or existing_item["item_type"],
        degraded=bool(existing_item.get("degraded", False)),
        fallback_reason=existing_item.get("fallback_reason"),
        degraded_warning=existing_item.get("degraded_warning"),
    )
    return PublishOperation(
        op_id=f"{existing_item['item_type']}:{artifact_id}",
        action=action,
        item_type=existing_item["item_type"],
        title=existing_item.get("title") or existing_item["artifact_id"],
        phase=existing_item.get("phase") or _zone_phase(phase_zone),
        phase_zone=phase_zone,
        workstream=workstream,
        collaboration_intent=existing_item.get("collaboration_intent", "anchor"),
        artifact_id=artifact_id,
        source_artifact_id=existing_item.get("source_artifact_id") or existing_item["artifact_id"],
        target_key=f"retired:{existing_item.get('target_key') or existing_item['artifact_id']}",
        container_target_key=existing_item.get("container_target_key"),
        existing_item=existing_item,
        object_family=operation_strategy.object_family,
        preferred_item_type=operation_strategy.preferred_item_type,
        resolved_item_type=operation_strategy.resolved_item_type,
        degraded=operation_strategy.degraded,
        fallback_reason=operation_strategy.fallback_reason,
        degraded_warning=operation_strategy.degraded_warning,
        status="pending",
        lifecycle_state=lifecycle_state,
        removal_policy=policy,
        heading_level=int(existing_item.get("heading_level", 0) or 0),
        parent_artifact_id=existing_item.get("parent_artifact_id"),
        deterministic_order=DeterministicOrder(
            zone_rank=phase_zone_rank(phase_zone),
            workstream_rank=workstream_rank(workstream),
            object_rank=3,
        ),
    )


def _retired_artifact_id(existing_item: dict) -> str:
    return f"{existing_item['artifact_id']}{_RETIRED_ARTIFACT_MARKER}{existing_item['item_type']}"


def _resolve_object_strategies(config: SyncConfig) -> dict[str, ObjectStrategyDecision]:
    strategies: dict[str, ObjectStrategyDecision] = {
        _OBJECT_FAMILY_PHASE_ZONE: ObjectStrategyDecision(
            object_family=_OBJECT_FAMILY_PHASE_ZONE,
            preferred_item_type="zone",
            resolved_item_type=config.object_strategies.phase_zone,
            degraded=config.object_strategies.phase_zone != "zone",
            fallback_reason=(
                "Configured object strategy resolved phase-zone scaffolding to workstream anchors."
                if config.object_strategies.phase_zone != "zone"
                else None
            ),
            degraded_warning=(
                "Preferred phase-zone containers are unavailable; workstream anchors will carry orientation without separate zone objects."
                if config.object_strategies.phase_zone != "zone"
                else None
            ),
        ),
        _OBJECT_FAMILY_STORY_SUMMARY: ObjectStrategyDecision(
            object_family=_OBJECT_FAMILY_STORY_SUMMARY,
            preferred_item_type="table",
            resolved_item_type=config.object_strategies.story_summary,
            degraded=config.object_strategies.story_summary != "table",
            fallback_reason=(
                "Configured object strategy resolved story summaries to docs."
                if config.object_strategies.story_summary != "table"
                else None
            ),
            degraded_warning=(
                "Preferred story summary tables are unavailable; story summaries will be published as readable docs."
                if config.object_strategies.story_summary != "table"
                else None
            ),
        ),
    }
    return strategies


def _split_oversized_doc_artifact(artifact: ArtifactRecord) -> list[ArtifactRecord]:
    heading_prefix = "#" * max(int(artifact.heading_level or 0), 1)
    body = _content_body_without_heading(artifact.content)
    parts = _split_markdown_body_to_fit(body, artifact.title, heading_prefix)
    source_digest = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()[:12]
    fragments: list[ArtifactRecord] = []
    total_parts = len(parts)

    for index, part_body in enumerate(parts, start=1):
        part_title = f"{artifact.title} ({index}/{total_parts})"
        part_slug = f"{artifact.section_slug or 'section'}-part-{index}"
        content = _fragment_markdown_content(heading_prefix, part_title, part_body)
        fragments.append(
            ArtifactRecord(
                artifact_id=f"{artifact.artifact_id}::part-{index}",
                source_artifact_id=artifact.source_artifact_id,
                kind=artifact.kind,
                title=part_title,
                phase=artifact.phase,
                phase_zone=artifact.phase_zone,
                workstream=artifact.workstream,
                collaboration_intent=artifact.collaboration_intent,
                relative_path=artifact.relative_path,
                content=content,
                sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                source_type=artifact.source_type,
                heading_level=artifact.heading_level,
                parent_artifact_id=artifact.parent_artifact_id,
                section_path=tuple(artifact.section_path) + (part_slug,),
                section_title_path=tuple(artifact.section_title_path) + (part_title,),
                section_slug=part_slug,
                section_sibling_index=index,
                lineage_key=f"{artifact.lineage_key or artifact.artifact_id}::split::{source_digest}::{index}",
                lineage_status="split",
                previous_artifact_id=None,
                previous_parent_artifact_id=artifact.previous_parent_artifact_id,
            )
        )

    return fragments


def _content_body_without_heading(content: str) -> str:
    lines = content.splitlines()
    started = False
    for index, line in enumerate(lines):
        if not started and not line.strip():
            continue
        started = True
        if line.lstrip().startswith("#"):
            return "\n".join(lines[index + 1 :]).strip()
        break
    return content.strip()


def _fragment_markdown_content(heading_prefix: str, title: str, body: str) -> str:
    heading_line = f"{heading_prefix} {title}".strip()
    body = body.strip()
    if not body:
        return heading_line + "\n"
    return f"{heading_line}\n\n{body}\n"


def _split_markdown_body_to_fit(body: str, title: str, heading_prefix: str) -> list[str]:
    remaining = body.strip()
    if not remaining:
        return [""]

    chunks: list[str] = []
    while remaining:
        candidate = _fragment_markdown_content(heading_prefix, title, remaining)
        if len(_markdown_to_simple_html(candidate)) <= _MAX_DOC_HTML_CHARS:
            chunks.append(remaining.strip())
            break

        split_at = _largest_fitting_prefix_index(remaining, title=title, heading_prefix=heading_prefix)
        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[: max(1, min(len(remaining), 512))].rstrip()
            split_at = len(chunk)
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    return chunks


def _largest_fitting_prefix_index(content: str, *, title: str, heading_prefix: str) -> int:
    current = ""
    current_end = 0
    for block, end_index in _split_candidates(content):
        proposal = f"{current}\n\n{block}".strip() if current else block
        if len(_markdown_to_simple_html(_fragment_markdown_content(heading_prefix, title, proposal))) <= _MAX_DOC_HTML_CHARS:
            current = proposal
            current_end = end_index
            continue
        if current:
            return current_end
        return _largest_fitting_line_prefix_index(block, content, end_index, title=title, heading_prefix=heading_prefix)
    return len(content)


def _largest_fitting_line_prefix_index(
    block: str,
    source_content: str,
    block_end_index: int,
    *,
    title: str,
    heading_prefix: str,
) -> int:
    current = ""
    consumed = 0
    for line in block.splitlines(keepends=True):
        proposal = current + line
        if len(_markdown_to_simple_html(_fragment_markdown_content(heading_prefix, title, proposal))) <= _MAX_DOC_HTML_CHARS:
            current = proposal
            consumed += len(line)
            continue
        if current:
            return block_end_index - len(block) + consumed
        return _largest_fitting_word_prefix_index(
            line,
            source_content,
            block_end_index - len(block),
            title=title,
            heading_prefix=heading_prefix,
        )
    return block_end_index


def _largest_fitting_word_prefix_index(
    line: str,
    source_content: str,
    block_start_index: int,
    *,
    title: str,
    heading_prefix: str,
) -> int:
    current = ""
    consumed = 0
    for match in re.finditer(r"\S+\s*", line):
        token = match.group(0)
        proposal = current + token
        if len(_markdown_to_simple_html(_fragment_markdown_content(heading_prefix, title, proposal))) <= _MAX_DOC_HTML_CHARS:
            current = proposal
            consumed = match.end()
            continue
        if current:
            return block_start_index + consumed
    return block_start_index + max(1, min(len(line), 512))


def _split_candidates(content: str) -> list[tuple[str, int]]:
    parts: list[tuple[str, int]] = []
    last_index = 0
    for match in re.finditer(r"(?:\n\s*\n)+", content):
        chunk = content[last_index:match.start()].strip()
        if chunk:
            parts.append((chunk, match.start()))
        last_index = match.end()
    tail = content[last_index:].strip()
    if tail:
        parts.append((tail, len(content)))
    return parts


def _plan_object_strategy_warnings(
    operations: list[PublishOperation],
    object_strategies: dict[str, ObjectStrategyDecision],
    *,
    used_zones: list[str],
) -> list[str]:
    warnings: list[str] = []

    zone_strategy = object_strategies.get(_OBJECT_FAMILY_PHASE_ZONE)
    if used_zones and zone_strategy and zone_strategy.degraded and zone_strategy.degraded_warning:
        warnings.append(zone_strategy.degraded_warning)

    for operation in operations:
        warning = operation.degraded_warning
        if warning and warning not in warnings:
            warnings.append(warning)
    return warnings


def _workstream_strategy() -> ObjectStrategyDecision:
    return ObjectStrategyDecision(
        object_family=_OBJECT_FAMILY_WORKSTREAM,
        preferred_item_type="workstream_anchor",
        resolved_item_type="workstream_anchor",
    )


def _default_item_strategy(item_type: str) -> ObjectStrategyDecision:
    return ObjectStrategyDecision(
        object_family=_OBJECT_FAMILY_ARTIFACT_CONTENT,
        preferred_item_type=item_type,
        resolved_item_type=item_type,
    )


def _artifact_operation_strategy(
    base_strategy: ObjectStrategyDecision,
    artifact: ArtifactRecord,
) -> ObjectStrategyDecision:
    if artifact.lineage_status != "split":
        return base_strategy
    return ObjectStrategyDecision(
        object_family=base_strategy.object_family,
        preferred_item_type=base_strategy.preferred_item_type,
        resolved_item_type=base_strategy.resolved_item_type,
        degraded=True,
        fallback_reason=_OVERSIZE_DOC_FALLBACK_REASON,
        degraded_warning=_OVERSIZE_DOC_FALLBACK_REASON,
    )


def _resolve_artifact_operation(
    artifact: ArtifactRecord,
    config: SyncConfig,
    object_strategies: dict[str, ObjectStrategyDecision],
) -> _ResolvedArtifactOperation:
    summary_table = _summary_table_for_artifact(artifact)
    if summary_table is None:
        return _ResolvedArtifactOperation(
            item_type="doc",
            columns=None,
            rows=None,
            strategy=_default_item_strategy("doc"),
        )

    if artifact.kind == "story":
        strategy = object_strategies[_OBJECT_FAMILY_STORY_SUMMARY]
        if strategy.resolved_item_type == "doc":
            return _ResolvedArtifactOperation(
                item_type="doc",
                columns=None,
                rows=None,
                strategy=strategy,
            )
        return _ResolvedArtifactOperation(
            item_type="table",
            columns=summary_table.columns,
            rows=summary_table.rows,
            strategy=strategy,
        )

    return _ResolvedArtifactOperation(
        item_type="table",
        columns=summary_table.columns,
        rows=summary_table.rows,
        strategy=_default_item_strategy("table"),
    )


def _summary_table_for_artifact(artifact: ArtifactRecord) -> _SummaryTable | None:
    if artifact.parent_artifact_id is not None:
        return None
    if artifact.collaboration_intent != "summary":
        return None
    return _extract_summary_table(artifact.content)


def _extract_summary_table(content: str) -> _SummaryTable | None:
    checklist_rows = _extract_checklist_rows(content)
    if len(checklist_rows) >= 2:
        return _SummaryTable(
            columns=[
                {"column_type": "text", "column_title": "Task"},
                {"column_type": "text", "column_title": "Status"},
            ],
            rows=[
                {
                    "cells": [
                        {"columnTitle": "Task", "value": row["Task"]},
                        {"columnTitle": "Status", "value": row["Status"]},
                    ]
                }
                for row in checklist_rows
            ],
        )

    kv_rows = _extract_key_value_rows(content)
    if len(kv_rows) >= 2:
        return _SummaryTable(
            columns=[
                {"column_type": "text", "column_title": "Field"},
                {"column_type": "text", "column_title": "Value"},
            ],
            rows=[
                {
                    "cells": [
                        {"columnTitle": "Field", "value": row["Field"]},
                        {"columnTitle": "Value", "value": row["Value"]},
                    ]
                }
                for row in kv_rows
            ],
        )

    bullet_rows = _extract_bullet_rows(content)
    if len(bullet_rows) >= 3:
        return _SummaryTable(
            columns=[{"column_type": "text", "column_title": "Item"}],
            rows=[
                {
                    "cells": [
                        {"columnTitle": "Item", "value": row},
                    ]
                }
                for row in bullet_rows
            ],
        )

    return None


def _extract_checklist_rows(content: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in content.splitlines():
        match = re.match(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+(?P<task>.+?)\s*$", line)
        if match is None:
            continue
        rows.append(
            {
                "Task": match.group("task"),
                "Status": "Done" if match.group("state").strip().lower() == "x" else "Open",
            }
        )
    return rows


def _extract_key_value_rows(content: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_html_comment = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if in_html_comment:
            if "-->" in stripped:
                in_html_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_html_comment = True
            continue
        if stripped.startswith(("-", "*")):
            continue
        if ":" not in stripped:
            continue
        field, value = stripped.split(":", 1)
        field = field.strip()
        value = value.strip()
        if not field or not value:
            continue
        rows.append({"Field": field, "Value": value})
    return rows


def _extract_bullet_rows(content: str) -> list[str]:
    rows: list[str] = []
    for line in content.splitlines():
        match = re.match(r"^\s*(?:[-*]|\d+\.)\s+(?P<item>.+?)\s*$", line)
        if match is None:
            continue
        if "[" in match.group("item") and "]" in match.group("item"):
            continue
        rows.append(match.group("item"))
    return rows


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


def _zone_phase(phase_zone: str) -> str:
    if phase_zone in {"implementation_readiness", "delivery_feedback"}:
        return "implementation"
    return phase_zone
