import json
import hmac
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .scraper import clear_scrape_cache, scrape_urls

API_VERSION = "0.1.0"


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return False


def _is_cache_admin(handler: BaseHTTPRequestHandler) -> bool:
    expected_token = os.getenv("CACHE_ADMIN_TOKEN")
    provided_token = handler.headers.get("X-Cache-Admin-Token", "")
    return bool(expected_token) and hmac.compare_digest(provided_token, expected_token)


class RapidAPIHandler(BaseHTTPRequestHandler):
    server_version = "RapidAPIScraper/0.1"

    def do_GET(self) -> None:
        if self.path == "/":
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "name": "email-scraper-api",
                    "status": "running",
                    "version": API_VERSION,
                    "endpoints": [
                        "GET /",
                        "GET /health",
                        "GET /version",
                        "POST /validate-url",
                        "POST /scrape-email",
                        "POST /scrape-emails",
                        "POST /cache/clear",
                    ],
                },
            )
            return

        if self.path == "/health":
            _json_response(self, HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/version":
            _json_response(self, HTTPStatus.OK, {"version": API_VERSION})
            return

        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
            return

        if self.path == "/cache/clear":
            if not _is_cache_admin(self):
                _json_response(self, HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
                return

            cleared_count = clear_scrape_cache()
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "success": True,
                    "cleared": cleared_count,
                },
            )
            return

        if self.path == "/validate-url":
            raw_url = payload.get("url", "")
            is_valid = isinstance(raw_url, str) and _is_valid_url(raw_url)
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "url": raw_url,
                    "valid": is_valid,
                },
            )
            return

        if self.path == "/scrape-email":
            raw_url = payload.get("url", "")
            if not isinstance(raw_url, str) or not _is_valid_url(raw_url):
                _json_response(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"error": "A valid 'url' field is required"},
                )
                return

            results = scrape_urls(
                [raw_url],
                verify=_as_bool(payload.get("verify", False)),
                js_render=_as_bool(payload.get("js_render", False)),
                delay_range=(0.0, 0.0),
            )
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "success": True,
                    "count": len(results),
                    "results": results,
                },
            )
            return

        if self.path != "/scrape-emails":
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        raw_urls = payload.get("URL", payload.get("websiteUrls", []))
        urls = raw_urls if isinstance(raw_urls, list) else str(raw_urls)
        results = scrape_urls(
            urls,
            verify=_as_bool(payload.get("verify", False)),
            js_render=_as_bool(payload.get("js_render", False)),
            delay_range=(0.0, 0.0),
        )

        _json_response(
            self,
            HTTPStatus.OK,
            {
                "success": True,
                "count": len(results),
                "results": results,
            },
        )

    def log_message(self, format: str, *args) -> None:
        return


def run() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), RapidAPIHandler)
    print(f"Serving API on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
