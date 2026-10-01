from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .data import default_itinerary
from .models import DisruptionRequest
from .workflow import TravelReplanningWorkflow


API_PATH = "/api/replan"


class TravelAgentAPIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        if urlsplit(self.path).path != API_PATH:
            self._send_json(404, {"error": "Not found"})
            return
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        if urlsplit(self.path).path != API_PATH:
            self._send_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 1_000_000:
                raise ValueError("Request body must be between 1 byte and 1 MB")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            delay_hours = payload.get("delay_hours")
            if (
                isinstance(delay_hours, bool)
                or not isinstance(delay_hours, (int, float))
                or not math.isfinite(delay_hours)
                or delay_hours < 0
            ):
                raise ValueError("delay_hours must be a finite, non-negative number")
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
            return

        result = TravelReplanningWorkflow().run(
            default_itinerary(),
            DisruptionRequest(
                flight_id="flight-1",
                delay_by_seconds=int(timedelta(hours=delay_hours).total_seconds()),
            ),
        )
        self._send_json(200, asdict(result))

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=self._serialize_value).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Cannot serialize {type(value).__name__}")

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the travel-agent HTTP API.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: all interfaces)")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), TravelAgentAPIHandler)
    print(f"Travel-agent API listening on http://{args.host}:{args.port}{API_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping travel-agent API.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()