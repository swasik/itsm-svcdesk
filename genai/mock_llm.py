# ai-generated: 100% - adapted by Claude Code (Opus 5.5) from the Lab 3 research notes; the lecturer reviews it
"""Tiny mock of an OpenAI-compatible /v1/chat/completions endpoint (Ollama-like).

- Request with `tools` and no `tool` message yet -> assistant message with one tool_calls entry.
- Otherwise -> plain assistant text.
Listens on 127.0.0.1:19750. Logs each request body to stderr.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 19750
MODEL = "llama3.2:3b"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter default log
        sys.stderr.write("mock: " + fmt % args + "\n")

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") == "/v1/models":
            return self._send(200, {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "library"}]})
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or b"{}")
        sys.stderr.write("mock: request body: " + json.dumps(req)[:400] + "\n")
        if self.path.rstrip("/") != "/v1/chat/completions":
            return self._send(404, {"error": {"message": "not found"}})
        msgs = req.get("messages", [])
        wants_tool = bool(req.get("tools")) and not any(m.get("role") == "tool" for m in msgs)
        if wants_tool:
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_abc123",
                    "index": 0,
                    "type": "function",
                    "function": {"name": "get_ticket", "arguments": "{\"ticket_id\": \"INC-42\"}"},
                }],
            }
            finish = "tool_calls"
            usage = {"prompt_tokens": 57, "completion_tokens": 18, "total_tokens": 75}
        else:
            message = {"role": "assistant", "content": "Ticket INC-42 is a P2 incident: VPN down for the Poznan office."}
            finish = "stop"
            usage = {"prompt_tokens": 91, "completion_tokens": 21, "total_tokens": 112}
        self._send(200, {
            "id": "chatcmpl-mock-%d" % int(time.time() * 1000),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL,
            "system_fingerprint": "fp_ollama",
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": usage,
        })


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write(f"mock OpenAI-compatible server on http://127.0.0.1:{PORT}/v1\n")
    srv.serve_forever()
