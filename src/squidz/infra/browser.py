"""Loopback-only URL bridge, authenticated per browser foreground window."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread, Lock
import json
import time

class BrowserBridge:
    def __init__(self, token: str, port: int):
        self.token, self.port = token, port
        self._lock = Lock()
        self._url_by_process: dict[str, tuple[str, float]] = {}
        self._server = None

    def domain(self, process: str) -> str:
        from urllib.parse import urlparse
        with self._lock:
            url, updated = self._url_by_process.get(process, ("", 0))
        if time.monotonic() - updated > 5:
            return ""
        return (urlparse(url).hostname or "").lower()

    def start(self) -> None:
        bridge = self
        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-squidz-Token")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.end_headers()
            def do_POST(self):
                if self.path != "/active" or self.headers.get("X-squidz-Token") != bridge.token:
                    self.send_error(403); return
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 4096:
                    self.send_error(413); return
                try:
                    obj = json.loads(self.rfile.read(size))
                    proc, url = obj["process"], obj["url"]
                    if proc not in ("firefox.exe", "brave.exe") or not isinstance(url, str) or not url.startswith(("http://", "https://")):
                        raise ValueError("Invalid payload")
                    with bridge._lock:
                        bridge._url_by_process[proc] = (url, time.monotonic())
                except (ValueError, KeyError, TypeError):
                    self.send_error(400); return
                self.send_response(204); self.end_headers()
            def log_message(self, *_): pass
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
