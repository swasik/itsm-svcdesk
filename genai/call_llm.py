# ai-generated: 100% - Claude Code (Opus 5.5) adapted this from the Lab 3 research notes (L.8); the lecturer reviews it
"""One instrumented LLM call for L3-STRETCH-1: svcdesk's triage helper asks a model about a ticket, the model asks for
a tool, the helper answers it, the model replies. The OpenTelemetry GenAI instrumentation records the two chat spans;
the tool span is recorded by hand (no instrumentation creates it). Spans go to genai/spans.json as OTLP JSON lines.

    python -m venv .venv && .venv/bin/pip install -r genai/requirements.txt
    OPENAI_BASE_URL=http://localhost:11434/v1 .venv/bin/python genai/call_llm.py     # Ollama, any tool-capable model
    # or, with no model at all: python genai/mock_llm.py 19750 &  OPENAI_BASE_URL=http://127.0.0.1:19750/v1 ...
"""

import json
import os
from pathlib import Path

from openai import OpenAI
from opentelemetry import trace
from opentelemetry.exporter.otlp.json.file import FileSpanExporter
from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

OUT = Path(__file__).resolve().parent / "spans.json"
MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

OUT.unlink(missing_ok=True)
provider = TracerProvider(resource=Resource.create({"service.name": "svcdesk-triage"}))
provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter(str(OUT))))
trace.set_tracer_provider(provider)
OpenAIInstrumentor().instrument()            # before the first client call

client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"), api_key="ollama")
tracer = trace.get_tracer("svcdesk.triage")
tools = [{"type": "function", "function": {"name": "get_ticket", "description": "Look up a ticket",
          "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}}]
messages = [{"role": "user", "content": "What is the status of INC-42?"}]
with tracer.start_as_current_span("invoke_agent svcdesk-triage"):
    reply = client.chat.completions.create(model=MODEL, messages=messages, tools=tools).choices[0].message
    messages.append(reply.model_dump(exclude_none=True))
    for call in reply.tool_calls or []:
        with tracer.start_as_current_span(f"execute_tool {call.function.name}", kind=trace.SpanKind.INTERNAL,
                                          attributes={"gen_ai.operation.name": "execute_tool",
                                                      "gen_ai.tool.name": call.function.name,
                                                      "gen_ai.tool.call.id": call.id, "gen_ai.tool.type": "function"}):
            result = {"id": json.loads(call.function.arguments)["ticket_id"], "priority": "P2"}
        messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    print(client.chat.completions.create(model=MODEL, messages=messages, tools=tools).choices[0].message.content)
provider.shutdown()
