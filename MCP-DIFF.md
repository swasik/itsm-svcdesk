---
lab8_mcp_diff:
  agent: "Claude Code, Claude Opus 5.5 (knowledge cutoff June 2026), 11 October 2026; asked for an MCP server over the rag service in 'the latest MCP revision you know', given neither the 2026-07-28 specification nor a web search"
  spec: 2026-07-28
  items:
    - {change: "sessions removed (no Mcp-Session-Id)", verdict: deviates, where: "mcp-server/server.py:135"}
    - {change: "initialize handshake removed (version and capabilities in every request's _meta)", verdict: deviates, where: "mcp-server/server.py:151"}
    - {change: "server/discover", verdict: absent, where: "mcp-server/server.py:170"}
    - {change: "GET stream endpoint removed", verdict: conforms, where: "mcp-server/server.py:106"}
    - {change: "header-based routing (Mcp-Method / Mcp-Name)", verdict: absent, where: "mcp-server/server.py:127"}
    - {change: "cacheable lists (ttlMs / cacheScope on tools/list)", verdict: absent, where: "mcp-server/server.py:164"}
---
<!-- ai-generated: 60% - Claude Code (Opus 5.5) wrote mcp-server/ and ran stretch/stateless/probe.py; the student read the probe's output against the changelog's six changes as the course's Stretch README describes them -->

# MCP stateless diff

**What was asked and what came back.** I asked an agent - Claude Code with Claude Opus 5.5, whose training data
ends in June 2026, a month before the 2026-07-28 revision - for an MCP server in front of my rag service's
`/retrieve`, "in the latest revision of the MCP specification you know", with no specification and no web search.
It wrote `mcp-server/server.py` (Python standard library, Streamable HTTP, one tool `search_semester`) and declared
`PROTOCOL_VERSION = "2025-06-18"` in its first lines: it knew it was writing 2025-06-18 and did not know a later
revision existed. It is kept as written.

**What the probe showed** (`python3 stretch/stateless/probe.py http://127.0.0.1:8765/mcp`, six requests):

| probe | answer | the line that explains it |
|---|---|---|
| 1 GET | `405`, `allow: POST, DELETE` | `server.py:106`: no server-initiated stream was ever offered |
| 2 `server/discover` | `400` `-32600 "Mcp-Session-Id header required"` | `server.py:151`: every method but `initialize` needs a session |
| 3 `tools/list` without a session | the same `400` | `server.py:151` |
| 4 header says `tools/call`, body `tools/list` | the same `400` - the header is never read | `server.py:127`: the method comes from the body only |
| 5 `tools/call` without `Mcp-Name` | the same `400` | `server.py:127`, `server.py:151` |
| 6 legacy `initialize` | `200`, `mcp-session-id: bb7a...`, `protocolVersion: 2025-06-18` | `server.py:131-142`, the id minted at `server.py:135` |

**The six changes.** *Sessions removed*: deviates - the server mints an id (`secrets.token_hex(16)`, line 135) and
keeps per-session state in `_sessions`; a stateless request has nothing to carry. *Initialize removed*: deviates -
line 151 refuses everything before `initialize`, so a 2026-07-28 client, which sends its version and capabilities in
each request's `_meta` and never initializes, gets nothing but 400s. *`server/discover`*: absent - had a session
existed, the request would have fallen into the unknown-method branch (line 170, `-32601`). *GET stream removed*:
conforms, by accident - the 2025 revision made the GET stream optional and the agent chose not to offer one, so the
405 of line 106 is what a stateless server answers too; the agent's comment says it relied on the old option, not
the new rule. *Header routing*: absent - `Mcp-Method` and `Mcp-Name` are never read (line 127 takes the method from
the body), so a header that contradicts the body is not refused with `-32020` as a conforming server does (the
course's `poisoned-mcp` refuses probe 4 that way). *Cacheable lists*: absent - the `tools/list` result of line 164
has neither `ttlMs` nor `cacheScope`.

**What conforming would take.** Drop `_sessions` and the session check; read the protocol version and client
capabilities from `params._meta` of every request (and `MCP-Protocol-Version`); answer `server/discover` with the
supported versions and capabilities; check `Mcp-Method` (and `Mcp-Name` for `tools/call`) against the body and
refuse a mismatch; add `ttlMs` and `cacheScope` to `tools/list`; keep `initialize` only as a compatibility path for
2025 clients. **The point of the exercise held:** an agent trained before the revision wrote the previous
revision fluently and correctly, and nothing in its output warned that the protocol had moved. I judged the six
changes from the course's Stretch README's summary of the changelog and the `poisoned-mcp` server's stateless
answers (`list_tools.py --stateless`: `server/discover` with `protocolVersions: ["2026-07-28", ...]`, `tools/list`
with `ttlMs` and `cacheScope: "public"`), not from a reading of the full 2026-07-28 text.
