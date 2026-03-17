from __future__ import annotations

from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import json
import logging
import time
import uuid

from .api import run_task, verify_task_run


logger = logging.getLogger("agentkit.server")


@dataclass(slots=True)
class ApiServerSettings:
    workspace: str
    host: str = "127.0.0.1"
    port: int = 8787
    require_api_token: bool = False
    api_token: str = ""
    log_level: str = "INFO"
    log_to_file: bool = True
    log_file: str = ".agentkit/logs/agentkit-serve.log"


@dataclass(slots=True)
class ApiServerHandle:
    httpd: ThreadingHTTPServer
    settings: ApiServerSettings


def _get_request_token(handler: BaseHTTPRequestHandler) -> str:
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :].strip()
    return handler.headers.get("X-AgentKit-Token", "").strip()


def _is_authorized(handler: BaseHTTPRequestHandler, settings: ApiServerSettings) -> bool:
    if not settings.require_api_token:
        return True
    if not settings.api_token:
        return False
    return _get_request_token(handler) == settings.api_token


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any], request_id: str) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-Id", request_id)
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(body)


def _build_handler(settings: ApiServerSettings) -> type[BaseHTTPRequestHandler]:
    class AgentKitApiHandler(BaseHTTPRequestHandler):
        server_version = "AgentKitAPI/0.1"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            logger.debug("httpserver: " + format, *args)

        def _request_id(self) -> str:
            explicit = self.headers.get("X-Request-Id", "").strip()
            return explicit or uuid.uuid4().hex[:12]

        def _read_json_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}
            raw = self.rfile.read(content_length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("request body must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("request body must be a JSON object")
            return parsed

        def do_GET(self) -> None:  # noqa: N802
            request_id = self._request_id()
            started = time.perf_counter()
            if self.path == "/health":
                _json_response(self, 200, {"status": "ok", "request_id": request_id}, request_id)
                logger.info("[%s] GET /health -> 200 (%.2fms)", request_id, (time.perf_counter() - started) * 1000)
                return
            _json_response(self, 404, {"error": "not_found", "request_id": request_id}, request_id)
            logger.info("[%s] GET %s -> 404 (%.2fms)", request_id, self.path, (time.perf_counter() - started) * 1000)

        def do_POST(self) -> None:  # noqa: N802
            request_id = self._request_id()
            started = time.perf_counter()
            client = self.client_address[0] if self.client_address else "unknown"

            if not _is_authorized(self, settings):
                _json_response(self, 401, {"error": "unauthorized", "request_id": request_id}, request_id)
                logger.warning("[%s] POST %s unauthorized from %s", request_id, self.path, client)
                return

            try:
                payload = self._read_json_body()
                if self.path == "/v1/tasks/run":
                    task_file = str(payload.get("task") or payload.get("task_file") or "")
                    if not task_file:
                        _json_response(self, 400, {"error": "task is required", "request_id": request_id}, request_id)
                        logger.info("[%s] POST /v1/tasks/run -> 400 missing task", request_id)
                        return
                    logger.info("[%s] POST /v1/tasks/run task=%s workspace=%s", request_id, task_file, settings.workspace)
                    result = run_task(workspace=settings.workspace, task_file=task_file)
                    response = asdict(result)
                    response["request_id"] = request_id
                    _json_response(self, 200, response, request_id)
                    logger.info(
                        "[%s] POST /v1/tasks/run -> 200 task_id=%s status=%s (%.2fms)",
                        request_id,
                        result.task_id,
                        result.status,
                        (time.perf_counter() - started) * 1000,
                    )
                    return

                if self.path == "/v1/tasks/verify":
                    task_id = str(payload.get("task_id") or "")
                    if not task_id:
                        _json_response(self, 400, {"error": "task_id is required", "request_id": request_id}, request_id)
                        logger.info("[%s] POST /v1/tasks/verify -> 400 missing task_id", request_id)
                        return
                    logger.info("[%s] POST /v1/tasks/verify task_id=%s", request_id, task_id)
                    ok, missing = verify_task_run(workspace=settings.workspace, task_id=task_id)
                    code = 200 if ok else 409
                    _json_response(self, code, {"ok": ok, "missing": missing, "request_id": request_id}, request_id)
                    logger.info(
                        "[%s] POST /v1/tasks/verify -> %s task_id=%s missing=%d (%.2fms)",
                        request_id,
                        code,
                        task_id,
                        len(missing),
                        (time.perf_counter() - started) * 1000,
                    )
                    return

                _json_response(self, 404, {"error": "not_found", "request_id": request_id}, request_id)
                logger.info("[%s] POST %s -> 404", request_id, self.path)
            except ValueError as exc:
                _json_response(self, 400, {"error": "bad_request", "detail": str(exc), "request_id": request_id}, request_id)
                logger.warning("[%s] POST %s -> 400 bad_request: %s", request_id, self.path, exc)
            except Exception as exc:  # pragma: no cover
                _json_response(
                    self,
                    500,
                    {"error": "internal_error", "detail": str(exc), "request_id": request_id},
                    request_id,
                )
                logger.exception("[%s] POST %s -> 500 internal_error", request_id, self.path)

    return AgentKitApiHandler


def create_http_server(settings: ApiServerSettings) -> ApiServerHandle:
    handler = _build_handler(settings)
    httpd = ThreadingHTTPServer((settings.host, settings.port), handler)
    return ApiServerHandle(httpd=httpd, settings=settings)


def serve(settings: ApiServerSettings) -> None:
    handle = create_http_server(settings)
    host, port = handle.httpd.server_address
    logger.info(
        "AgentKit API listening on http://%s:%s workspace=%s auth_required=%s log_level=%s log_to_file=%s log_file=%s",
        host,
        port,
        settings.workspace,
        settings.require_api_token,
        settings.log_level,
        settings.log_to_file,
        settings.log_file,
    )
    try:
        handle.httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("AgentKit API server interrupted")
    finally:
        handle.httpd.server_close()
        logger.info("AgentKit API server stopped")
