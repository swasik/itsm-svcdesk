<!-- ai-generated: 100% - Claude Code (Opus 5.5) acting as the student scored both investigators and wrote this comparison -->
# Two investigators on the same incident

Both ran the course's agent loop (`agent.py`) with the course's MCP server `prom_mcp.py` (mcp 2.2.0), on the local
Ollama with an 8k context, against the live playground after recovery. Each got the plain question first ("Checkout
errors paged at 07:59:49Z on 2026-10-11. Investigate 07:45Z to 08:10Z. What is the cause?"), and, because neither
gave a hypothesis about the shop on that run, a sharper second question as the handout suggests (the window repeated
with its date, and "state at least three hypotheses"; for qwen3:4b-instruct also "use instant queries with rate() or
histogram_quantile()"). Neither question named a service or a flag. The fault was productCatalogFailure,
productCatalogLockContention and recommendationCacheFailure: product-catalog failing and stalling, recommendation
without its cache.

## First: qwen3:1.7b (`ai-rca-eval.json`, six entries)

- Run 1 read the alerts (`alerts_at` at the page) and two raw series, then queried 2026-10-24, two weeks after the
  incident, with label values that do not exist (`service_name="backend"`, `span_kind="error"`). Everything came
  back empty, and its three closing claims are about its own tooling: the metrics "are not being collected" (H4,
  hallucinated: both metrics were collected throughout), a time window that "may exclude the actual data" (H5) and
  labels that "might not match" (H6), both unfalsifiable as claims about the agent's queries, not the shop.
- Run 2 never made a valid tool call: it wrapped every argument in `{"type": "string", "value": ...}`, and all
  twelve calls were refused. It then wrote "After correcting the validation errors, the tools now execute
  successfully", which is false, and listed three generic hypotheses. H1 (checkout errors, a "service outage") is
  partially correct: 14.4 % of checkout's spans failed at 08:01:00, but not more than half, and the cause was a
  dependency it never named. H2 (payment or inventory latency) is hallucinated: payment's p95 was 1.9 ms. H3 (errors
  in `user_profile` or `order_history`) is hallucinated: no service outside the product-catalog path failed a single
  span, and those services do not exist.

## Second: qwen3:4b-instruct (`ai-rca-eval-2.json`, three entries)

- Run 1 made six tool calls, pulled raw counters for checkout into its context, asked for `status_code="ERROR"` (a
  value that does not exist), and then answered "I don't have any information to work with": no hypothesis.
- Run 2 made 36 tool calls. It listed metrics and services correctly, but wrote `rate(metric{...})` without a range
  over and over (Prometheus's parse error each time) and used `span_name="*"` as if it were a wildcard. From those
  empty answers it concluded that the data itself was broken. All three entries are hallucinated: STATUS_CODE_ERROR
  series did exist (H1), the five services it named all reported spans (H2), and `service_name="checkout"` matched
  (H3) - its own earlier query in the same transcript had returned checkout's series.

## Entry by entry: where they agreed and where they parted

- **Checkout.** Only the 1.7b model blamed checkout, and only by restating the page's symptom (its run 2 had no
  data at all): partially correct, and it did not go beyond what the CheckoutErrorRate alert already said. The 4b
  model mentioned checkout's reported errors only to argue that the metrics were mislabelled.
- **"The metrics are missing".** This is where they agreed, and both were wrong: 1.7b's H4 and 4b's H1 to H3 blame
  the telemetry for what were their own malformed queries (a wrong date, nonexistent label values, `rate` without a
  range, `*` in an equality matcher). The data proved them wrong in every case.
- **The real cause.** Neither named product-catalog, recommendation or the 15-second latencies, although
  ServiceLatencyRaised on both services was in the `alerts_at` answer the 1.7b model received. The larger model
  made more calls and wrote more fluent text, and scored no better: zero true predictions against one partial.

What decided every verdict was a query on the snapshot, not the agents' confidence. For an incident after the fact,
both small local models are below the threshold where an agentic loop helps: they fail on tool-call formats and
PromQL syntax before they reach the question.
