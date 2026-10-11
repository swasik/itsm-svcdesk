# ai-generated: 100% - Claude Code (Opus 5.5) wrote this probe for Lab 8 Stretch 3 from the MCP 2026-07-28 changelog and transport pages and ran it against two servers on 1 October 2026; the lecturer reviews it
"""Six requests that show how an MCP server over Streamable HTTP stands against the 2026-07-28 revision.

    python3 probe.py http://127.0.0.1:8765/mcp

Each probe prints what it sent and what came back (status, the headers that matter, the body) - evidence for
MCP-DIFF.md, not a verdict: the verdict, and the `path:line` that explains it, are yours. For a stdio server use
`../poisoned-mcp/list_tools.py` with and without `--stateless` instead. Standard library only; Python 3.9 or newer.

  1 GET on the endpoint                         the GET stream endpoint removed: 405 expected
  2 server/discover, no initialize, no session  server/discover; the handshake removed: a result expected
  3 tools/list, no initialize, no session       sessions removed (no Mcp-Session-Id); cacheable lists (ttlMs, cacheScope)
  4 tools/list with Mcp-Method: tools/call      header-based routing: a mismatch must be refused (400, -32020)
  5 tools/call without Mcp-Name                 header-based routing: Mcp-Name is required on tools/call
  6 initialize (the legacy handshake)           what an old client gets: a session id is the old revision's
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

VERSION = "2026-07-28"
META = {"io.modelcontextprotocol/protocolVersion": VERSION, "io.modelcontextprotocol/clientCapabilities": {}}
SHOWN = ("content-type", "mcp-session-id", "allow")


def send(url: str, method: str, body: dict | None, headers: dict) -> None:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Accept": "application/json, text/event-stream", **headers,
                                              **({"Content-Type": "application/json"} if data else {})})
    sent = " ".join(f"{k}: {v}" for k, v in headers.items())
    print(f"> {method} {url} {sent}")
    if body is not None:
        print(f"> {json.dumps(body)}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status, got, text = response.status, response.headers, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status, got, text = exc.code, exc.headers, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        print(f"< no answer: {exc}\n")
        return
    print(f"< {status}")
    for name in SHOWN:
        if got.get(name):
            print(f"< {name}: {got.get(name)}")
    print(f"< {text.strip()[:700]}\n")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    url = sys.argv[1]
    modern = {"MCP-Protocol-Version": VERSION}
    print("1 - GET on the endpoint")
    send(url, "GET", None, {})
    print("2 - server/discover, no initialize, no session")
    send(url, "POST", {"jsonrpc": "2.0", "id": 2, "method": "server/discover", "params": {"_meta": META}},
         {**modern, "Mcp-Method": "server/discover"})
    print("3 - tools/list, no initialize, no session")
    send(url, "POST", {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {"_meta": META}},
         {**modern, "Mcp-Method": "tools/list"})
    print("4 - tools/list with a header that says tools/call")
    send(url, "POST", {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {"_meta": META}},
         {**modern, "Mcp-Method": "tools/call"})
    print("5 - tools/call without Mcp-Name (the tool name is made up; the header is the point)")
    send(url, "POST", {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "no_such_tool", "arguments": {}, "_meta": META}},
         {**modern, "Mcp-Method": "tools/call"})
    print("6 - initialize, the legacy handshake")
    send(url, "POST", {"jsonrpc": "2.0", "id": 6, "method": "initialize",
                       "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                  "clientInfo": {"name": "probe.py", "version": "1"}}}, {})
    return 0


if __name__ == "__main__":
    sys.exit(main())
