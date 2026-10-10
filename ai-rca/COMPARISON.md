<!-- ai-generated: 100% - Claude Code (Opus 5.5) acting as the student scored both investigators and wrote this comparison -->
# Two investigators on the same incident

Both ran the course's agent loop (`agent.py`) with the course's MCP server `prom_mcp.py` (mcp 2.2.0), on the local
Ollama, with the same question: "Checkout errors paged at 23:11:09Z on 2026-10-10. Investigate 22:55Z to 23:20Z.
What is the cause?". The first used `qwen3:1.7b` (2 model calls, 3 tool calls, 1 minute;
`ai-rca/transcript.md`, ledger `ai-rca-eval.json`); the second `qwen3:4b-instruct` (11 tool calls, 3 minutes;
`ai-rca/second/transcript.md`, ledger `ai-rca-eval-2.json`). The fault, read from the flag state during the
incident, was productCatalogFailure, intlShippingSlowdown (10sec) and recommendationCacheFailure.

## Entry by entry

| | qwen3:1.7b | qwen3:4b-instruct | what the data proved |
|---|---|---|---|
| shipping | H1 partially_correct: shipping slow, "status_code=ERROR" | not mentioned | shipping p95 2600 ms at 23:12, no shipping errors at all: slow, not failing |
| checkout | H2 correct: checkout failing | H2 hallucinated: "no results" for checkout errors | 16 % of PlaceOrder failed over 5 minutes at 23:12 |
| frontend | H3 correct: frontend errors | (listed as "no results", not scored separately) | 7.5 % of frontend SERVER spans failed |
| product-catalog | H4 correct: product-catalog errors | H3 hallucinated: "rather than a failure at any of the backend services" | GetProduct failed at 0.13/s, 38 calls |
| whole shop | - | H1 hallucinated: "No service showed errors" | 0.55 failed SERVER spans per second at 23:12 |

## Where they agreed, where they parted, and why

They agreed on nothing. The small model read `ALERTS` at the page's instant (`alerts_at`) and restated each firing
or pending alert as a hypothesis: every claim it made about *where* the symptoms were is confirmed by the data, but
it learned them from our own alert names, not from the span metrics, and its explanations of *why* are invented
("span_kind=latency", "span_kind=error" are not values of that label; shipping had no error spans). It is right by
reading our rules back to us, which is worth knowing: an investigator with access to `ALERTS` inherits the on-call's
alert design, good or bad.

The larger model did the opposite: it listed the metrics and the values of all four labels (`label_values`), then
queried the span metrics service by service, but with `span_name="*"`, which
PromQL takes as the literal value `*` and which matches nothing. It then treated six empty answers as evidence that
no service failed and concluded "a transient or external factor". Each of its three scored claims is contradicted by
a query on series the snapshot really holds, so all three are hallucinated. More tool calls did not help: one wrong
selector, repeated, made a confident wrong answer.

Neither named a flag (no metric names one, by design), neither saw the recommendation cache fault, and neither found
the mechanism behind the product-catalog errors. The data proved the 1.7b model right on the components (four of four
true at 23:12:00 and false at the baseline 23:02:36), and the 4b model wrong on every claim. For the next incident
the useful lesson is about verification rather than size: the 4b model had read the real label values and still
wrote a selector that matches nothing, so a result of "no series" should always be checked against a query that
must return something (the same selector without the error filter) before it is read as "no errors".
