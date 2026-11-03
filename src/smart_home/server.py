"""Loopback-only local demo; no cloud service or remote hardware exposure."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from typing import Any
from urllib.parse import urlparse

from .commands import process
from .controller import CommandError, Home, Operation

MAX_BODY = 16_384


class LocalServer(ThreadingHTTPServer):
    request_queue_size = 8

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def make_server(home: Home, *, host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise CommandError("The dashboard only binds to localhost. It is a local demo.")

    class Handler(BaseHTTPRequestHandler):
        server_version = "SmartHomeLocal/1"

        def log_message(self, *args: Any) -> None:
            return  # Do not log commands, code fields or private activity.

        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; "
                             "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                             "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def json(self, status: int, payload: Any) -> None:
            self.respond(status, json.dumps(payload, allow_nan=False).encode(), "application/json")

        def local_request(self) -> bool:
            expected = f"{self.server.server_name}:{self.server.server_port}"
            allowed = {expected, f"127.0.0.1:{self.server.server_port}",
                       f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed:
                self.json(403, {"ok": False, "message": "Invalid local host."})
                return False
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc not in allowed:
                self.json(403, {"ok": False, "message": "Cross-origin requests are not accepted."})
                return False
            return True

        def do_GET(self) -> None:
            if not self.local_request():
                return
            path = urlparse(self.path).path
            if path == "/api/state":
                try:
                    self.json(200, home.snapshot())
                except OSError:
                    self.json(500, {"ok": False, "message": "Cannot save the simulation state."})
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "application/javascript"),
                      "/style.css": ("style.css", "text/css")}
            if path not in assets:
                self.json(404, {"ok": False, "message": "Not found."})
                return
            name, mime = assets[path]
            self.respond(200, files("smart_home").joinpath("web", name).read_bytes(), mime)

        def do_POST(self) -> None:
            if not self.local_request():
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.json(415, {"ok": False, "message": "Send application/json."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= MAX_BODY:
                    raise ValueError("Request body is empty or too large.")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Send a JSON object.")
                path = urlparse(self.path).path
                code = payload.get("code")
                if code is not None and (not isinstance(code, str) or len(code) > 128):
                    raise ValueError("Invalid code format.")
                if path == "/api/command":
                    result = process(home, payload.get("text"), code=code)
                elif path == "/api/device":
                    result = home.execute([Operation(payload["device_id"], payload["command"],
                                                     payload.get("value"))], code=code)
                elif path == "/api/scene":
                    result = home.scene(payload["name"], code=code)
                else:
                    self.json(404, {"ok": False, "message": "Not found."})
                    return
                self.json(200, {"result": result.to_dict(), "state": home.snapshot()})
            except (ValueError, KeyError, TypeError, OSError) as e:
                self.json(400, {"ok": False, "message": str(e)})

    server = LocalServer((host, port), Handler)
    server.daemon_threads = True
    return server
