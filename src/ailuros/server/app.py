from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import urlparse

from ailuros.audit import build_audit_summary
from ailuros.errors import AilurosNotFoundError
from ailuros.replay import ReplayService
from ailuros.storage import SQLiteStorage

logger = logging.getLogger(__name__)


class _Handler(BaseHTTPRequestHandler):
    storage: SQLiteStorage | None = None

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/health":
                self._send_json({"status": "ok"})
                return

            storage = self._get_storage()
            if storage is None:
                self._send_error(503, "Storage not available")
                return

            if path == "/runs":
                runs = storage.list_runs()
                data = [run.model_dump(mode="json") for run in runs]
                self._send_json(data)
                return

            parts = path.split("/")
            if len(parts) == 4 and parts[1] == "runs":
                run_id = parts[2]
                if parts[3] == "replay":
                    self._handle_replay(storage, run_id)
                    return
                if parts[3] == "audit":
                    self._handle_audit(storage, run_id)
                    return

            self._send_error(404, "Not found")
        except Exception:
            logger.exception("unhandled error")
            self._send_error(500, "Internal server error")

    def _get_storage(self) -> SQLiteStorage | None:
        cls = self.__class__
        return getattr(cls, "storage", None)

    def _handle_replay(self, storage: SQLiteStorage, run_id: str) -> None:
        try:
            events = ReplayService(storage).load_run(run_id)
        except AilurosNotFoundError:
            self._send_error(404, f"Run not found: {run_id}")
            return
        data = [event.model_dump(mode="json") for event in events]
        self._send_json(data)

    def _handle_audit(self, storage: SQLiteStorage, run_id: str) -> None:
        try:
            events = ReplayService(storage).load_run(run_id)
            summary = build_audit_summary(events)
        except AilurosNotFoundError:
            self._send_error(404, f"Run not found: {run_id}")
            return
        self._send_json({
            "decision": summary.decision,
            "reason": summary.reason,
            "tool": summary.tool,
            "path_validation": summary.path_validation,
        })

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("access: %s", format % args)


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def create_app(storage: SQLiteStorage) -> type[BaseHTTPRequestHandler]:
    cls = type("ReadOnlyHandler", (_Handler,), {"storage": storage})
    return cls


def run_server(
    storage: SQLiteStorage,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    handler = create_app(storage)
    server = _Server((host, port), handler)
    logger.info("server listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("server shutting down")
        server.shutdown()
