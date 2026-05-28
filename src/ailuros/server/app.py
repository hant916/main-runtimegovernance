from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import parse_qs, urlparse

from ailuros.audit import build_audit_summary
from ailuros.errors import AilurosNotFoundError
from ailuros.replay import ReplayService
from ailuros.storage import SQLiteStorage

logger = logging.getLogger(__name__)


def _build_evaluation_summary(ev: Any) -> dict[str, Any]:
    total = len(ev.findings) or 1
    passed = ev.passed
    return {
        "run_id": ev.run_id,
        "evaluator": ev.evaluator,
        "status": "passed" if passed else "failed",
        "total_cases": total,
        "passed_cases": total if passed else 0,
        "failed_cases": 0 if passed else total,
        "created_at": ev.created_at.isoformat(),
    }


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

    def _parse_pagination(self) -> tuple[int | None, int | None, str | None]:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        limit: int | None = None
        offset: int | None = None
        if "limit" in params:
            try:
                limit = int(params["limit"][0])
            except (ValueError, IndexError):
                return None, None, "limit must be a non-negative integer"
            if limit < 0:
                return None, None, "limit must be a non-negative integer"
        if "offset" in params:
            try:
                offset = int(params["offset"][0])
            except (ValueError, IndexError):
                return None, None, "offset must be a non-negative integer"
            if offset < 0:
                return None, None, "offset must be a non-negative integer"
        return limit, offset, None

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
                limit, offset, err = self._parse_pagination()
                if err:
                    self._send_error(400, err)
                    return
                runs = storage.list_runs(limit=limit, offset=offset)
                data = [run.model_dump(mode="json") for run in runs]
                self._send_json(data)
                return

            if path == "/evaluations":
                limit, offset, err = self._parse_pagination()
                if err:
                    self._send_error(400, err)
                    return
                evaluations = storage.list_evaluations(limit=limit, offset=offset)
                data = [_build_evaluation_summary(ev) for ev in evaluations]
                self._send_json(data)
                return

            parts = path.split("/")
            if len(parts) == 4 and parts[1] == "runs":
                run_id = parts[2]
                if parts[3] == "replay":
                    limit, offset, err = self._parse_pagination()
                    if err:
                        self._send_error(400, err)
                        return
                    self._handle_replay(storage, run_id, limit=limit, offset=offset)
                    return
                if parts[3] == "audit":
                    self._handle_audit(storage, run_id)
                    return
                if parts[3] == "events":
                    limit, offset, err = self._parse_pagination()
                    if err:
                        self._send_error(400, err)
                        return
                    self._handle_run_events(storage, run_id, limit=limit, offset=offset)
                    return

            if len(parts) == 3 and parts[1] == "runs" and parts[2]:
                self._handle_run_detail(storage, parts[2])
                return

            if len(parts) == 3 and parts[1] == "evaluations":
                run_id = parts[2]
                self._handle_evaluation_detail(storage, run_id)
                return

            self._send_error(404, "Not found")
        except Exception:
            logger.exception("unhandled error")
            self._send_error(500, "Internal server error")

    def _get_storage(self) -> SQLiteStorage | None:
        cls = self.__class__
        return getattr(cls, "storage", None)

    def _handle_replay(
        self, storage: SQLiteStorage, run_id: str,
        limit: int | None = None, offset: int | None = None,
    ) -> None:
        try:
            if limit is not None or offset is not None:
                events = storage.list_events(run_id, limit=limit, offset=offset)
            else:
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

    def _handle_run_detail(self, storage: SQLiteStorage, run_id: str) -> None:
        try:
            run = storage.get_run(run_id)
        except AilurosNotFoundError:
            self._send_error(404, f"Run not found: {run_id}")
            return
        self._send_json({
            "run": run.model_dump(mode="json"),
            "metadata_version": 1,
        })

    def _handle_run_events(
        self, storage: SQLiteStorage, run_id: str,
        limit: int | None = None, offset: int | None = None,
    ) -> None:
        try:
            events = storage.list_events(run_id, limit=limit, offset=offset)
        except AilurosNotFoundError:
            self._send_error(404, f"Run not found: {run_id}")
            return
        self._send_json({
            "events": [e.model_dump(mode="json") for e in events],
            "metadata_version": 1,
        })

    def _handle_evaluation_detail(self, storage: SQLiteStorage, run_id: str) -> None:
        try:
            ev = storage.get_evaluation(run_id)
        except AilurosNotFoundError:
            self._send_error(404, f"Evaluation not found for run: {run_id}")
            return
        self._send_json(ev.model_dump(mode="json"))

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
