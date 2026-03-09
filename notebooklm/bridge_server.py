"""Tiny CORS HTTP relay between Streamlit and the browser JS bridge."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

_state = {"question": None, "answer": None, "status": "idle", "notebook_id": None}
_lock = threading.Lock()


class BridgeHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        with _lock:
            self._json_response(200, _state.copy())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        path = self.path.rstrip("/")
        with _lock:
            if path == "/question":
                _state["question"] = body.get("question")
                _state["notebook_id"] = body.get("notebook_id")
                _state["answer"] = None
                _state["status"] = "pending"
                self._json_response(200, {"ok": True})
            elif path == "/answer":
                _state["answer"] = body.get("answer")
                _state["status"] = "answered"
                self._json_response(200, {"ok": True})
            elif path == "/reset":
                _state["question"] = None
                _state["answer"] = None
                _state["status"] = "idle"
                _state["notebook_id"] = None
                self._json_response(200, {"ok": True})
            else:
                self._json_response(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass  # Suppress request logs


def start_bridge(port=8081):
    server = HTTPServer(("0.0.0.0", port), BridgeHandler)
    print(f"Bridge relay on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    start_bridge()
