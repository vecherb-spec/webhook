from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from src.config import Settings, get_settings
from src.crm import CrmRouter
from src.marquiz import parse_marquiz_payload
from src.parser import is_quiz_application, parse_application

logger = logging.getLogger(__name__)


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(settings: Settings) -> type[BaseHTTPRequestHandler]:
    crm = CrmRouter(settings)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            logger.info("marquiz-http " + fmt, *args)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/health", "/marquiz/health"}:
                _json_response(self, 200, {"ok": True})
                return
            _json_response(self, 404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path not in {"/marquiz", "/incoming"}:
                _json_response(self, 404, {"ok": False, "error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                text = raw.decode("utf-8", errors="replace")
                if is_quiz_application(text):
                    data = {"_text": text}
                else:
                    _json_response(self, 400, {"ok": False, "error": "invalid_json"})
                    return

            try:
                if isinstance(data, dict) and data.get("_text"):
                    lead = parse_application(str(data["_text"]))
                elif isinstance(data, dict) and (
                    "answers" in data or "contacts" in data or "quiz" in data
                ):
                    lead = parse_marquiz_payload(data)
                else:
                    _json_response(
                        self,
                        400,
                        {"ok": False, "error": "unsupported_payload"},
                    )
                    return

                import asyncio

                result = asyncio.run(
                    crm.create_from_parsed(lead, meta={"source": "marquiz"})
                )
                logger.info(
                    "Marquiz lead created bitrix=%s espo=%s planfix=%s",
                    result.bitrix_id,
                    result.espo_id,
                    result.planfix_id,
                )
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "bitrix_lead_id": result.bitrix_id,
                        "espo_id": result.espo_id,
                        "planfix_id": result.planfix_id,
                        "errors": result.errors,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Marquiz webhook failed")
                _json_response(self, 500, {"ok": False, "error": str(exc)[:300]})

    return Handler


def start_marquiz_server(settings: Settings | None = None) -> ThreadingHTTPServer:
    settings = settings or get_settings()
    host = settings.marquiz_http_host
    port = settings.marquiz_http_port
    server = ThreadingHTTPServer((host, port), make_handler(settings))
    thread = threading.Thread(target=server.serve_forever, name="marquiz-http", daemon=True)
    thread.start()
    logger.info("Marquiz webhook listening on %s:%s/marquiz", host, port)
    return server
