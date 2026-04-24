from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qsl
from urllib.request import urlopen


CONFIG_TEXT = """
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


class CliApplyResultsTests(unittest.TestCase):
    def test_plan_resolves_relative_output_path_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root = temp_root / "project"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            plan_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "plan",
                    "--project-root",
                    str(root),
                    "--config",
                    ".bmad-miro.toml",
                    "--output",
                    ".bmad-miro-sync/run/plan.json",
                ],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
            self.assertTrue((root / ".bmad-miro-sync/run/plan.json").exists())
            self.assertFalse((temp_root / ".bmad-miro-sync/run/plan.json").exists())

    def test_export_bundle_resolves_relative_config_and_output_paths_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root = temp_root / "project"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    ".bmad-miro.toml",
                    "--output-dir",
                    ".bmad-miro-sync/run",
                ],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(export_result.returncode, 0, export_result.stderr)
            self.assertTrue((root / ".bmad-miro-sync/run/plan.json").exists())
            self.assertTrue((root / ".bmad-miro-sync/run/publish-bundle.json").exists())
            self.assertTrue((root / ".bmad-miro-sync/run/codex-bundle.json").exists())
            self.assertFalse((temp_root / ".bmad-miro-sync/run/plan.json").exists())

    def test_plan_rejects_out_of_repo_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "project"
            outside = Path(tmpdir) / "outside"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            outside.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "plan",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output",
                    str(outside / "plan.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("--output must stay inside the project root", result.stderr)
            self.assertFalse((outside / "plan.json").exists())

    def test_render_host_instructions_rejects_out_of_repo_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "project"
            outside = Path(tmpdir) / "outside"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            outside.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "render-host-instructions",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output",
                    str(outside / "instructions.md"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("--output must stay inside the project root", result.stderr)
            self.assertFalse((outside / "instructions.md").exists())

    def test_export_bundle_rejects_out_of_repo_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "project"
            outside = Path(tmpdir) / "outside"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            outside.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(outside / "run"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("--output-dir must stay inside the project root", result.stderr)
            self.assertFalse((outside / "run/plan.json").exists())

    def test_apply_results_falls_back_to_legacy_reconciliation_when_default_plan_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync/run").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            results_path = root / ".bmad-miro-sync/run/results.json"
            results_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "artifact_id": "doc:test#overview",
                                "artifact_sha256": "sha-123",
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": "Overview",
                                "target_key": "artifact:doc:test#overview",
                                "source_artifact_id": "doc:test",
                                "phase_zone": "planning",
                                "workstream": "general",
                                "collaboration_intent": "anchor",
                                "container_target_key": "workstream:planning:general",
                                "heading_level": 0,
                                "parent_artifact_id": None,
                                "updated_at": "2026-04-18T00:15:00Z",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(results_path),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_result.returncode, 0)
            self.assertIn("Plan file not found", apply_result.stderr)
            self.assertIn("legacy results-only reconciliation", apply_result.stderr)
            state = json.loads((root / ".bmad-miro-sync/state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["items"]["doc:test#overview"]["item_id"], "doc-123")

    def test_apply_results_legacy_fallback_reports_invalid_content_item_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync/run").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            results_path = root / ".bmad-miro-sync/run/results.json"
            results_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "artifact_id": "doc:test#overview",
                                "item_type": "doc",
                                "item_id": "doc-123",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(results_path),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("Invalid results data", apply_result.stderr)
            self.assertIn("artifact_sha256", apply_result.stderr)
            self.assertFalse((root / ".bmad-miro-sync/state.json").exists())

    def test_apply_results_rejects_plan_manifest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (runtime_dir / "plan.json").write_text(
                json.dumps(
                    {
                        "config_path": str(root / ".bmad-miro.toml"),
                        "manifest_path": "custom/state.json",
                        "operations": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "results.json").write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("Plan/runtime manifest mismatch", apply_result.stderr)
            self.assertFalse((root / ".bmad-miro-sync/state.json").exists())

    def test_apply_results_rejects_out_of_repo_stage_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "project"
            outside_root = Path(tmpdir) / "outside"
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            outside_root.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (runtime_dir / "plan.json").write_text(json.dumps({"operations": []}, indent=2) + "\n", encoding="utf-8")
            outside_results = outside_root / "results.json"
            outside_results.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(outside_results),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("--results must stay inside the project root", apply_result.stderr)
            self.assertNotIn("Traceback", apply_result.stderr)
            self.assertFalse((root / ".bmad-miro-sync/state.json").exists())

    def test_plan_rejects_out_of_repo_manifest_path_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(
                CONFIG_TEXT.replace('manifest_path = ".bmad-miro-sync/state.json"', 'manifest_path = "/tmp/state.json"'),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "plan",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("manifest_path must stay inside the project root", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_plan_rejects_out_of_repo_discovery_source_paths_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            outside_root = root.parent / "outside-source"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            outside_root.mkdir(parents=True, exist_ok=True)
            (outside_root / "foreign.md").write_text("# Foreign\n\nBody\n", encoding="utf-8")
            (root / ".bmad-miro.toml").write_text(
                CONFIG_TEXT
                + f"""
