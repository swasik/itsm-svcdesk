# ai-generated: 100% - Claude Code (Opus 5.5) wrote this client for Lab 8 Stretch 2 and ran it against poisoned-mcp on 1 October 2026; the lecturer reviews it
"""Ask a stdio MCP server what it offers, the way an agent does before its model sees anything - no agent, no model.

    python3 list_tools.py -- docker run -i --rm -e POISONED_MCP_LOGIN=<login> ghcr.io/swasik/poisoned-mcp:2026
    python3 list_tools.py --stateless -- docker run -i --rm -e POISONED_MCP_LOGIN=<login> ghcr.io/swasik/poisoned-mcp:2026
    python3 list_tools.py --call TOOL --args '{"ticket_id": "INC-4042"}' -- docker run -i --rm ...

Everything after `--` is the server's command line, exactly what `command` and `args` say in `.mcp.json`. The client
speaks JSON-RPC 2.0, one message per line on the server's stdin and stdout. By default it talks the legacy protocol
Claude Code uses with a local stdio server (`initialize`, `notifications/initialized`, `tools/list`); `--stateless`
talks 2026-07-28 instead (`server/discover`, then `tools/list` carrying its protocol version in `_meta`). It prints
every tool with its arguments and its FULL description - the text the agent's model reads and the user usually never
sees. `--call` then sends one `tools/call` with the arguments you give, and the server's stderr (printed at the end)
shows what the server received. Standard library only; Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading

LEGACY = "2025-11-25"
STATELESS = "2026-07-28"
META = "io.modelcontextprotocol/protocolVersion"


class Server:
    def __init__(self, argv: list[str]) -> None:
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", bufsize=1)
        self.stderr: list[str] = []
        threading.Thread(target=self._drain, daemon=True).start()
        self.next_id = 1

    def _drain(self) -> None:
        for line in self.proc.stderr:
            self.stderr.append(line.rstrip("\n"))

    def send(self, method: str, params: dict | None = None, notify: bool = False) -> dict | None:
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            message["id"] = self.next_id
            self.next_id += 1
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise SystemExit(f"the server closed its stdout; its stderr:\n" + "\n".join(self.stderr))
            reply = json.loads(line)
            if reply.get("id") == message["id"]:
                if "error" in reply:
                    raise SystemExit(f"{method}: error {json.dumps(reply['error'])}")
                return reply["result"]
            print(f"(server notification: {line.strip()})")

    def close(self) -> None:
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stateless", action="store_true", help=f"speak {STATELESS} instead of the {LEGACY} handshake")
    parser.add_argument("--call", metavar="TOOL", help="after listing, call this tool once")
    parser.add_argument("--args", default="{}", metavar="JSON", help="the arguments of --call, a JSON object")
    parser.add_argument("server", nargs=argparse.REMAINDER, help="-- and the server's command line")
    opts = parser.parse_args()
    argv = opts.server[1:] if opts.server[:1] == ["--"] else opts.server
    if not argv:
        parser.error("give the server's command line after --")

    server = Server(argv)
    try:
        if opts.stateless:
            found = server.send("server/discover", {"_meta": {META: STATELESS}})
            print(f"server/discover: {json.dumps(found)}\n")
            listed = server.send("tools/list", {"_meta": {META: STATELESS}})
        else:
            hello = server.send("initialize", {"protocolVersion": LEGACY, "capabilities": {},
                                               "clientInfo": {"name": "list_tools.py", "version": "1"}})
            print(f"initialize: protocol {hello.get('protocolVersion')}, server {json.dumps(hello.get('serverInfo'))}")
            if hello.get("instructions"):
                print(f"instructions: {hello['instructions']}")
            print()
            server.send("notifications/initialized", notify=True)
            listed = server.send("tools/list", {})
        extra = {k: v for k, v in listed.items() if k != "tools"}
        if extra:
            print(f"tools/list also says: {json.dumps(extra)}\n")
        for tool in listed.get("tools", []):
            props = (tool.get("inputSchema") or {}).get("properties") or {}
            print("=" * 100)
            print(f"tool {tool['name']}   arguments: {', '.join(props) or '(none)'}")
            for name, spec in props.items():
                print(f"  - {name}: {spec.get('description', '')}")
            print("-" * 100)
            print(tool.get("description", ""))
        print("=" * 100)
        if opts.call:
            params = {"name": opts.call, "arguments": json.loads(opts.args)}
            if opts.stateless:
                params["_meta"] = {META: STATELESS}
            result = server.send("tools/call", params)
            texts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
            print(f"\ntools/call {opts.call}: isError={result.get('isError')}\n" + "\n".join(texts))
    finally:
        server.close()
    if server.stderr:
        print("\n--- the server's stderr " + "-" * 76)
        print("\n".join(server.stderr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
