from __future__ import annotations

import unittest

from bmad_miro_sync.config import LayoutConfig
from bmad_miro_sync.miro_api import (
    MiroApiError,
    _apply_layout_positions,
    _doc_summary_html,
    _execute_single_operation,
    _result_entry_from_response,
)


class _MissingFrameUpdateClient:
    def update_frame(self, board_id: str, item_id: str, payload: dict) -> dict:
        raise MiroApiError(
            f'Miro API PATCH /v2/boards/{board_id}/frames/{item_id} failed with 404: {{ "message" : "Item not found", "status" : 404 }}'
        )

    def create_frame(self, board_id: str, payload: dict) -> dict:
        return {
            "id": "new-frame-id",
            "position": payload["position"],
            "geometry": payload["geometry"],
            "links": {"self": f"https://api.miro.com/v2/boards/{board_id}/frames/new-frame-id"},
            "createdAt": "2026-05-06T12:00:00Z",
        }


class MiroApiLayoutTests(unittest.TestCase):
    def test_phases_stack_horizontally_by_rendered_content_width_by_default(self) -> None:
        layout = LayoutConfig()
        operations = [
            {
                "op_id": "zone:analysis",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "analysis",
                "workstream": "general",
            },
            {
                "op_id": "zone:planning",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "planning",
                "workstream": "general",
            },
            {
                "op_id": "workstream:analysis:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "analysis",
                "workstream": "product",
            },
            {
                "op_id": "workstream:planning:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "planning",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:analysis-large",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
            },
            {
                "op_id": "doc:source_header:analysis-large",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
                "artifact_id": "source_header:_bmad-output/analysis-large.md",
                "title": "Analysis",
                "content": "Product · 1 section",
                "heading_level": 0,
            },
            {
                "op_id": "doc:analysis-large",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
                "artifact_id": "_bmad-output/analysis-large.md#overview",
                "title": "Analysis / Overview",
                "content": "\n".join(f"Line {index} with enough text to expand the card height significantly." for index in range(160)),
                "heading_level": 1,
            },
            {
                "op_id": "source_frame:planning-small",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-small.md",
            },
            {
                "op_id": "doc:source_header:planning-small",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-small.md",
                "artifact_id": "source_header:_bmad-output/planning-small.md",
                "title": "Planning",
                "content": "Product · 1 section",
                "heading_level": 0,
            },
            {
                "op_id": "doc:planning-small",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-small.md",
                "artifact_id": "_bmad-output/planning-small.md#overview",
                "title": "Planning / Overview",
                "content": "Short content",
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)
        analysis_frame = planned[4]
        planning_frame = planned[7]

        analysis_right = analysis_frame["planned_position"]["x"] + (analysis_frame["planned_geometry"]["width"] / 2.0)
        planning_left = planning_frame["planned_position"]["x"] - (planning_frame["planned_geometry"]["width"] / 2.0)
        analysis_top = analysis_frame["planned_position"]["y"] - (analysis_frame["planned_geometry"]["height"] / 2.0)
        planning_top = planning_frame["planned_position"]["y"] - (planning_frame["planned_geometry"]["height"] / 2.0)

        self.assertGreaterEqual(planning_left - analysis_right, layout.phase_gap_x)
        self.assertEqual(planning_top, analysis_top)

    def test_phases_can_stack_vertically_when_configured(self) -> None:
        layout = LayoutConfig(phase_axis="vertical")
        operations = [
            {
                "op_id": "zone:analysis",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "analysis",
                "workstream": "general",
            },
            {
                "op_id": "zone:planning",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "planning",
                "workstream": "general",
            },
            {
                "op_id": "workstream:analysis:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "analysis",
                "workstream": "product",
            },
            {
                "op_id": "workstream:planning:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "planning",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:analysis-large",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
            },
            {
                "op_id": "doc:analysis-large",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
                "artifact_id": "_bmad-output/analysis-large.md#overview",
                "title": "Analysis / Overview",
                "content": "Tall content\\n" * 120,
                "heading_level": 1,
            },
            {
                "op_id": "source_frame:planning-small",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-small.md",
            },
            {
                "op_id": "doc:planning-small",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-small.md",
                "artifact_id": "_bmad-output/planning-small.md#overview",
                "title": "Planning / Overview",
                "content": "Short content",
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)
        analysis_frame = planned[4]
        planning_frame = planned[6]

        analysis_bottom = analysis_frame["planned_position"]["y"] + (analysis_frame["planned_geometry"]["height"] / 2.0)
        planning_top = planning_frame["planned_position"]["y"] - (planning_frame["planned_geometry"]["height"] / 2.0)
        self.assertGreaterEqual(planning_top - analysis_bottom, layout.phase_gap_y)

    def test_zone_background_spans_phase_content_with_padding(self) -> None:
        layout = LayoutConfig()
        operations = [
            {
                "op_id": "zone:analysis",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "analysis",
                "workstream": "general",
            },
            {
                "op_id": "workstream:analysis:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "analysis",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:analysis-large",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
            },
            {
                "op_id": "doc:analysis-large",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis-large.md",
                "artifact_id": "_bmad-output/analysis-large.md#overview",
                "title": "Analysis / Overview",
                "content": "Long content\\n" * 80,
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)
        zone = planned[0]
        workstream = planned[1]
        frame = planned[2]

        zone_left = zone["planned_position"]["x"] - (zone["planned_geometry"]["width"] / 2.0)
        zone_right = zone["planned_position"]["x"] + (zone["planned_geometry"]["width"] / 2.0)
        zone_top = zone["planned_position"]["y"] - (zone["planned_geometry"]["height"] / 2.0)
        zone_bottom = zone["planned_position"]["y"] + (zone["planned_geometry"]["height"] / 2.0)

        frame_left = frame["planned_position"]["x"] - (frame["planned_geometry"]["width"] / 2.0)
        frame_right = frame["planned_position"]["x"] + (frame["planned_geometry"]["width"] / 2.0)
        frame_top = frame["planned_position"]["y"] - (frame["planned_geometry"]["height"] / 2.0)
        frame_bottom = frame["planned_position"]["y"] + (frame["planned_geometry"]["height"] / 2.0)

        workstream_top = workstream["planned_position"]["y"] - (layout.workstream_header_height / 2.0)

        self.assertLessEqual(zone_left, frame_left - layout.phase_column_padding_x)
        self.assertGreaterEqual(zone_right, frame_right + layout.phase_column_padding_x)
        self.assertLessEqual(zone_top, workstream_top - (layout.phase_column_padding_top - 24.0))
        self.assertGreaterEqual(zone_bottom, frame_bottom + layout.phase_column_padding_bottom)

    def test_phase_separator_is_positioned_between_horizontal_phase_columns(self) -> None:
        layout = LayoutConfig()
        operations = [
            {
                "op_id": "zone:analysis",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "analysis",
                "workstream": "general",
            },
            {
                "op_id": "phase_separator:analysis:planning",
                "action": "create_phase_separator",
                "item_type": "phase_separator",
                "phase_zone": "planning",
                "workstream": "general",
            },
            {
                "op_id": "zone:planning",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "planning",
                "workstream": "general",
            },
            {
                "op_id": "workstream:analysis:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "analysis",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:analysis",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis.md",
            },
            {
                "op_id": "doc:analysis",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/analysis.md",
                "artifact_id": "_bmad-output/analysis.md#overview",
                "title": "Analysis / Overview",
                "content": "Long content\\n" * 40,
                "heading_level": 1,
            },
            {
                "op_id": "workstream:planning:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "planning",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:planning",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning.md",
            },
            {
                "op_id": "doc:planning",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning.md",
                "artifact_id": "_bmad-output/planning.md#overview",
                "title": "Planning / Overview",
                "content": "Short content",
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)
        analysis_zone = planned[0]
        separator = planned[1]
        planning_zone = planned[2]

        analysis_right = analysis_zone["planned_position"]["x"] + (analysis_zone["planned_geometry"]["width"] / 2.0)
        planning_left = planning_zone["planned_position"]["x"] - (planning_zone["planned_geometry"]["width"] / 2.0)
        separator_x = separator["planned_position"]["x"]

        self.assertGreater(separator_x, analysis_right)
        self.assertLess(separator_x, planning_left)
        self.assertEqual(separator["planned_geometry"]["width"], 12.0)

    def test_missing_source_frame_update_recreates_frame(self) -> None:
        layout = LayoutConfig()
        operation = {
            "op_id": "source_frame:_bmad-output/planning-artifacts/prd.md",
            "action": "update_source_frame",
            "item_type": "source_frame",
            "artifact_id": "source:_bmad-output/planning-artifacts/prd.md",
            "artifact_sha256": "abc123",
            "title": "PRD",
            "phase_zone": "planning",
            "workstream": "product",
            "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
            "collaboration_intent": "orientation",
            "container_target_key": "workstream:planning:product",
            "existing_item": {
                "item_id": "stale-frame-id",
                "item_type": "source_frame",
                "host_item_type": "frame",
            },
            "planned_position": {"x": -1200.0, "y": 16000.0},
            "planned_geometry": {"width": 1100.0, "height": 8200.0},
        }

        result = _execute_single_operation(
            _MissingFrameUpdateClient(),
            board_id="uXjVGixS6vQ=",
            board_url="https://miro.com/app/board/uXjVGixS6vQ=/",
            operation=operation,
            artifact=None,
            layout=layout,
            item_id_by_artifact={},
        )

        self.assertEqual(result["execution_status"], "recreated")
        self.assertEqual(result["item_id"], "new-frame-id")
        self.assertEqual(result["layout_snapshot"]["y"], 16000.0)

    def test_result_entry_prefers_planned_layout_snapshot(self) -> None:
        operation = {
            "op_id": "source_frame:_bmad-output/planning-artifacts/prd.md",
            "action": "update_source_frame",
            "item_type": "source_frame",
            "artifact_id": "source:_bmad-output/planning-artifacts/prd.md",
            "artifact_sha256": "abc123",
            "title": "PRD",
            "phase_zone": "planning",
            "workstream": "product",
            "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
            "planned_position": {"x": -1200.0, "y": 36000.0},
            "planned_geometry": {"width": 1100.0, "height": 8200.0},
        }
        response_item = {
            "id": "frame-id",
            "position": {"x": -1200.0, "y": 1200.0},
            "geometry": {"width": 400.0, "height": 300.0},
            "links": {"self": "https://api.miro.com/v2/boards/uXjVGixS6vQ=/frames/frame-id"},
        }

        result = _result_entry_from_response(
            operation,
            None,
            response_item,
            board_url="https://miro.com/app/board/uXjVGixS6vQ=/",
            execution_status="updated",
        )

        self.assertEqual(result["layout_snapshot"]["x"], -1200.0)
        self.assertEqual(result["layout_snapshot"]["y"], 36000.0)
        self.assertEqual(result["layout_snapshot"]["width"], 1100.0)
        self.assertEqual(result["layout_snapshot"]["height"], 8200.0)

    def test_updated_docs_still_participate_in_source_frame_layout(self) -> None:
        layout = LayoutConfig()
        operations = [
            {
                "op_id": "workstream:planning:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "planning",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:_bmad-output/planning-artifacts/prd.md",
                "action": "update_source_frame",
                "item_type": "source_frame",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                "artifact_id": "source:_bmad-output/planning-artifacts/prd.md",
            },
            {
                "op_id": "doc:source_header:_bmad-output/planning-artifacts/prd.md",
                "action": "update_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                "artifact_id": "source_header:_bmad-output/planning-artifacts/prd.md",
                "title": "PRD",
                "content": "Product · 2 sections",
                "heading_level": 0,
            },
            {
                "op_id": "doc:_bmad-output/planning-artifacts/prd.md#overview",
                "action": "update_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
                "title": "PRD / Overview",
                "content": "\n".join(f"Line {index} with enough text to expand the frame." for index in range(80)),
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)
        frame = planned[1]
        header = planned[2]
        doc = planned[3]

        self.assertEqual(header["planned_parent_artifact_id"], "source:_bmad-output/planning-artifacts/prd.md")
        self.assertEqual(doc["planned_parent_artifact_id"], "source:_bmad-output/planning-artifacts/prd.md")
        self.assertGreater(frame["planned_geometry"]["height"], 260.8)
        self.assertGreater(doc["planned_position"]["y"], header["planned_position"]["y"])

    def test_source_headers_do_not_start_next_frame_before_body_cards(self) -> None:
        layout = LayoutConfig()
        operations = [
            {
                "op_id": "workstream:analysis:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "analysis",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:first",
                "action": "update_source_frame",
                "item_type": "source_frame",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/first.md",
                "artifact_id": "source:_bmad-output/first.md",
            },
            {
                "op_id": "doc:source_header:first",
                "action": "update_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/first.md",
                "artifact_id": "source_header:_bmad-output/first.md",
                "title": "First",
                "content": "Product · 1 section",
                "heading_level": 0,
            },
            {
                "op_id": "source_frame:second",
                "action": "update_source_frame",
                "item_type": "source_frame",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/second.md",
                "artifact_id": "source:_bmad-output/second.md",
            },
            {
                "op_id": "doc:source_header:second",
                "action": "update_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/second.md",
                "artifact_id": "source_header:_bmad-output/second.md",
                "title": "Second",
                "content": "Product · 1 section",
                "heading_level": 0,
            },
            {
                "op_id": "doc:first-body",
                "action": "update_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/first.md",
                "artifact_id": "_bmad-output/first.md#overview",
                "title": "First / Overview",
                "content": "\n".join(f"Line {index} with enough text to make the first frame tall." for index in range(120)),
                "heading_level": 1,
            },
            {
                "op_id": "doc:second-body",
                "action": "update_doc",
                "item_type": "doc",
                "phase_zone": "analysis",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/second.md",
                "artifact_id": "_bmad-output/second.md#overview",
                "title": "Second / Overview",
                "content": "Short content",
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)
        first_frame = planned[1]
        second_frame = planned[3]

        first_bottom = first_frame["planned_position"]["y"] + (first_frame["planned_geometry"]["height"] / 2.0)
        second_top = second_frame["planned_position"]["y"] - (second_frame["planned_geometry"]["height"] / 2.0)

        self.assertGreaterEqual(second_top - first_bottom, layout.source_gap_y)

    def test_source_frame_reserves_clearance_below_workstream_header(self) -> None:
        layout = LayoutConfig()
        operations = [
            {
                "op_id": "zone:planning",
                "action": "ensure_zone",
                "item_type": "zone",
                "phase_zone": "planning",
                "workstream": "product",
            },
            {
                "op_id": "workstream:planning:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "phase_zone": "planning",
                "workstream": "product",
            },
            {
                "op_id": "source_frame:_bmad-output/planning-artifacts/prd.md",
                "action": "create_source_frame",
                "item_type": "source_frame",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
            },
            {
                "op_id": "doc:source_header:_bmad-output/planning-artifacts/prd.md",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                "artifact_id": "source_header:_bmad-output/planning-artifacts/prd.md",
                "title": "PRD",
                "content": "Product · 1 section",
                "heading_level": 0,
            },
            {
                "op_id": "doc:_bmad-output/planning-artifacts/prd.md#prd",
                "action": "create_doc",
                "item_type": "doc",
                "phase_zone": "planning",
                "workstream": "product",
                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd",
                "title": "PRD",
                "content": "Overview paragraph",
                "heading_level": 1,
            },
        ]

        planned = _apply_layout_positions(operations, layout)

        workstream = planned[1]
        source_frame = planned[2]
        source_header = planned[3]
        section_card = planned[4]
        workstream_bottom = workstream["planned_position"]["y"] + (layout.workstream_header_height / 2.0)
        source_frame_top = source_frame["planned_position"]["y"] - (source_frame["planned_geometry"]["height"] / 2.0)

        self.assertGreaterEqual(source_frame_top - workstream_bottom, 112.0)
        self.assertEqual(source_header["planned_parent_artifact_id"], "source:_bmad-output/planning-artifacts/prd.md")
        self.assertGreater(section_card["planned_position"]["y"], source_header["planned_position"]["y"])

    def test_doc_summary_prefers_real_paragraph_over_sanitization_placeholder(self) -> None:
        layout = LayoutConfig()
        operation = {
            "item_type": "doc",
            "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
            "title": "PRD",
            "phase_zone": "planning",
            "workstream": "product",
            "heading_level": 1,
            "content": "\n".join(
                [
                    "<style>.x{color:red}</style>",
                    "",
                    "This is the real summary paragraph.",
                    "",
                    "- First bullet",
                ]
            ),
        }

        lines = _doc_summary_html(operation, layout=layout)

        self.assertNotIn("Raw HTML/CSS payload omitted", "".join(lines))
        self.assertIn("This is the real summary paragraph.", "".join(lines))
        self.assertIn("First bullet", "".join(lines))

    def test_doc_summary_omits_placeholder_when_no_real_content_exists(self) -> None:
        layout = LayoutConfig()
        operation = {
            "item_type": "doc",
            "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
            "title": "PRD",
            "phase_zone": "planning",
            "workstream": "product",
            "heading_level": 1,
            "content": "<style>.x{color:red}</style>",
        }

        lines = _doc_summary_html(operation, layout=layout)

        rendered = "".join(lines)
        self.assertNotIn("Raw HTML/CSS payload omitted", rendered)
        self.assertEqual(rendered, "<p><strong>Summary</strong></p><p><em>Planning / Product</em></p>")

    def test_doc_summary_omits_placeholder_when_only_bullets_are_meaningful(self) -> None:
        layout = LayoutConfig()
        operation = {
            "item_type": "doc",
            "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
            "title": "PRD",
            "phase_zone": "planning",
            "workstream": "product",
            "heading_level": 1,
            "content": "\n".join(
                [
                    "<style>.x{color:red}</style>",
                    "",
                    "- First bullet",
                    "- Second bullet",
                ]
            ),
        }

        lines = _doc_summary_html(operation, layout=layout)
        rendered = "".join(lines)

        self.assertNotIn("Raw HTML/CSS payload omitted", rendered)
        self.assertIn("First bullet", rendered)
        self.assertIn("Second bullet", rendered)

    def test_doc_summary_uses_fallback_content_when_primary_content_is_metadata_only(self) -> None:
        layout = LayoutConfig()
        operation = {
            "item_type": "doc",
            "artifact_id": "_bmad-output/planning-artifacts/prd.md#overview",
            "title": "Product Requirements Document - fluidscan / Overview",
            "phase_zone": "planning",
            "workstream": "product",
            "heading_level": 0,
            "content": "---\nworkflow_completed: true\n---\n",
            "summary_fallback_content": "## Executive Summary\n\nFluidScan is a web application for readers who accumulate worthwhile long-form articles.",
        }

        lines = _doc_summary_html(operation, layout=layout)
        rendered = "".join(lines)

        self.assertIn("FluidScan is a web application", rendered)
        self.assertNotIn("Raw HTML/CSS payload omitted", rendered)


if __name__ == "__main__":
    unittest.main()
