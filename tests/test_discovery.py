from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from bmad_miro_sync.config import load_config
from bmad_miro_sync.discovery import discover_artifacts
from bmad_miro_sync.host_exports import write_json
from bmad_miro_sync.manifest import apply_results, load_manifest, save_manifest
from bmad_miro_sync.planner import build_sync_plan


CONFIG_WITH_DISCOVERY = """
board_url = "https://miro.com/app/board/uXjVGixS6vQ=/"
source_root = "_bmad-output"
manifest_path = ".bmad-miro-sync/state.json"

[discovery]
source_paths = [
  "_bmad-output/planning-artifacts",
  "_bmad-output/implementation-artifacts",
]
required_artifact_classes = ["prd", "ux_design"]

[layout]
create_phase_frames = true

[publish]
analysis = true
planning = true
solutioning = true
implementation = true
stories_table = true
"""


LEGACY_CONFIG = """
board_url = "https://miro.com/app/board/uXjVGixS6vQ=/"
source_root = "_bmad-output"
manifest_path = ".bmad-miro-sync/state.json"

[layout]
create_phase_frames = true

[publish]
analysis = true
planning = true
solutioning = true
implementation = true
stories_table = true
"""


class DiscoveryTests(unittest.TestCase):
    def test_generated_readiness_artifacts_use_exact_name_matching(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/implementation-readiness-report-2026-04-17-revised.md").write_text(
                "# Implementation Readiness Report\n\nBody\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/implementation-artifacts/implementation-readiness.md").write_text(
                "# Implementation Readiness\n\nOverall readiness: At Risk\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)
            by_path = {item.relative_path: item for item in result.selected}

            planning_report = by_path["_bmad-output/planning-artifacts/implementation-readiness-report-2026-04-17-revised.md"]
            readiness_summary = by_path["_bmad-output/implementation-artifacts/implementation-readiness.md"]

            self.assertEqual(planning_report.artifact_class, "document")
            self.assertEqual(planning_report.phase, "planning")
            self.assertEqual(planning_report.phase_zone, "planning")
            self.assertEqual(planning_report.workstream, "general")
            self.assertEqual(readiness_summary.artifact_class, "readiness_report")
            self.assertEqual(readiness_summary.phase, "implementation")
            self.assertEqual(readiness_summary.phase_zone, "implementation_readiness")
            self.assertEqual(readiness_summary.workstream, "delivery")

    def test_load_config_preserves_legacy_source_root_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(LEGACY_CONFIG, encoding="utf-8")

            config = load_config(config_path)

            self.assertEqual(config.source_root, "_bmad-output")
            self.assertEqual(config.source_paths, ("_bmad-output",))
            self.assertEqual(config.required_artifact_classes, ())

    def test_load_config_uses_custom_source_root_when_no_discovery_override_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(
                LEGACY_CONFIG.replace('source_root = "_bmad-output"', 'source_root = "docs/bmad"'),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.source_root, "docs/bmad")
            self.assertEqual(config.source_paths, ("docs/bmad",))

    def test_load_config_rejects_out_of_repo_manifest_path_when_project_root_is_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(
                LEGACY_CONFIG.replace('manifest_path = ".bmad-miro-sync/state.json"', 'manifest_path = "/tmp/state.json"'),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "manifest_path must stay inside the project root"):
                load_config(config_path, project_root=root)

    def test_load_config_rejects_out_of_repo_discovery_source_paths_when_project_root_is_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(
                LEGACY_CONFIG
                + """
[discovery]
source_paths = ["/tmp", "_bmad-output"]
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "discovery.source_paths\\[0\\] must stay inside the project root"):
                load_config(config_path, project_root=root)

    def test_discovery_prefers_whole_docs_and_reports_missing_required_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts/prd").mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\n## Goals\n\nWhole document\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd/index.md").write_text(
                "# PRD Index\n\n## Goals\n\nSharded document\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/implementation-artifacts/1-1-first-story.md").write_text(
                "# First Story\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            selected_paths = [item.relative_path for item in result.selected]
            self.assertEqual(
                selected_paths,
                [
                    "_bmad-output/planning-artifacts/prd.md",
                    "_bmad-output/implementation-artifacts/1-1-first-story.md",
                ],
            )
            self.assertEqual([item.relative_path for item in result.skipped], ["_bmad-output/planning-artifacts/prd/index.md"])
            self.assertIn("whole-document source", result.skipped[0].reason)
            self.assertEqual([item.artifact_class for item in result.missing_required], ["ux_design"])
            self.assertEqual(result.missing_required[0].search_paths, list(config.source_paths))
            self.assertTrue(any("ux_design" in warning for warning in result.warnings))
            self.assertTrue(all("index.md" not in artifact.source_artifact_id for artifact in result.artifacts))
            self.assertEqual(result.selected[0].phase_zone, "planning")
            self.assertEqual(result.selected[0].workstream, "product")
            self.assertEqual(result.selected[0].collaboration_intent, "anchor")

    def test_discovery_prefers_whole_docs_across_configured_source_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                LEGACY_CONFIG
                + """
[discovery]
source_paths = ["docs", "_bmad-output/planning-artifacts"]
required_artifact_classes = ["prd"]
""",
                encoding="utf-8",
            )
            (root / "docs/prd.md").write_text(
                "# PRD\n\n## Goals\n\nWhole document\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd/index.md").write_text(
                "# PRD Index\n\n## Goals\n\nSharded document\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual([item.relative_path for item in result.selected], ["docs/prd.md"])
            self.assertEqual(
                [item.relative_path for item in result.skipped],
                ["_bmad-output/planning-artifacts/prd/index.md"],
            )
            self.assertIn("docs/prd.md", result.skipped[0].reason)

    def test_discovery_keeps_first_whole_doc_as_canonical_across_configured_source_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                LEGACY_CONFIG
                + """
[discovery]
source_paths = ["docs", "_bmad-output/planning-artifacts"]
required_artifact_classes = ["prd"]
""",
                encoding="utf-8",
            )
            (root / "docs/prd.md").write_text(
                "# PRD\n\nPrimary whole document\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\nDuplicate whole document\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual([item.relative_path for item in result.selected], ["docs/prd.md"])
            self.assertEqual(
                [item.relative_path for item in result.skipped],
                ["_bmad-output/planning-artifacts/prd.md"],
            )
            self.assertIn("canonical source docs/prd.md", result.skipped[0].reason)

    def test_discovery_treats_alias_whole_docs_as_one_canonical_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                LEGACY_CONFIG
                + """
[discovery]
source_paths = ["_bmad-output/planning-artifacts"]
required_artifact_classes = ["prd"]
""",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/prd.md").write_text(
                "# PRD\n\nPrimary whole document\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/planning-artifacts/updated-prd.md").write_text(
                "# Updated PRD\n\nAlias whole document\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual([item.relative_path for item in result.selected], ["_bmad-output/planning-artifacts/prd.md"])
            self.assertEqual(
                [item.relative_path for item in result.skipped],
                ["_bmad-output/planning-artifacts/updated-prd.md"],
            )
            self.assertIn("canonical source _bmad-output/planning-artifacts/prd.md", result.skipped[0].reason)

    def test_story_files_under_implementation_artifacts_remain_story_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/1-1-discover-configured-planning-artifacts.md").write_text(
                "# Story 1.1\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(result.selected[0].artifact_class, "story")
            self.assertEqual(result.selected[0].phase, "implementation")
            self.assertEqual(result.selected[0].phase_zone, "implementation_readiness")
            self.assertEqual(result.selected[0].workstream, "delivery")
            self.assertEqual(result.selected[0].collaboration_intent, "summary")

    def test_story_files_under_legacy_stories_folder_remain_story_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts/stories").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/stories/review-ready.md").write_text(
                "# Review Ready Story\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(result.selected[0].artifact_class, "story")
            self.assertEqual(result.selected[0].phase, "implementation")
            self.assertEqual(result.selected[0].phase_zone, "implementation_readiness")
            self.assertEqual(result.selected[0].workstream, "delivery")
            self.assertEqual(result.selected[0].collaboration_intent, "summary")

    def test_date_prefixed_implementation_docs_do_not_become_stories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/2026-04-17-release-notes.md").write_text(
                "# Release Notes\n\nBody\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(result.selected[0].artifact_class, "document")
            self.assertEqual(result.selected[0].phase, "implementation")
            self.assertEqual(result.selected[0].phase_zone, "implementation_readiness")
            self.assertEqual(result.selected[0].workstream, "general")
            self.assertEqual(result.selected[0].collaboration_intent, "anchor")

    def test_discovery_classifies_solutioning_and_delivery_feedback_workspaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/ux-design-specification.md").write_text(
                "# UX Spec\n\nBody\n",
                encoding="utf-8",
            )
            (root / "_bmad-output/implementation-artifacts/epic-1-retrospective.md").write_text(
                "# Retro\n\n- Follow up on feedback\n- Close loop with stakeholders\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)
            by_path = {item.relative_path: item for item in result.selected}

            self.assertEqual(by_path["_bmad-output/planning-artifacts/ux-design-specification.md"].phase, "solutioning")
            self.assertEqual(by_path["_bmad-output/planning-artifacts/ux-design-specification.md"].phase_zone, "solutioning")
            self.assertEqual(by_path["_bmad-output/planning-artifacts/ux-design-specification.md"].workstream, "ux")
            self.assertEqual(by_path["_bmad-output/implementation-artifacts/epic-1-retrospective.md"].phase_zone, "delivery_feedback")
            self.assertEqual(by_path["_bmad-output/implementation-artifacts/epic-1-retrospective.md"].workstream, "delivery")

    def test_discovery_classifies_decision_records_as_delivery_feedback_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/review-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/review-artifacts/decision-records.md").write_text(
                "# Decision Records\n\nOpen topics: 1\nBlocked topics: 1\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(len(result.selected), 1)
            self.assertEqual(result.selected[0].artifact_class, "decision_records")
            self.assertEqual(result.selected[0].phase, "implementation")
            self.assertEqual(result.selected[0].phase_zone, "delivery_feedback")
            self.assertEqual(result.selected[0].workstream, "delivery")
            self.assertEqual(result.selected[0].collaboration_intent, "summary")

    def test_discovery_classifies_implementation_handoff_as_delivery_readiness_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/implementation-handoff.md").write_text(
                "# Implementation Handoff\n\nOverall readiness: At Risk\nReady for implementation handoff: No\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(len(result.selected), 1)
            self.assertEqual(result.selected[0].artifact_class, "implementation_handoff")
            self.assertEqual(result.selected[0].phase, "implementation")
            self.assertEqual(result.selected[0].phase_zone, "implementation_readiness")
            self.assertEqual(result.selected[0].workstream, "delivery")
            self.assertEqual(result.selected[0].collaboration_intent, "summary")

    def test_discovery_classifies_readiness_handoff_as_implementation_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/implementation-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/implementation-artifacts/readiness-handoff.md").write_text(
                "# Readiness Handoff\n\nOverall readiness: At Risk\nReady for implementation handoff: No\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(len(result.selected), 1)
            self.assertEqual(result.selected[0].artifact_class, "implementation_handoff")
            self.assertEqual(result.selected[0].phase, "implementation")
            self.assertEqual(result.selected[0].phase_zone, "implementation_readiness")
            self.assertEqual(result.selected[0].workstream, "delivery")
            self.assertEqual(result.selected[0].collaboration_intent, "summary")

    def test_planning_readiness_artifacts_do_not_auto_become_implementation_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(LEGACY_CONFIG, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/solutioning-readiness.md").write_text(
                "# Solutioning Readiness\n\nStatus: Ready\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            result = discover_artifacts(root, config)

            self.assertEqual(len(result.selected), 1)
            self.assertEqual(result.selected[0].artifact_class, "document")
            self.assertEqual(result.selected[0].phase, "planning")
            self.assertEqual(result.selected[0].phase_zone, "planning")
            self.assertEqual(result.selected[0].workstream, "general")
            self.assertEqual(result.selected[0].collaboration_intent, "anchor")

    def test_discovery_produces_stable_nested_section_ids_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text(
                "# PRD\n\nIntro\n\n## Goals\n\nBody\n\n### Metrics\n\nTrack it\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first = discover_artifacts(root, config)
            second = discover_artifacts(root, config)

            self.assertEqual(
                [artifact.artifact_id for artifact in first.artifacts],
                [
                    "_bmad-output/planning-artifacts/prd.md#prd",
                    "_bmad-output/planning-artifacts/prd.md#prd/goals",
                    "_bmad-output/planning-artifacts/prd.md#prd/goals/metrics",
                ],
            )
            self.assertEqual(
                [artifact.artifact_id for artifact in second.artifacts],
                [artifact.artifact_id for artifact in first.artifacts],
            )
            self.assertEqual(first.artifacts[2].parent_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
            self.assertEqual(first.artifacts[2].section_title_path, ("PRD", "Goals", "Metrics"))

    def test_discovery_marks_renamed_section_with_previous_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            renamed = by_id["_bmad-output/planning-artifacts/prd.md#prd/objectives"]
            sibling = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(renamed.lineage_status, "changed")
            self.assertEqual(renamed.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
            self.assertEqual(sibling.lineage_status, "unchanged")

    def test_discovery_marks_renamed_section_changed_when_content_also_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody v1\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody v2\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            renamed = by_id["_bmad-output/planning-artifacts/prd.md#prd/objectives"]
            sibling = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(renamed.lineage_status, "changed")
            self.assertEqual(renamed.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
            self.assertEqual(sibling.lineage_status, "unchanged")

    def test_discovery_uses_host_neutral_publish_bundle_for_lineage_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "publish-bundle.json", first_plan.to_dict())

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            renamed = by_id["_bmad-output/planning-artifacts/prd.md#prd/objectives"]
            sibling = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(renamed.lineage_status, "changed")
            self.assertEqual(renamed.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
            self.assertEqual(sibling.lineage_status, "unchanged")

    def test_discovery_ignores_malformed_runtime_artifacts_and_falls_back_to_next_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", {"artifacts": [123]})
            write_json(runtime_dir / "publish-bundle.json", first_plan.to_dict())

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            renamed = by_id["_bmad-output/planning-artifacts/prd.md#prd/objectives"]
            sibling = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(renamed.lineage_status, "changed")
            self.assertEqual(renamed.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
            self.assertEqual(sibling.lineage_status, "unchanged")

    def test_discovery_ignores_runtime_exports_with_mismatched_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            first_plan = build_sync_plan(root, config_path, config)
            payload = first_plan.to_dict()
            payload["config_path"] = str(root / "other-config.toml")
            write_json(runtime_dir / "plan.json", payload)

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n", encoding="utf-8")

            result = discover_artifacts(root, config, config_path=config_path)
            renamed = next(artifact for artifact in result.artifacts if artifact.artifact_id.endswith("/objectives"))

            self.assertEqual(renamed.lineage_status, "new")
            self.assertIsNone(renamed.previous_artifact_id)

    def test_discovery_ignores_runtime_exports_with_mismatched_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            config_path = root / ".bmad-miro.toml"
            config_path.write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            config = load_config(config_path)
            first_plan = build_sync_plan(root, config_path, config)
            payload = first_plan.to_dict()
            payload["manifest_path"] = "custom/state.json"
            write_json(runtime_dir / "plan.json", payload)

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n", encoding="utf-8")

            result = discover_artifacts(root, config, config_path=config_path)
            renamed = next(artifact for artifact in result.artifacts if artifact.artifact_id.endswith("/objectives"))

            self.assertEqual(renamed.lineage_status, "new")
            self.assertIsNone(renamed.previous_artifact_id)

    def test_discovery_uses_manifest_lineage_when_runtime_exports_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text("# PRD\n\n## Goals\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            manifest = apply_results(
                load_manifest(root, config.manifest_path),
                {
                    "items": [
                        {
                            "artifact_id": artifact.artifact_id,
                            "artifact_sha256": artifact.sha256,
                            "item_type": "doc",
                            "item_id": f"doc-{index}",
                            "miro_url": f"https://miro.com/app/board/x/?moveToWidget=doc-{index}",
                            "title": artifact.title,
                            "target_key": f"artifact:{artifact.artifact_id}",
                            "source_artifact_id": artifact.source_artifact_id,
                            "phase_zone": artifact.phase_zone,
                            "workstream": artifact.workstream,
                            "collaboration_intent": artifact.collaboration_intent,
                            "container_target_key": f"workstream:{artifact.phase_zone}:{artifact.workstream}",
                            "heading_level": artifact.heading_level,
                            "parent_artifact_id": artifact.parent_artifact_id,
                            "section_path": list(artifact.section_path),
                            "section_title_path": list(artifact.section_title_path),
                            "section_slug": artifact.section_slug,
                            "section_sibling_index": artifact.section_sibling_index,
                            "lineage_key": artifact.lineage_key,
                            "lineage_status": artifact.lineage_status,
                            "previous_artifact_id": artifact.previous_artifact_id,
                            "previous_parent_artifact_id": artifact.previous_parent_artifact_id,
                            "updated_at": "2026-04-20T00:00:00Z",
                        }
                        for index, artifact in enumerate(first_plan.artifacts, start=1)
                    ]
                },
            )
            save_manifest(root, config.manifest_path, manifest)

            doc_path.write_text("# PRD\n\n## Objectives\n\nBody\n\n## Risks\n\nRisk body\n", encoding="utf-8")

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            renamed = by_id["_bmad-output/planning-artifacts/prd.md#prd/objectives"]
            sibling = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(renamed.lineage_status, "changed")
            self.assertEqual(renamed.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/goals")
            self.assertEqual(sibling.lineage_status, "unchanged")

    def test_discovery_marks_moved_section_with_previous_lineage_without_changing_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text(
                "# PRD\n\n## Goals\n\nBody\n\n## Risks\n\nRisk body\n\n### Follow-up\n\nTrack it\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            doc_path.write_text(
                "# PRD\n\n## Goals\n\nBody\n\n### Follow-up\n\nTrack it\n\n## Risks\n\nRisk body\n",
                encoding="utf-8",
            )

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            moved = by_id["_bmad-output/planning-artifacts/prd.md#prd/goals/follow-up"]
            risks = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(moved.lineage_status, "changed")
            self.assertEqual(moved.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/risks/follow-up")
            self.assertEqual(risks.lineage_status, "unchanged")

    def test_discovery_marks_moved_section_changed_when_content_also_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text(
                "# PRD\n\n## Goals\n\nBody\n\n## Risks\n\nRisk body\n\n### Follow-up\n\nTrack v1\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            doc_path.write_text(
                "# PRD\n\n## Goals\n\nBody\n\n### Follow-up\n\nTrack v2\n\n## Risks\n\nRisk body\n",
                encoding="utf-8",
            )

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            moved = by_id["_bmad-output/planning-artifacts/prd.md#prd/goals/follow-up"]
            risks = by_id["_bmad-output/planning-artifacts/prd.md#prd/risks"]
            self.assertEqual(moved.lineage_status, "changed")
            self.assertEqual(moved.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/risks/follow-up")
            self.assertEqual(risks.lineage_status, "unchanged")

    def test_discovery_preserves_duplicate_sibling_ids_when_a_neighbor_is_renamed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text(
                "# PRD\n\n## Notes\n\nAlpha\n\n## Notes\n\nBeta\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            doc_path.write_text(
                "# PRD\n\n## Summary\n\nAlpha\n\n## Notes\n\nBeta\n",
                encoding="utf-8",
            )

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            renamed = by_id["_bmad-output/planning-artifacts/prd.md#prd/summary"]
            preserved = by_id["_bmad-output/planning-artifacts/prd.md#prd/notes-2"]
            self.assertEqual(renamed.lineage_status, "changed")
            self.assertEqual(renamed.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/notes")
            self.assertEqual(preserved.lineage_status, "unchanged")
            self.assertEqual(preserved.section_path, ("prd", "notes"))
            self.assertEqual(preserved.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/notes-2")

    def test_discovery_marks_moved_child_changed_when_duplicate_parent_titles_share_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_WITH_DISCOVERY, encoding="utf-8")
            doc_path = root / "_bmad-output/planning-artifacts/prd.md"
            doc_path.write_text(
                "# PRD\n\n## Section\n\nA\n\n### Item\n\nSame\n\n## Section\n\nB\n\n### Item\n\nSame\n",
                encoding="utf-8",
            )

            config = load_config(root / ".bmad-miro.toml")
            first_plan = build_sync_plan(root, root / ".bmad-miro.toml", config)
            write_json(runtime_dir / "plan.json", first_plan.to_dict())

            doc_path.write_text(
                "# PRD\n\n## Section\n\nA\n\n### Item\n\nSame\n\n### Item\n\nSame\n\n## Section\n\nB\n",
                encoding="utf-8",
            )

            result = discover_artifacts(root, config)
            by_id = {artifact.artifact_id: artifact for artifact in result.artifacts}

            moved = by_id["_bmad-output/planning-artifacts/prd.md#prd/section/item-2"]
            self.assertEqual(moved.lineage_status, "changed")
            self.assertEqual(moved.previous_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/section-2/item")
            self.assertEqual(moved.previous_parent_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/section-2")
            self.assertEqual(moved.parent_artifact_id, "_bmad-output/planning-artifacts/prd.md#prd/section")


if __name__ == "__main__":
    unittest.main()
