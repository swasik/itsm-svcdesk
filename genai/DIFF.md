---
lab3_genai_diff:
  instrumentation: "opentelemetry-instrumentation-genai-openai 1.2b0 (opentelemetry-util-genai 1.2b0, SDK 1.45.0, openai 3.19.2)"
  spec_ref: "semantic-conventions-genai@e57c543b4889619eb2a05702471937db5119165d"
  attributes:
    - {name: gen_ai.operation.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.provider.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.id, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.finish_reasons, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.input_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.output_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.tool.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.tool.call.id, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.tool.type, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.input.messages, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.output.messages, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.conversation.id, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.system, emitted: false, in_spec: false}
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this diff from genai/spans.json on 27 September 2026; the lecturer reviews it -->

# What the library emits, against the spec

`genai/call_llm.py` makes one tool-using call through the OpenAI client (a mock OpenAI-compatible server,
`genai/mock_llm.py`; the same code runs against Ollama). The spans are in `genai/spans.json` (OTLP JSON, one batch
per line): two `chat llama3.2:3b` CLIENT spans from the instrumentation, and two spans the application had to record
itself, `invoke_agent svcdesk-triage` and `execute_tool get_ticket`. The spec compared against is the GenAI conventions repository at commit
`e57c543` (24 September 2026) - the conventions left the main semantic-conventions repository in v1.42.0 and the new
repository has no release, so a commit is the only precise reference there is.

What agrees: every one of the eleven `gen_ai.*` keys in the file - eight on the instrumentation's chat spans, the three
`gen_ai.tool.*` keys on the hand-made tool span - is in the registry, with the status the registry gives all of them,
Development - there is no stable GenAI attribute yet.

What does not, or not quite:

- `gen_ai.provider.name` says `openai` although the model ran behind an OpenAI-compatible server that is not OpenAI.
  The attribute is right by name and wrong by meaning; only `server.address` tells the truth.
- `gen_ai.system`, which the older `openai-v2` instrumentation still writes by default, is absent: this package
  follows the rename of semconv v1.37.0. In the last release that held the GenAI conventions (v1.41.1) it is listed
  as deprecated; in the new repository it no longer exists at all.
- The tool call is invisible without the hand-made span: with content capture off (the default), the chat span
  records only `finish_reasons=["tool_calls"]`.
- `gen_ai.input.messages` and `gen_ai.output.messages` are opt-in and were not captured; `gen_ai.conversation.id`
  is conditionally required for multi-turn agents and was not set by anything.

The lesson for monitoring: a dashboard built on these attributes is built on Development conventions whose home moved
in June 2026 and whose token metric changed on 22 September. Pin the spec by commit, and diff again when either the
library or the spec moves.
