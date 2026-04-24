from __future__ import annotations

from datetime import UTC, datetime
from getpass import getpass
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
from typing import Any
from urllib import error, parse, request
import webbrowser


DEFAULT_AUTH_PATH = ".bmad-miro-auth.json"
DEFAULT_INSTALL_BASE_URL = "https://miro.com/app-install/"
DEFAULT_TOKEN_ENDPOINT = "https://api.miro.com/v1/oauth/token"
DEFAULT_LOCAL_REDIRECT_URI = "http://127.0.0.1:8899/callback"
DEFAULT_LOCAL_CALLBACK_TIMEOUT = 300


class MiroAuthError(RuntimeError):
    pass


def load_repo_auth_token(project_root: str | Path, auth_path: str | Path = DEFAULT_AUTH_PATH) -> str | None:
    path = _resolve_repo_local_path(Path(project_root).resolve(), auth_path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MiroAuthError(f"Unable to read repo-local Miro auth file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MiroAuthError(f"Repo-local Miro auth file {path} must contain a JSON object.")
    access_token = payload.get("access_token")
    if isinstance(access_token, str) and access_token:
        return access_token
    return None


def save_repo_auth(
    project_root: str | Path,
    payload: dict[str, Any],
    *,
    auth_path: str | Path = DEFAULT_AUTH_PATH,
) -> Path:
    root = Path(project_root).resolve()
    path = _resolve_repo_local_path(root, auth_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_install_url(client_id: str, redirect_uri: str, *, install_base_url: str = DEFAULT_INSTALL_BASE_URL) -> str:
    query = parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }
    )
    separator = "&" if "?" in install_base_url else "?"
    return f"{install_base_url}{separator}{query}"


def parse_install_url(install_url: str) -> tuple[str, str, str]:
    parsed = parse.urlparse(install_url)
    query = parse.parse_qs(parsed.query)
    client_id = _require_single_query_value(query, "client_id", "install URL")
    redirect_uri = _require_single_query_value(query, "redirect_uri", "install URL")
    base_url = parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return client_id, redirect_uri, base_url or DEFAULT_INSTALL_BASE_URL


def parse_authorization_code(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise MiroAuthError("Missing authorization code.")
    parsed = parse.urlparse(candidate)
    if parsed.scheme or parsed.netloc or parsed.query:
        query = parse.parse_qs(parsed.query)
        code = _require_single_query_value(query, "code", "redirected URL")
        return code
    return candidate


def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    token_endpoint: str = DEFAULT_TOKEN_ENDPOINT,
) -> dict[str, Any]:
    body = parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    req = request.Request(
        token_endpoint,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with request.urlopen(req) as response:
            raw = response.read()
    except error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise MiroAuthError(f"Miro token exchange failed with {exc.code}: {payload}") from exc
    except error.URLError as exc:
        raise MiroAuthError(f"Miro token exchange failed: {exc.reason}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise MiroAuthError("Miro token exchange returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise MiroAuthError("Miro token exchange returned an unexpected payload.")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise MiroAuthError("Miro token exchange did not return an access_token.")
    return payload


def interactive_setup(
    project_root: str | Path,
    *,
    auth_path: str | Path = DEFAULT_AUTH_PATH,
    token_endpoint: str = DEFAULT_TOKEN_ENDPOINT,
    install_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    redirected_value: str | None = None,
    callback_timeout: int = DEFAULT_LOCAL_CALLBACK_TIMEOUT,
    announce: bool = True,
) -> dict[str, Any]:
    resolved_client_id = client_id
    resolved_redirect_uri = redirect_uri
    install_base_url = DEFAULT_INSTALL_BASE_URL

    if install_url:
        parsed_client_id, parsed_redirect_uri, parsed_install_base_url = parse_install_url(install_url)
        resolved_client_id = resolved_client_id or parsed_client_id
        resolved_redirect_uri = resolved_redirect_uri or parsed_redirect_uri
        install_base_url = parsed_install_base_url or install_base_url

    if not resolved_client_id:
        install_url = _prompt("Paste the Miro app install URL (or leave blank to enter values manually): ").strip()
        if install_url:
            parsed_client_id, parsed_redirect_uri, parsed_install_base_url = parse_install_url(install_url)
            resolved_client_id = parsed_client_id
            resolved_redirect_uri = resolved_redirect_uri or parsed_redirect_uri
            install_base_url = parsed_install_base_url or install_base_url

    if not resolved_client_id:
        resolved_client_id = _prompt("Miro Client ID: ").strip()
    if not resolved_client_id:
        raise MiroAuthError("Miro Client ID is required.")

    if not resolved_redirect_uri:
        resolved_redirect_uri = (
            _prompt(f"Miro redirect URI [{DEFAULT_LOCAL_REDIRECT_URI}]: ").strip() or DEFAULT_LOCAL_REDIRECT_URI
        )

    resolved_install_url = build_install_url(
        resolved_client_id,
        resolved_redirect_uri,
        install_base_url=install_base_url,
    )
    if redirected_value is None and announce:
        print("\nOpen this Miro authorization URL in your browser:\n")
        print(resolved_install_url)
        _try_open_browser(resolved_install_url)
        if _is_local_callback_uri(resolved_redirect_uri):
            print(
                "\nAuthorize the app in your browser. The local callback server will capture the code automatically.\n"
            )
        else:
            print("\nAuthorize the app, then paste the redirected URL or just the code below.\n")

    resolved_client_secret = client_secret or getpass("Miro Client Secret: ")
    if not resolved_client_secret:
        raise MiroAuthError("Miro Client Secret is required.")

    if redirected_value is not None:
        resolved_redirected_value = redirected_value
    elif _is_local_callback_uri(resolved_redirect_uri):
        resolved_redirected_value = _wait_for_local_callback(resolved_redirect_uri, timeout_seconds=callback_timeout)
    else:
        resolved_redirected_value = _prompt("Redirected URL or code: ").strip()
    code = parse_authorization_code(resolved_redirected_value)

    token_payload = exchange_authorization_code(
        client_id=resolved_client_id,
        client_secret=resolved_client_secret,
        code=code,
        redirect_uri=resolved_redirect_uri,
        token_endpoint=token_endpoint,
    )
    stored_payload = {
        "access_token": token_payload["access_token"],
        "token_type": token_payload.get("token_type"),
        "scope": token_payload.get("scope"),
        "refresh_token": token_payload.get("refresh_token"),
        "expires_in": token_payload.get("expires_in"),
        "client_id": resolved_client_id,
        "redirect_uri": resolved_redirect_uri,
        "stored_at": _now_timestamp(),
    }
    path = save_repo_auth(project_root, stored_payload, auth_path=auth_path)
    return {
        "auth_path": str(path),
        "client_id": resolved_client_id,
        "redirect_uri": resolved_redirect_uri,
        "install_url": resolved_install_url,
        "token_type": token_payload.get("token_type"),
        "scope": token_payload.get("scope"),
        "expires_in": token_payload.get("expires_in"),
    }


def _prompt(message: str) -> str:
    return input(message)


def _try_open_browser(url: str) -> None:
    try:
        opened = webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        return
    if opened:
        print("\nOpened the authorization URL in your browser.\n")


def _is_local_callback_uri(redirect_uri: str) -> bool:
    parsed = parse.urlparse(redirect_uri)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and bool(parsed.path)
    )


def _wait_for_local_callback(redirect_uri: str, *, timeout_seconds: int) -> str:
    parsed = parse.urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    expected_path = parsed.path or "/"

    class _CallbackServer(HTTPServer):
        def __init__(self, server_address: tuple[str, int]) -> None:
            super().__init__(server_address, _CallbackHandler)
            self.event = threading.Event()
            self.result: str | None = None
            self.error_message: str | None = None
            self.expected_path = expected_path

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != self.server.expected_path:
                self.send_response(404)
                self.end_headers()
                return
            parsed_request = parse.urlparse(self.path)
            query = parse.parse_qs(parsed_request.query)
            if "error" in query:
                self.server.error_message = _require_single_query_value(query, "error", "callback URL")
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><p>Miro authorization failed. You can close this tab.</p></body></html>")
                self.server.event.set()
                return
            try:
                code = _require_single_query_value(query, "code", "callback URL")
            except MiroAuthError as exc:
                self.server.error_message = str(exc)
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><p>Missing authorization code. You can close this tab.</p></body></html>")
                self.server.event.set()
                return
            self.server.result = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><p>Miro authorization captured. You can close this tab and return to the terminal.</p></body></html>")
            self.server.event.set()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    try:
        server = _CallbackServer((host, port))
    except OSError as exc:
        raise MiroAuthError(f"Unable to start local callback server on {redirect_uri}: {exc}") from exc

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not server.event.wait(timeout_seconds):
            raise MiroAuthError(
                "Timed out waiting for the local Miro authorization callback. "
                f"Confirm the app redirect URI is set to {redirect_uri} and retry."
            )
        if server.error_message:
            raise MiroAuthError(f"Miro authorization callback failed: {server.error_message}")
        if not server.result:
            raise MiroAuthError("Local Miro authorization callback did not return a code.")
        return server.result
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _require_single_query_value(query: dict[str, list[str]], key: str, label: str) -> str:
    values = query.get(key)
    if not values or not values[0]:
        raise MiroAuthError(f"{label} is missing required query parameter: {key}")
    return values[0]


def _resolve_repo_local_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise MiroAuthError(f"Auth path must stay inside the project root ({project_root}): {resolved}") from exc
    return resolved


def _now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