[discovery]
source_paths = [\"{outside_root}\", \"_bmad-output/planning-artifacts\"]
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "plan",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("discovery.source_paths[0] must stay inside the project root", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_ingest_comments_rejects_invalid_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text('{"version": 3, "items": {}}\n', encoding="utf-8")
            (runtime_dir / "comments.json").write_text(json.dumps({"foo": []}, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "ingest-comments",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--comments",
                    str(runtime_dir / "comments.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Comments input must include a 'comments' list.", result.stderr)


class _MiroApiTestServer(HTTPServer):
    def __init__(self, server_address: tuple[str, int], fail_bulk: bool = False) -> None:
        super().__init__(server_address, _MiroApiTestHandler)
        self.calls: list[dict[str, object]] = []
        self.fail_bulk = fail_bulk


class _MiroApiTestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        raw_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(raw_length).decode("utf-8") if raw_length else ""
        payload = json.loads(body) if body and self.headers.get("Content-Type") == "application/json" else body
        self.server.calls.append({"method": "POST", "path": self.path, "body": payload})

        if self.path == "/v1/oauth/token":
            params = parse_form_body(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "access_token": "oauth-access-token",
                        "token_type": "bearer",
                        "scope": "boards:read boards:write",
                        "expires_in": 3600,
                        "redirect_uri": params.get("redirect_uri"),
                    }
                ).encode("utf-8")
            )
            return

        if self.path.endswith("/items/bulk") and self.server.fail_bulk:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "bulk create failed"}).encode("utf-8"))
            return

        if self.path.endswith("/items/bulk"):
            data = []
            for index, item in enumerate(payload or []):
                item_type = item["type"]
                prefix = "shape" if item_type == "shape" else "text"
                geometry = item.get("geometry", {})
                position = item.get("position", {})
                data.append(
                    {
                        "id": f"{prefix}-{index + 1}",
                        "type": item_type,
                        "createdAt": "2026-04-23T10:00:00Z",
                        "geometry": {
                            "width": geometry.get("width"),
                            "height": geometry.get("height"),
                        },
                        "position": {
                            "x": position.get("x"),
                            "y": position.get("y"),
                        },
                    }
                )
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": data}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class CliPublishDirectTests(unittest.TestCase):
    def test_setup_miro_rest_auth_captures_localhost_callback_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            callback_port = 8899
            callback_thread: threading.Thread | None = None
            try:
                result_holder: dict[str, subprocess.CompletedProcess[str]] = {}

                def run_setup() -> None:
                    result_holder["result"] = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "bmad_miro_sync",
                            "setup-miro-rest-auth",
                            "--project-root",
                            str(root),
                            "--client-id",
                            "3458764669066385754",
                            "--client-secret",
                            "secret-value",
                            "--redirect-uri",
                            f"http://127.0.0.1:{callback_port}/callback",
                            "--token-endpoint",
                            f"http://127.0.0.1:{server.server_port}/v1/oauth/token",
                            "--callback-timeout",
                            "10",
                        ],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                callback_thread = threading.Thread(target=run_setup, daemon=True)
                callback_thread.start()

                _wait_for_port(callback_port)
                with urlopen(f"http://127.0.0.1:{callback_port}/callback?code=auto-code-123") as response:
                    self.assertEqual(response.status, 200)

                callback_thread.join(timeout=10)
                self.assertIn("result", result_holder)
                result = result_holder["result"]
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
                if callback_thread is not None:
                    callback_thread.join(timeout=1)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["redirect_uri"], f"http://127.0.0.1:{callback_port}/callback")
            auth_payload = json.loads((root / ".bmad-miro-auth.json").read_text(encoding="utf-8"))
            self.assertEqual(auth_payload["access_token"], "oauth-access-token")

    def test_setup_miro_rest_auth_writes_repo_local_auth_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "setup-miro-rest-auth",
                        "--project-root",
                        str(root),
                        "--install-url",
                        "https://miro.com/app-install/?response_type=code&client_id=3458764669066385754&redirect_uri=%2Fapp-install%2Fconfirm%2F",
                        "--client-secret",
                        "secret-value",
                        "--redirected-url",
                        "https://miro.com/app-install/confirm/?code=abc123",
                        "--token-endpoint",
                        f"http://127.0.0.1:{server.server_port}/v1/oauth/token",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["client_id"], "3458764669066385754")
            self.assertIn("redirect_uri=%2Fapp-install%2Fconfirm%2F", payload["install_url"])
            auth_payload = json.loads((root / ".bmad-miro-auth.json").read_text(encoding="utf-8"))
            self.assertEqual(auth_payload["access_token"], "oauth-access-token")
            self.assertEqual(auth_payload["client_id"], "3458764669066385754")
            self.assertEqual(auth_payload["redirect_uri"], "/app-install/confirm/")

    def test_setup_miro_rest_auth_rebuilds_install_url_for_explicit_localhost_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "setup-miro-rest-auth",
                        "--project-root",
                        str(root),
                        "--install-url",
                        "https://miro.com/app-install/?response_type=code&client_id=3458764669066385754&redirect_uri=%2Fapp-install%2Fconfirm%2F",
                        "--client-secret",
                        "secret-value",
                        "--redirect-uri",
                        "http://127.0.0.1:8899/callback",
                        "--redirected-url",
                        "http://127.0.0.1:8899/callback?code=abc123",
                        "--token-endpoint",
                        f"http://127.0.0.1:{server.server_port}/v1/oauth/token",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("redirect_uri=http%3A%2F%2F127.0.0.1%3A8899%2Fcallback", payload["install_url"])
            auth_payload = json.loads((root / ".bmad-miro-auth.json").read_text(encoding="utf-8"))
            self.assertEqual(auth_payload["redirect_uri"], "http://127.0.0.1:8899/callback")

    def test_publish_direct_uses_bulk_create_and_applies_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath, MIRO_API_TOKEN="test-token")
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            plan_path = runtime_dir / "plan.json"
            plan_path.write_text(json.dumps(_sample_publish_plan(root), indent=2) + "\n", encoding="utf-8")

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "publish-direct",
                        "--project-root",
                        str(root),
                        "--config",
                        str(root / ".bmad-miro.toml"),
                        "--plan",
                        str(plan_path),
                        "--results",
                        ".bmad-miro-sync/run/results.json",
                        "--api-base-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--apply-results",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(server.calls), 1)
            self.assertEqual(server.calls[0]["path"], "/v2/boards/uXjVGixS6vQ=/items/bulk")
            self.assertEqual(len(server.calls[0]["body"]), 2)
            results_payload = json.loads((runtime_dir / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(results_payload["run_status"], "complete")
            self.assertEqual(len(results_payload["items"]), 2)
            state = json.loads((root / ".bmad-miro-sync/state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["last_run"]["run_status"], "complete")
            self.assertEqual(state["items"]["_bmad-output/planning-artifacts/prd.md#prd"]["host_item_type"], "text")
            self.assertEqual(state["items"]["workstream:planning:product"]["host_item_type"], "shape")

    def test_publish_direct_uses_repo_local_auth_file_when_env_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            env.pop("MIRO_API_TOKEN", None)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-auth.json").write_text(
                json.dumps({"access_token": "repo-token"}, indent=2) + "\n",
                encoding="utf-8",
            )
            plan_path = runtime_dir / "plan.json"
            plan_path.write_text(json.dumps(_sample_publish_plan(root), indent=2) + "\n", encoding="utf-8")

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "publish-direct",
                        "--project-root",
                        str(root),
                        "--config",
                        str(root / ".bmad-miro.toml"),
                        "--plan",
                        str(plan_path),
                        "--results",
                        ".bmad-miro-sync/run/results.json",
                        "--api-base-url",
                        f"http://127.0.0.1:{server.server_port}",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(server.calls), 1)
            self.assertEqual(
                server.calls[0]["path"],
                "/v2/boards/uXjVGixS6vQ=/items/bulk",
            )

    def test_publish_direct_respects_layout_config_for_colors_positions_and_widths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath, MIRO_API_TOKEN="test-token")
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            config_text = CONFIG_TEXT.replace(
                "[layout]\ncreate_phase_frames = true\n",
                "[layout]\n"
                "create_phase_frames = true\n"
                "doc_width = 720\n"
                "content_start_y = 320\n"
                "fragment_indent_x = 180\n",
            )
            config_text += """
[layout.phase_y]
planning = -250

[layout.workstream_x]
product = 150

[layout.phase_colors]
planning = "#123456"
"""
            (root / ".bmad-miro.toml").write_text(config_text, encoding="utf-8")
            plan_path = runtime_dir / "plan.json"
            plan_path.write_text(json.dumps(_sample_publish_plan(root), indent=2) + "\n", encoding="utf-8")

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "publish-direct",
                        "--project-root",
                        str(root),
                        "--config",
                        str(root / ".bmad-miro.toml"),
                        "--plan",
                        str(plan_path),
                        "--results",
                        ".bmad-miro-sync/run/results.json",
                        "--api-base-url",
                        f"http://127.0.0.1:{server.server_port}",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stderr)
            bulk_payload = server.calls[0]["body"]
            self.assertEqual(bulk_payload[0]["position"]["x"], 150.0)
            self.assertEqual(bulk_payload[0]["position"]["y"], -250.0)
            self.assertEqual(bulk_payload[0]["style"]["fillColor"], "#123456")
            self.assertEqual(bulk_payload[1]["position"]["x"], 150.0)
            self.assertEqual(bulk_payload[1]["position"]["y"], 70.0)
            self.assertEqual(bulk_payload[1]["geometry"]["width"], 720.0)

    def test_publish_direct_sanitizes_raw_html_and_css_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath, MIRO_API_TOKEN="test-token")
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            plan = _sample_publish_plan(root)
            plan["operations"][1]["content"] = (
                "# PRD\n\n"
                "<!DOCTYPE html>\n"
                "<html>\n"
                "<style>\n"
                ".com-sec-card-1__icon--pink path{fill:#ed6f78}.com-sec-card-1__icon--pink-light circle{fill:#ffbfbf}\n"
                "</style>\n"
                "<body>\n"
                "Visible summary text.\n"
                "```html\n"
                "<div class=\"waf\">blocked</div>\n"
                "</html>\n"
                "```\n"
            )
            plan_path = runtime_dir / "plan.json"
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

            server = _MiroApiTestServer(("127.0.0.1", 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "publish-direct",
                        "--project-root",
                        str(root),
                        "--config",
                        str(root / ".bmad-miro.toml"),
                        "--plan",
                        str(plan_path),
                        "--results",
                        ".bmad-miro-sync/run/results.json",
                        "--api-base-url",
                        f"http://127.0.0.1:{server.server_port}",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stderr)
            bulk_payload = server.calls[0]["body"]
            content = bulk_payload[1]["data"]["content"]
            self.assertIn("Visible summary text.", content)
            self.assertIn("Raw HTML/CSS payload omitted from Miro sync", content)
            self.assertIn("Code-heavy block omitted from Miro sync", content)
            self.assertNotIn("<!DOCTYPE html>", content)
            self.assertNotIn(".com-sec-card-1__icon--pink", content)
            self.assertNotIn("<div class=", content)

    def test_publish_direct_keeps_failed_results_without_applying_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath, MIRO_API_TOKEN="test-token")
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            plan_path = runtime_dir / "plan.json"
            plan_path.write_text(json.dumps(_sample_publish_plan(root), indent=2) + "\n", encoding="utf-8")

            server = _MiroApiTestServer(("127.0.0.1", 0), fail_bulk=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "publish-direct",
                        "--project-root",
                        str(root),
                        "--config",
                        str(root / ".bmad-miro.toml"),
                        "--plan",
                        str(plan_path),
                        "--results",
                        ".bmad-miro-sync/run/results.json",
                        "--api-base-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--apply-results",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(result.returncode, 1)
            self.assertIn("did not complete cleanly", result.stderr)
            results_payload = json.loads((runtime_dir / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(results_payload["run_status"], "failed")
            self.assertEqual(results_payload["items"][0]["execution_status"], "failed")
            self.assertFalse((root / ".bmad-miro-sync/state.json").exists())


def _sample_publish_plan(root: Path) -> dict[str, object]:
    artifact_id = "_bmad-output/planning-artifacts/prd.md#prd"
    source_artifact_id = "_bmad-output/planning-artifacts/prd.md"
    return {
        "board_url": "https://miro.com/app/board/uXjVGixS6vQ=/",
        "project_root": str(root),
        "config_path": str(root / ".bmad-miro.toml"),
        "manifest_path": ".bmad-miro-sync/state.json",
        "warnings": [],
        "object_strategies": [],
        "artifacts": [
            {
                "artifact_id": artifact_id,
                "source_artifact_id": source_artifact_id,
                "title": "PRD",
                "kind": "prd",
                "phase": "planning",
                "phase_zone": "planning",
                "workstream": "product",
                "collaboration_intent": "anchor",
                "relative_path": source_artifact_id,
                "sha256": "sha-123",
                "source_type": "file",
                "heading_level": 1,
                "parent_artifact_id": None,
                "section_path": ["prd"],
                "section_title_path": ["PRD"],
                "section_slug": "prd",
                "section_sibling_index": 1,
                "lineage_key": "prd",
                "lineage_status": "new",
                "previous_artifact_id": None,
                "previous_parent_artifact_id": None,
            }
        ],
        "operations": [
            {
                "op_id": "workstream:planning:product",
                "action": "ensure_workstream_anchor",
                "item_type": "workstream_anchor",
                "title": "Product",
                "phase": "planning",
                "phase_zone": "planning",
                "workstream": "product",
                "collaboration_intent": "orientation",
                "artifact_id": "workstream:planning:product",
                "source_artifact_id": "workstream:planning:product",
                "target_key": "workstream:planning:product",
                "container_target_key": None,
                "object_family": "workstream_anchor",
                "preferred_item_type": "workstream_anchor",
                "resolved_item_type": "workstream_anchor",
                "degraded": False,
                "fallback_reason": None,
                "degraded_warning": None,
                "status": "pending",
                "lifecycle_state": "active",
                "deterministic_order": {
                    "zone_rank": 1,
                    "workstream_rank": 1,
                    "object_rank": 1,
                    "artifact_rank": 0,
                    "section_rank": 0,
                },
            },
            {
                "op_id": f"doc:{artifact_id}",
                "action": "create_doc",
                "item_type": "doc",
                "title": "PRD",
                "phase": "planning",
                "phase_zone": "planning",
                "workstream": "product",
                "collaboration_intent": "anchor",
                "artifact_id": artifact_id,
                "source_artifact_id": source_artifact_id,
                "target_key": f"artifact:{artifact_id}",
                "container_target_key": "workstream:planning:product",
                "content": "# PRD\n\nBody\n",
                "object_family": "artifact_content",
                "preferred_item_type": "doc",
                "resolved_item_type": "doc",
                "degraded": False,
                "fallback_reason": None,
                "degraded_warning": None,
                "status": "pending",
                "lifecycle_state": "active",
                "heading_level": 1,
                "parent_artifact_id": None,
                "deterministic_order": {
                    "zone_rank": 1,
                    "workstream_rank": 1,
                    "object_rank": 2,
                    "artifact_rank": 1,
                    "section_rank": 1,
                },
            },
        ],
    }


def parse_form_body(body: str) -> dict[str, str]:
    values = {}
    for key, raw_value in parse_qsl(body, keep_blank_values=True):
        values[key] = raw_value
    return values


def _wait_for_port(port: int, *, attempts: int = 50) -> None:
    import socket
    import time

    for _ in range(attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for localhost:{port}")

    def test_ingest_comments_rejects_empty_comment_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text('{"version": 3, "items": {}}\n', encoding="utf-8")
            (runtime_dir / "comments.json").write_text(json.dumps({"comments": [{}]}, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "ingest-comments",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--comments",
                    str(runtime_dir / "comments.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Comment entry at comments[0] is empty.", result.stderr)
            self.assertFalse((root / "_bmad-output/review-artifacts/miro-comments.md").exists())

    def test_apply_results_reports_invalid_results_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir = root / ".bmad-miro-sync/run"
            runtime_dir.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (runtime_dir / "plan.json").write_text(json.dumps({"operations": []}, indent=2) + "\n", encoding="utf-8")
            (runtime_dir / "results.json").write_text("{\n", encoding="utf-8")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(apply_result.returncode, 1)
            self.assertIn("Invalid results JSON", apply_result.stderr)
            self.assertFalse((root / ".bmad-miro-sync/state.json").exists())

    def test_apply_results_reads_runtime_plan_and_persists_pending_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)

            bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            artifact = next(artifact for artifact in bundle["artifacts"] if artifact["artifact_id"].endswith("#prd"))
            results_payload = {
                "run_status": "partial",
                "executed_at": "2026-04-17T22:55:00Z",
                "items": [
                    {
                        "artifact_id": artifact["artifact_id"],
                        "artifact_sha256": artifact["sha256"],
                        "item_type": "doc",
                        "item_id": "doc-123",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                        "title": artifact["title"],
                        "target_key": f"artifact:{artifact['artifact_id']}",
                        "source_artifact_id": artifact["source_artifact_id"],
                        "phase_zone": artifact["phase_zone"],
                        "workstream": artifact["workstream"],
                        "collaboration_intent": artifact["collaboration_intent"],
                        "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                        "heading_level": artifact["heading_level"],
                        "parent_artifact_id": artifact["parent_artifact_id"],
                        "section_path": artifact["section_path"],
                        "section_title_path": artifact["section_title_path"],
                        "section_slug": artifact["section_slug"],
                        "section_sibling_index": artifact["section_sibling_index"],
                        "lineage_key": artifact["lineage_key"],
                        "lineage_status": artifact["lineage_status"],
                        "previous_artifact_id": artifact["previous_artifact_id"],
                        "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                        "execution_status": "created",
                        "updated_at": "2026-04-17T22:55:00Z",
                    }
                ],
            }
            (runtime_dir / "results.json").write_text(json.dumps(results_payload, indent=2) + "\n", encoding="utf-8")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)

            state = json.loads((root / ".bmad-miro-sync/state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["version"], 3)
            self.assertEqual(state["last_run"]["run_status"], "partial")
            self.assertGreater(state["last_run"]["pending_operation_count"], 0)
            self.assertIn("doc:_bmad-output/planning-artifacts/prd.md#prd", state["operations"])
            self.assertEqual(
                state["operations"]["doc:_bmad-output/planning-artifacts/prd.md#prd"]["execution_status"],
                "created",
            )
            self.assertEqual(state["operations"]["zone:planning"]["execution_status"], "pending")

    def test_apply_results_resolves_relative_runtime_paths_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root = temp_root / "project"
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)

            bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            artifact = next(artifact for artifact in bundle["artifacts"] if artifact["artifact_id"].endswith("#prd"))
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "partial",
                        "executed_at": "2026-04-17T23:15:00Z",
                        "items": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-17T23:15:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    ".bmad-miro-sync/run/results.json",
                ],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)

            state = json.loads((root / ".bmad-miro-sync/state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["last_run"]["plan_path"], ".bmad-miro-sync/run/plan.json")
            self.assertEqual(state["last_run"]["results_path"], ".bmad-miro-sync/run/results.json")


class CliTriageFeedbackTests(unittest.TestCase):
    def test_triage_feedback_writes_default_decision_records_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text(
                json.dumps(
                    {
                        "version": 3,
                        "items": {
                            "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "title": "PRD / Goals",
                                "item_id": "doc-123",
                                "item_type": "doc",
                                "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                            }
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            review_input = root / ".bmad-miro-sync/run/review-input.json"
            review_input.parent.mkdir(parents=True, exist_ok=True)
            review_input.write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "topic": "Acceptance criteria",
                                "author": "Jane Doe",
                                "created_at": "2026-04-15T11:00:00Z",
                                "body": "Please expand the acceptance criteria.",
                            }
                        ],
                        "triage": [
                            {
                                "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "topic": "Acceptance criteria",
                                "status": "deferred",
                                "owner": "Product",
                                "rationale": "Queue this after Story 3.3.",
                                "follow_up_notes": "Revisit after readiness summary work.",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "triage-feedback",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--input",
                    str(review_input),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            payload = json.loads(result.stdout)
            output_path = Path(payload["output_path"])
            self.assertTrue(output_path.exists())
            self.assertEqual(
                output_path,
                root / "_bmad-output/review-artifacts/decision-records.md",
            )
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Status: Deferred", content)
            self.assertIn("Owner: Product", content)
            self.assertIn("Follow-up notes: Revisit after readiness summary work.", content)

    def test_triage_feedback_surfaces_invalid_status_as_operator_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text(
                json.dumps(
                    {
                        "version": 3,
                        "items": {
                            "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "title": "PRD / Goals",
                            }
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            review_input = root / ".bmad-miro-sync/run/review-input.json"
            review_input.parent.mkdir(parents=True, exist_ok=True)
            review_input.write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "topic": "Acceptance criteria",
                                "author": "Jane Doe",
                                "body": "Please expand the acceptance criteria.",
                            }
                        ],
                        "triage": [
                            {
                                "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "topic": "Acceptance criteria",
                                "status": "done",
                                "owner": "Product",
                                "rationale": "No further work needed.",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "triage-feedback",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--input",
                    str(review_input),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unknown decision status", result.stderr)

    def test_triage_feedback_rejects_markdown_output_that_collides_with_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text(json.dumps({"version": 3, "items": {}}, indent=2) + "\n", encoding="utf-8")
            review_input = root / ".bmad-miro-sync/run/review-input.json"
            review_input.parent.mkdir(parents=True, exist_ok=True)
            review_input.write_text(json.dumps({"comments": []}) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "triage-feedback",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--input",
                    str(review_input),
                    "--output",
                    "_bmad-output/review-artifacts/decision-records.json",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Output path collision", result.stderr)


class CliIngestCommentsTests(unittest.TestCase):
    def test_ingest_comments_resolves_relative_paths_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root = temp_root / "project"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync/run").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text(
                json.dumps(
                    {
                        "version": 3,
                        "items": {
                            "_bmad-output/planning-artifacts/prd.md#prd/goals": {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "title": "PRD / Goals",
                                "item_id": "doc-123",
                                "item_type": "doc",
                                "target_key": "artifact:_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "miro_url": "https://miro.com/app/board/example/?moveToWidget=doc-123",
                            }
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / ".bmad-miro-sync/run/comments.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "topic": "Acceptance criteria",
                                "author": "Jane Doe",
                                "created_at": "2026-04-15T11:00:00Z",
                                "body": "Please expand the acceptance criteria.",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "ingest-comments",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--comments",
                    ".bmad-miro-sync/run/comments.json",
                ],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                Path(payload["output_path"]),
                root / "_bmad-output/review-artifacts/miro-comments.md",
            )
            content = (root / "_bmad-output/review-artifacts/miro-comments.md").read_text(encoding="utf-8")
            self.assertIn("PRD / Goals", content)
            self.assertFalse((temp_root / "_bmad-output/review-artifacts/miro-comments.md").exists())

    def test_triage_feedback_rejects_malformed_top_level_review_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text('{"version": 3, "items": {}}\n', encoding="utf-8")
            review_input = root / ".bmad-miro-sync/run/review-input.json"
            review_input.parent.mkdir(parents=True, exist_ok=True)
            review_input.write_text("[\n  \"not-an-object\"\n]\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "triage-feedback",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--input",
                    str(review_input),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Review input must be a JSON object", result.stderr)

    def test_triage_feedback_rejects_malformed_review_input_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text('{"version": 3, "items": {}}\n', encoding="utf-8")
            review_input = root / ".bmad-miro-sync/run/review-input.json"
            review_input.parent.mkdir(parents=True, exist_ok=True)
            review_input.write_text("{not json\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "triage-feedback",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--input",
                    str(review_input),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid review input JSON", result.stderr)

    def test_triage_feedback_reports_missing_review_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro-sync").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / ".bmad-miro-sync/state.json").write_text('{"version": 3, "items": {}}\n', encoding="utf-8")
            review_input = root / ".bmad-miro-sync/run/missing.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "triage-feedback",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--input",
                    str(review_input),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Review input file not found", result.stderr)

    def test_apply_results_persists_removed_history_from_runtime_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(
                CONFIG_TEXT
                + """
[sync]
removed_item_policy = "remove"
""",
                encoding="utf-8",
            )
            artifact_path = root / "_bmad-output/planning-artifacts/prd.md"
            artifact_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)

            bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            section = next(artifact for artifact in bundle["artifacts"] if artifact["artifact_id"].endswith("#prd/goals"))
            create_results = {
                "run_status": "complete",
                "executed_at": "2026-04-18T10:20:00Z",
                "items": [
                    {
                        "op_id": f"doc:{artifact['artifact_id']}",
                        "artifact_id": artifact["artifact_id"],
                        "artifact_sha256": artifact["sha256"],
                        "item_type": "doc",
                        "item_id": f"doc-{index}",
                        "miro_url": f"https://miro.com/app/board/x/?moveToWidget=doc-{index}",
                        "title": artifact["title"],
                        "target_key": f"artifact:{artifact['artifact_id']}",
                        "source_artifact_id": artifact["source_artifact_id"],
                        "phase_zone": artifact["phase_zone"],
                        "workstream": artifact["workstream"],
                        "collaboration_intent": artifact["collaboration_intent"],
                        "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                        "heading_level": artifact["heading_level"],
                        "parent_artifact_id": artifact["parent_artifact_id"],
                        "section_path": artifact["section_path"],
                        "section_title_path": artifact["section_title_path"],
                        "section_slug": artifact["section_slug"],
                        "section_sibling_index": artifact["section_sibling_index"],
                        "lineage_key": artifact["lineage_key"],
                        "lineage_status": artifact["lineage_status"],
                        "previous_artifact_id": artifact["previous_artifact_id"],
                        "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                        "execution_status": "created",
                        "updated_at": "2026-04-18T10:20:00Z",
                    }
                    for index, artifact in enumerate(bundle["artifacts"], start=1)
                ],
            }
            (runtime_dir / "results.json").write_text(json.dumps(create_results, indent=2) + "\n", encoding="utf-8")

            apply_create = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_create.returncode, 0, apply_create.stderr)

            artifact_path.write_text("# PRD\n\nBody\n", encoding="utf-8")
            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)

            bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            remove_operation = next(
                operation for operation in bundle["operations"] if operation["artifact_id"] == section["artifact_id"]
            )
            self.assertEqual(remove_operation["action"], "remove_doc")
            remove_results = {
                "run_status": "complete",
                "executed_at": "2026-04-18T10:25:00Z",
                "items": [
                    {
                        "op_id": remove_operation["op_id"],
                        "artifact_id": remove_operation["artifact_id"],
                        "item_type": "doc",
                        "execution_status": "removed",
                    }
                ],
            }
            (runtime_dir / "results.json").write_text(json.dumps(remove_results, indent=2) + "\n", encoding="utf-8")

            apply_remove = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_remove.returncode, 0, apply_remove.stderr)
            state = json.loads((root / ".bmad-miro-sync/state.json").read_text(encoding="utf-8"))
            removed_item = state["items"][section["artifact_id"]]
            self.assertEqual(removed_item["item_id"], "doc-2")
            self.assertEqual(removed_item["lifecycle_state"], "removed")
            self.assertEqual(removed_item["execution_status"], "removed")
            self.assertEqual(
                state["operations"][remove_operation["op_id"]]["execution_status"],
                "removed",
            )


class CliReadinessTests(unittest.TestCase):
    def test_summarize_readiness_writes_default_summary_and_handoff_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            review_dir = root / "_bmad-output/review-artifacts"
            review_dir.mkdir(parents=True)
            (review_dir / "decision-records.json").write_text(
                json.dumps(
                    {
                        "decision_records": [
                            {
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "section_title": "PRD / Goals",
                                "topic": "KPIs",
                                "status": "accepted",
                                "owner": "Product",
                                "rationale": "Accepted.",
                                "comments": [],
                                "unresolved_reasons": [],
                            },
                            {
                                "source_artifact_id": "_bmad-output/planning-artifacts/ux-design-specification.md",
                                "section_id": "_bmad-output/planning-artifacts/ux-design-specification.md#ux/flows",
                                "section_title": "UX / Flows",
                                "topic": "Navigation handoff",
                                "status": "blocked",
                                "owner": "UX",
                                "rationale": "Prototype annotations are incomplete.",
                                "follow_up_notes": "Add the missing transition notes before handoff.",
                                "comments": [],
                                "unresolved_reasons": [],
                            },
                            {
                                "source_artifact_id": "_bmad-output/planning-artifacts/architecture.md",
                                "section_id": "_bmad-output/planning-artifacts/architecture.md#architecture/data",
                                "section_title": "Architecture / Data",
                                "topic": "Schema",
                                "status": "accepted",
                                "owner": "Architecture",
                                "rationale": "Approved.",
                                "comments": [],
                                "unresolved_reasons": [],
                            },
                            {
                                "source_artifact_id": "_bmad-output/implementation-artifacts/epics.md",
                                "section_id": "_bmad-output/implementation-artifacts/epics.md#epics/story-sequencing",
                                "section_title": "Epics / Story sequencing",
                                "topic": "Sequencing",
                                "status": "resolved",
                                "owner": "Delivery",
                                "rationale": "Ready for handoff.",
                                "comments": [],
                                "unresolved_reasons": [],
                            },
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "summarize-readiness",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            summary_path = root / "_bmad-output/implementation-artifacts/implementation-readiness.md"
            handoff_path = root / "_bmad-output/implementation-artifacts/implementation-handoff.md"
            self.assertEqual(Path(payload["output_path"]), summary_path)
            self.assertEqual(Path(payload["handoff_output_path"]), handoff_path)
            self.assertEqual(payload["overall_state"], "blocked")

            summary = summary_path.read_text(encoding="utf-8")
            handoff = handoff_path.read_text(encoding="utf-8")
            self.assertIn("Overall readiness: Blocked", summary)
            self.assertIn("## Source Artifacts", summary)
            self.assertIn("## Review Activity", summary)
            self.assertIn("## Readiness Conclusions", summary)
            self.assertIn("Navigation handoff [Blocked]", summary)
            self.assertIn("Artifact: `_bmad-output/planning-artifacts/ux-design-specification.md`", summary)

            self.assertIn("Overall readiness: Blocked", handoff)
            self.assertIn("## Workstream Handoff", handoff)
            self.assertIn("Ready for implementation handoff: No", handoff)
            self.assertIn("Navigation handoff [Blocked]", handoff)
            self.assertIn("Follow-up: Add the missing transition notes before handoff.", handoff)

    def test_summarize_readiness_reports_missing_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "summarize-readiness",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Decision input file not found", result.stderr)

    def test_summarize_readiness_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            review_dir = root / "_bmad-output/review-artifacts"
            review_dir.mkdir(parents=True)
            (review_dir / "decision-records.json").write_text("{not json\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "summarize-readiness",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid decision input JSON", result.stderr)

    def test_summarize_readiness_rejects_malformed_decision_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            review_dir = root / "_bmad-output/review-artifacts"
            review_dir.mkdir(parents=True)
            (review_dir / "decision-records.json").write_text(json.dumps({"wrong": []}) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "summarize-readiness",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Decision sidecar payload must include a 'decision_records' list.", result.stderr)

    def test_summarize_readiness_rejects_unknown_decision_status_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            review_dir = root / "_bmad-output/review-artifacts"
            review_dir.mkdir(parents=True)
            (review_dir / "decision-records.json").write_text(
                json.dumps(
                    {
                        "decision_records": [
                            {
                                "source_artifact_id": "_bmad-output/planning-artifacts/prd.md",
                                "section_id": "_bmad-output/planning-artifacts/prd.md#prd/goals",
                                "section_title": "PRD / Goals",
                                "topic": "Scope",
                                "status": "done",
                                "owner": "Product",
                                "rationale": "Complete.",
                                "comments": [],
                                "unresolved_reasons": [],
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "summarize-readiness",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unknown decision status 'done' in serialized decision record.", result.stderr)

    def test_summarize_readiness_rejects_overlapping_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            review_dir = root / "_bmad-output/review-artifacts"
            review_dir.mkdir(parents=True)
            decision_path = review_dir / "decision-records.json"
            decision_path.write_text(json.dumps({"decision_records": []}) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "summarize-readiness",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output",
                    str(decision_path),
                    "--handoff-output",
                    str(decision_path),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Output path collision", result.stderr)

    def test_export_and_apply_results_round_trip_layout_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            artifact_path = root / "_bmad-output/planning-artifacts/prd.md"
            artifact_path.write_text("# PRD\n\n## Goals\n\nBody\n", encoding="utf-8")

            export_initial = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_initial.returncode, 0, export_initial.stderr)

            initial_bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            goals_artifact = next(
                artifact for artifact in initial_bundle["artifacts"] if artifact["artifact_id"].endswith("#prd/goals")
            )
            initial_results = {
                "run_status": "complete",
                "executed_at": "2026-04-18T10:50:00Z",
                "items": [
                    {
                        "op_id": f"doc:{goals_artifact['artifact_id']}",
                        "artifact_id": goals_artifact["artifact_id"],
                        "artifact_sha256": goals_artifact["sha256"],
                        "item_type": "doc",
                        "item_id": "doc-goals",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-goals",
                        "title": "PRD / Goals",
                        "target_key": f"artifact:{goals_artifact['artifact_id']}",
                        "source_artifact_id": goals_artifact["source_artifact_id"],
                        "phase_zone": goals_artifact["phase_zone"],
                        "workstream": goals_artifact["workstream"],
                        "collaboration_intent": goals_artifact["collaboration_intent"],
                        "container_target_key": f"workstream:{goals_artifact['phase_zone']}:{goals_artifact['workstream']}",
                        "heading_level": goals_artifact["heading_level"],
                        "parent_artifact_id": goals_artifact["parent_artifact_id"],
                        "section_path": goals_artifact["section_path"],
                        "section_title_path": goals_artifact["section_title_path"],
                        "section_slug": goals_artifact["section_slug"],
                        "section_sibling_index": goals_artifact["section_sibling_index"],
                        "lineage_key": goals_artifact["lineage_key"],
                        "lineage_status": goals_artifact["lineage_status"],
                        "previous_artifact_id": goals_artifact["previous_artifact_id"],
                        "previous_parent_artifact_id": goals_artifact["previous_parent_artifact_id"],
                        "layout_snapshot": {
                            "x": 125,
                            "y": 245,
                            "width": 360,
                            "height": 180,
                            "parent_item_id": "frame-1",
                            "group_id": "group-1",
                        },
                        "execution_status": "created",
                        "updated_at": "2026-04-18T10:50:00Z",
                    }
                ],
            }
            (runtime_dir / "results.json").write_text(json.dumps(initial_results, indent=2) + "\n", encoding="utf-8")

            apply_initial = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_initial.returncode, 0, apply_initial.stderr)

            artifact_path.write_text("# PRD\n\n## Goals\n\nUpdated body\n", encoding="utf-8")
            export_repeat = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_repeat.returncode, 0, export_repeat.stderr)

            repeat_bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            repeat_operation = next(
                operation for operation in repeat_bundle["operations"] if operation["artifact_id"].endswith("#prd/goals")
            )
            self.assertEqual(repeat_operation["action"], "update_doc")
            self.assertEqual(repeat_operation["layout_policy"], "preserve")
            self.assertEqual(repeat_operation["layout_snapshot"]["group_id"], "group-1")

            instructions = (runtime_dir / "instructions.md").read_text(encoding="utf-8")
            self.assertIn("layout_policy", instructions)
            self.assertIn("layout_snapshot", instructions)
            self.assertIn("resolved_item_type", instructions)

            results_template = json.loads((runtime_dir / "results.template.json").read_text(encoding="utf-8"))
            self.assertEqual(results_template["object_strategies"][0]["resolved_item_type"], "<resolved item type>")
            self.assertEqual(results_template["items"][0]["layout_policy"], "<auto|preserve>")
            self.assertEqual(results_template["items"][0]["layout_snapshot"]["group_id"], "<group id or null>")
            self.assertEqual(results_template["items"][0]["preferred_item_type"], "<preferred item type>")

            repeat_results = {
                "run_status": "complete",
                "executed_at": "2026-04-18T11:00:00Z",
                "items": [
                    {
                        "op_id": repeat_operation["op_id"],
                        "artifact_id": repeat_operation["artifact_id"],
                        "artifact_sha256": next(
                            artifact["sha256"]
                            for artifact in repeat_bundle["artifacts"]
                            if artifact["artifact_id"] == repeat_operation["artifact_id"]
                        ),
                        "item_type": "doc",
                        "item_id": "doc-goals",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-goals",
                        "title": repeat_operation["title"],
                        "target_key": repeat_operation["target_key"],
                        "source_artifact_id": repeat_operation["source_artifact_id"],
                        "phase_zone": repeat_operation["phase_zone"],
                        "workstream": repeat_operation["workstream"],
                        "collaboration_intent": repeat_operation["collaboration_intent"],
                        "container_target_key": repeat_operation["container_target_key"],
                        "heading_level": repeat_operation["heading_level"],
                        "parent_artifact_id": repeat_operation["parent_artifact_id"],
                        "layout_policy": "preserve",
                        "layout_snapshot": {
                            "x": 180,
                            "y": 255,
                            "width": 420,
                            "height": 210,
                            "parent_item_id": "frame-2",
                            "group_id": "group-9",
                        },
                        "execution_status": "updated",
                        "updated_at": "2026-04-18T11:00:00Z",
                    }
                ],
            }
            (runtime_dir / "results.json").write_text(json.dumps(repeat_results, indent=2) + "\n", encoding="utf-8")

            apply_repeat = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "apply-results",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--results",
                    str(runtime_dir / "results.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_repeat.returncode, 0, apply_repeat.stderr)

            state = json.loads((root / ".bmad-miro-sync/state.json").read_text(encoding="utf-8"))
            updated_item = state["items"][repeat_operation["artifact_id"]]
            self.assertEqual(updated_item["layout_policy"], "preserve")
            self.assertEqual(updated_item["layout_snapshot"]["parent_item_id"], "frame-2")
            self.assertEqual(updated_item["layout_snapshot"]["group_id"], "group-9")


class CliRenderHostInstructionsTests(unittest.TestCase):
    def test_render_host_instructions_resolves_relative_output_path_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root = temp_root / "project"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            render_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "render-host-instructions",
                    "--project-root",
                    str(root),
                    "--config",
                    ".bmad-miro.toml",
                    "--output",
                    ".bmad-miro-sync/run/instructions.md",
                ],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(render_result.returncode, 0, render_result.stderr)
            self.assertTrue((root / ".bmad-miro-sync/run/instructions.md").exists())
            self.assertFalse((temp_root / ".bmad-miro-sync/run/instructions.md").exists())

    def test_non_codex_hosts_document_layout_policy_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            for host in ("generic", "claude-code", "gemini-cli"):
                render_result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "bmad_miro_sync",
                        "render-host-instructions",
                        "--project-root",
                        str(root),
                        "--config",
                        str(root / ".bmad-miro.toml"),
                        "--host",
                        host,
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(render_result.returncode, 0, render_result.stderr)
                self.assertIn("layout_policy = preserve", render_result.stdout)
                self.assertIn("layout_policy = auto", render_result.stdout)
                self.assertIn("layout_snapshot", render_result.stdout)
                self.assertIn("live parent and grouping context", render_result.stdout)


class CliCollaborationWorkflowTests(unittest.TestCase):
    def test_run_codex_collaboration_workflow_rejects_out_of_repo_runtime_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "project"
            outside_root = Path(tmpdir) / "outside"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            outside_root.mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            workflow_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "run-codex-collaboration-workflow",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--runtime-dir",
                    str(outside_root / "run"),
                    "--report",
                    str(outside_root / "collaboration-run.json"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(workflow_result.returncode, 1)
            self.assertIn("--runtime-dir must stay inside the project root", workflow_result.stderr)
            self.assertFalse((outside_root / "run/plan.json").exists())

    def test_run_codex_collaboration_workflow_rejects_runtime_dir_that_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            runtime_file = root / ".bmad-miro-sync" / "run"
            runtime_file.parent.mkdir(parents=True)
            runtime_file.write_text("not a directory\n", encoding="utf-8")

            workflow_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "run-codex-collaboration-workflow",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(workflow_result.returncode, 1)
            self.assertIn("Invalid repo-local runtime_dir:", workflow_result.stderr)
            self.assertIn("Choose a repo-local directory path for --runtime-dir", workflow_result.stderr)
            self.assertNotIn("Traceback", workflow_result.stderr)

    def test_run_codex_collaboration_workflow_rejects_report_path_that_is_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")
            report_dir = root / ".bmad-miro-sync" / "run" / "collaboration-run.json"
            report_dir.mkdir(parents=True)

            workflow_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "run-codex-collaboration-workflow",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(workflow_result.returncode, 1)
            self.assertIn("Invalid repo-local report path:", workflow_result.stderr)
            self.assertIn("Choose a repo-local file path for --report", workflow_result.stderr)
            self.assertNotIn("Traceback", workflow_result.stderr)

    def test_run_codex_collaboration_workflow_runs_full_cycle_with_default_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)

            bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            artifact = next(artifact for artifact in bundle["artifacts"] if artifact["artifact_id"].endswith("#prd"))
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            comments_payload = {
                "comments": [
                    {
                        "artifact_id": artifact["artifact_id"],
                        "section_id": artifact["artifact_id"],
                        "source_artifact_id": artifact["source_artifact_id"],
                        "section_title": artifact["title"],
                        "topic": "Acceptance criteria",
                        "author": "Reviewer",
                        "created_at": "2026-04-18T09:10:00Z",
                        "body": "Looks good.",
                        "published_object_id": "doc-123",
                        "published_object_type": "doc",
                        "published_object_reference": f"artifact:{artifact['artifact_id']}",
                        "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                    }
                ]
            }
            (runtime_dir / "comments.json").write_text(json.dumps(comments_payload, indent=2) + "\n", encoding="utf-8")
            (runtime_dir / "review-input.json").write_text(
                json.dumps(
                    {
                        **comments_payload,
                        "triage": [
                            {
                                "section_id": artifact["artifact_id"],
                                "topic": "Acceptance criteria",
                                "status": "accepted",
                                "owner": "product",
                                "rationale": "Approved in review",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            workflow_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "run-codex-collaboration-workflow",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(workflow_result.returncode, 0, workflow_result.stderr)
            payload = json.loads(workflow_result.stdout)
            self.assertEqual(payload["run_status"], "completed")
            self.assertEqual(payload["stages"]["publish"]["status"], "completed")
            self.assertEqual(payload["stages"]["apply-results"]["status"], "completed")
            self.assertEqual(payload["stages"]["ingest-comments"]["status"], "completed")
            self.assertEqual(payload["stages"]["triage-feedback"]["status"], "completed")
            self.assertEqual(payload["stages"]["summarize-readiness"]["status"], "completed")
            self.assertTrue((root / ".bmad-miro-sync/run/collaboration-run.json").exists())
            self.assertTrue((root / "_bmad-output/review-artifacts/decision-records.json").exists())
            self.assertTrue((root / "_bmad-output/implementation-artifacts/implementation-readiness.md").exists())

    def test_run_codex_collaboration_workflow_reports_stage_specific_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_dir = root / ".bmad-miro-sync/run"
            pythonpath = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ, PYTHONPATH=pythonpath)
            runtime_dir.mkdir(parents=True)
            (root / "_bmad-output/planning-artifacts").mkdir(parents=True)
            (root / ".bmad-miro.toml").write_text(CONFIG_TEXT, encoding="utf-8")
            (root / "_bmad-output/planning-artifacts/prd.md").write_text("# PRD\n\nBody\n", encoding="utf-8")

            export_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "export-codex-bundle",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                    "--output-dir",
                    str(runtime_dir),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)

            bundle = json.loads((runtime_dir / "codex-bundle.json").read_text(encoding="utf-8"))
            artifact = next(artifact for artifact in bundle["artifacts"] if artifact["artifact_id"].endswith("#prd"))
            (runtime_dir / "results.json").write_text(
                json.dumps(
                    {
                        "run_status": "complete",
                        "executed_at": "2026-04-18T09:00:00Z",
                        "items": [
                            {
                                "op_id": f"doc:{artifact['artifact_id']}",
                                "artifact_id": artifact["artifact_id"],
                                "artifact_sha256": artifact["sha256"],
                                "item_type": "doc",
                                "item_id": "doc-123",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                                "title": artifact["title"],
                                "target_key": f"artifact:{artifact['artifact_id']}",
                                "source_artifact_id": artifact["source_artifact_id"],
                                "phase_zone": artifact["phase_zone"],
                                "workstream": artifact["workstream"],
                                "collaboration_intent": artifact["collaboration_intent"],
                                "container_target_key": f"workstream:{artifact['phase_zone']}:{artifact['workstream']}",
                                "heading_level": artifact["heading_level"],
                                "parent_artifact_id": artifact["parent_artifact_id"],
                                "section_path": artifact["section_path"],
                                "section_title_path": artifact["section_title_path"],
                                "section_slug": artifact["section_slug"],
                                "section_sibling_index": artifact["section_sibling_index"],
                                "lineage_key": artifact["lineage_key"],
                                "lineage_status": artifact["lineage_status"],
                                "previous_artifact_id": artifact["previous_artifact_id"],
                                "previous_parent_artifact_id": artifact["previous_parent_artifact_id"],
                                "execution_status": "created",
                                "updated_at": "2026-04-18T09:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (runtime_dir / "comments.json").write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "artifact_id": artifact["artifact_id"],
                                "section_id": artifact["artifact_id"],
                                "source_artifact_id": artifact["source_artifact_id"],
                                "section_title": artifact["title"],
                                "topic": "Acceptance criteria",
                                "author": "Reviewer",
                                "created_at": "2026-04-18T09:10:00Z",
                                "body": "Needs triage.",
                                "published_object_id": "doc-123",
                                "published_object_type": "doc",
                                "published_object_reference": f"artifact:{artifact['artifact_id']}",
                                "miro_url": "https://miro.com/app/board/x/?moveToWidget=doc-123",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            workflow_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bmad_miro_sync",
                    "run-codex-collaboration-workflow",
                    "--project-root",
                    str(root),
                    "--config",
                    str(root / ".bmad-miro.toml"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(workflow_result.returncode, 1)
            payload = json.loads(workflow_result.stdout)
            self.assertEqual(payload["run_status"], "failed")
            self.assertEqual(payload["failed_stage"], "triage-feedback")
            self.assertEqual(payload["stages"]["apply-results"]["status"], "completed")
            self.assertEqual(payload["stages"]["ingest-comments"]["status"], "completed")
            self.assertEqual(payload["stages"]["triage-feedback"]["status"], "failed")
            self.assertTrue((root / ".bmad-miro-sync/run/plan.json").exists())
            self.assertTrue((root / "_bmad-output/review-artifacts/miro-comments.md").exists())


if __name__ == "__main__":
    unittest.main()
