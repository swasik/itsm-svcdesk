---
lab3_first_draft:
  source: ai
  tool: "Claude Opus 5.5 (Claude Code), 27 September 2026, asked before any measurement"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  verdict: refuted
  evidence: {p99_seconds: 0.236, bucket: [0.1, 0.25], relative_width: 0.636}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.236, bucket: [0.04, 0.5], relative_width: 1.949}
---
<!-- ai-generated: 100% - the answer below is an assistant's, verbatim; the verdicts were written by Claude Code (Opus 5.5) from the measurement; the lecturer reviews it -->

# The assistant's first draft, and two verdicts

## Prompt

I am instrumenting a Python FastAPI service with prometheus_client. The endpoint GET /kb/search calls a search
backend on every request. Suggest histogram bucket boundaries for http_server_request_duration_seconds, and a
Prometheus alert rule that pages when latency is bad.

## Answer

For a typical web API, the standard latency buckets work well and match what most dashboards expect:

```python
buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
```

These cover everything from very fast cache hits (5 ms) to slow requests (10 s) on a roughly logarithmic scale.
For the alert, page when the 99th percentile goes above 500 ms for 10 minutes:

```yaml
- alert: KbSearchHighLatency
  expr: histogram_quantile(0.99, sum by (le) (rate(http_server_request_duration_seconds_bucket{http_route="/kb/search"}[5m]))) > 0.5
  for: 10m
  labels:
    severity: page
```

## Verdict on the draft ladder: refuted

Measured with the published command (60 s open-loop at 40 requests/s), the p99 of `/kb/search` is 0.236 s. In the
draft's ladder that falls in (0.1, 0.25]: a bucket 0.15 s wide, 64 % of the p99, where the rule allows 20 %. Every
request between 100 and 250 ms is one count to the histogram, so `histogram_quantile` can only interpolate linearly
across the bucket - and the slow requests of this service all sit in a narrow mode near 230 ms, the worst case for
that assumption. The ladder is Go's `DefBuckets`; Python's default adds 0.075, 0.75 and 7.5 and does not help here.

The alert has the second classic flaw: a threshold on `histogram_quantile` over these buckets is decided inside the
same 150 ms-wide bucket, and it pages on the p99 of five minutes, not on how fast the error budget is going.

## Verdict on the instructor's flawed ladder: refuted

The flawed ladder has fourteen boundaries, twelve of them below 40 ms, then 0.5 and 2.5. The p99 of 0.236 s falls in
(0.04, 0.5]: 0.46 s wide, 195 % of the p99. It resolves the median (about 26 ms, in a 2.5 ms bucket) beautifully and
the p99 not at all - resolution spent where nothing happens.
