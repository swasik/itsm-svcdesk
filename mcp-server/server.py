# ai-generated: 100% - Claude Code (Opus 5.5, knowledge cutoff June 2026) wrote this server on 11 October 2026 when asked for "an MCP server over the rag service, the latest MCP revision you know", without the 2026-07-28 specification or a web search; kept as written (Lab 8 Stretch 3, MCP-DIFF.md)
"""A small MCP server (Streamable HTTP transport) in front of the Lab 8 rag service.

Protocol revision: 2025-06-18 (the latest one the author knows), with 2025-03-26 accepted for older clients.

    POST   /mcp   JSON-RPC requests, notifications and responses (one message per POST)
    GET    /mcp   405: this server offers no server-initiated SSE stream
    DELETE /mcp   ends the session named by Mcp-Session-Id

Lifecycle: the client sends `initialize`; the server answers with its protocol version, capabilities and server
info, and an `Mcp-Session-Id` header; the client sends `notifications/initialized`; every later request carries
`Mcp-Session-Id` (and `MCP-Protocol-Version`), and a request without a valid session is refused.

One tool, `search_semester`: retrieves passages of the student's coursework through the rag service's
POST /retrieve (RAG_URL, default http://127.0.0.1:8088).

    python3 mcp-server/server.py --port 8765
"""

import argparse
import json
import os
import secrets
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = {"2025-06-18", "2025-03-26"}
SERVER_INFO = {"name": "semester-rag-mcp", "version": "0.1.0"}
RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:8088").rstrip("/")

TOOLS = [
    {
        "name": "search_semester",
        "title": "Search my ITSM semester",
        "description": "Retrieve passages of the student's ITSM coursework (Labs 1-7) relevant to a question. "
        "Returns the document path and the passage text of each result, best first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "what to look for"},
                "k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            },
            "required": ["question"],
        },
    }
]

_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def rpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def call_search(arguments: dict) -> dict:
    question = arguments.get("question")
    if not isinstance(question, str) or not question.strip():
        return {"content": [{"type": "text", "text": "question is required"}], "isError": True}
    k = int(arguments.get("k", 3))
    body = json.dumps({"question": question, "k": k}).encode()
    request = urllib.request.Request(f"{RAG_URL}/retrieve", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            results = json.load(response)["results"]
    except Exception as err:  # the rag service is down or not indexed
        return {"content": [{"type": "text", "text": f"rag service error: {err}"}], "isError": True}
    text = "\n\n".join(f"[{r['doc']}]\n{r['chunk']}" for r in results)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {"results": results},
        "isError": False,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "semester-rag-mcp/0.1"

    def _send_json(self, status: int, payload, headers: dict | None = None):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_empty(self, status: int, headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def do_GET(self):
        if self.path != "/mcp":
            return self._send_empty(404)
        # No server-initiated messages: the spec allows 405 for the optional GET stream.
        return self._send_empty(405, {"Allow": "POST, DELETE"})

    def do_DELETE(self):
        if self.path != "/mcp":
            return self._send_empty(404)
        session_id = self.headers.get("Mcp-Session-Id")
        with _sessions_lock:
            existed = _sessions.pop(session_id, None) if session_id else None
        return self._send_empty(200 if existed else 404)

    def do_POST(self):
        if self.path != "/mcp":
            return self._send_empty(404)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            message = json.loads(self.rfile.read(length) or b"null")
        except json.JSONDecodeError:
            return self._send_json(400, rpc_error(None, -32700, "Parse error"))
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return self._send_json(400, rpc_error(None, -32600, "Invalid Request"))

        method = message.get("method")
        msg_id = message.get("id")
        is_notification = "id" not in message

        if method == "initialize":
            params = message.get("params") or {}
            requested = params.get("protocolVersion")
            version = requested if requested in SUPPORTED_VERSIONS else PROTOCOL_VERSION
            session_id = secrets.token_hex(16)
            with _sessions_lock:
                _sessions[session_id] = {"version": version, "initialized": False,
                                         "client": params.get("clientInfo", {})}
            result = {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": "Use search_semester to find passages of the student's coursework; cite the [doc].",
            }
            return self._send_json(200, rpc_result(msg_id, result), {"Mcp-Session-Id": session_id})

        session_id = self.headers.get("Mcp-Session-Id")
        with _sessions_lock:
            session = _sessions.get(session_id) if session_id else None
        if session is None:
            return self._send_json(400, rpc_error(msg_id, -32600, "Mcp-Session-Id header required"))
        version_header = self.headers.get("MCP-Protocol-Version")
        if version_header and version_header not in SUPPORTED_VERSIONS:
            return self._send_json(400, rpc_error(msg_id, -32600, f"Unsupported protocol version {version_header}"))

        if method == "notifications/initialized":
            session["initialized"] = True
            return self._send_empty(202)
        if is_notification:  # other notifications (cancelled, progress): accepted, nothing to do
            return self._send_empty(202)
        if method == "ping":
            return self._send_json(200, rpc_result(msg_id, {}))
        if method == "tools/list":
            return self._send_json(200, rpc_result(msg_id, {"tools": TOOLS}))
        if method == "tools/call":
            params = message.get("params") or {}
            if params.get("name") != "search_semester":
                return self._send_json(200, rpc_error(msg_id, -32602, f"Unknown tool: {params.get('name')}"))
            return self._send_json(200, rpc_result(msg_id, call_search(params.get("arguments") or {})))
        return self._send_json(200, rpc_error(msg_id, -32601, f"Method not found: {method}"))

    def log_message(self, fmt, *args):  # one line per request on stderr
        print(f"semester-rag-mcp: {self.command} {self.path} {fmt % args}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"semester-rag-mcp: MCP {PROTOCOL_VERSION} on http://{args.host}:{args.port}/mcp, rag at {RAG_URL}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
