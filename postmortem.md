---
lab4_postmortem:
  ticket: "23b2e067-02e9-441b-8f1c-4ce22042bd54"
  detecting_alert: ServiceLatencyRaised
  onset: 2026-10-11T07:55:26Z
  detection: 2026-10-11T07:58:38Z
  acknowledgement: 2026-10-11T07:59:57Z
  recovery: 2026-10-11T08:05:38Z
  mttd_seconds: 192
  mtta_seconds: 79
  mttr_seconds: 612
  identified_flags: [productCatalogFailure, productCatalogLockContention, recommendationCacheFailure]
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) worked the incident as the student and wrote this postmortem from its own notes and queries -->

# Postmortem: the product catalogue failed and stalled, and pages took 15 seconds, for nine minutes

## Date

The incident happened on Sunday 11 October 2026 (UTC) between 07:55:26 and 08:04:31; this postmortem was written the
same morning, about half an hour after the last flag was switched off.

## Authors

The on-call engineer for the shop, who was paged, opened and acknowledged the P1 ticket, switched the flags off and
scored the two AI investigators.

## Status

Complete for the incident: service restored at 08:04:31 and the ticket acknowledged. Action items open; the problem
record below stays open.

## Summary

From 07:55:26 to 08:04:31 UTC three feature flags of the shop failed at once, all of them on the product catalogue's
path. Product-catalog's GetProduct failed for one product in ten, which failed 3 of 60 orders and 27 product pages;
product-catalog's reads stalled for up to 30 seconds at a time, which pushed the p95 of the frontend, of
recommendation and of product-catalog to the 15-second ceiling of the histogram and checkout's p95 to 12 seconds; and
the recommendation service ran without its cache. Switching the three flags off restored service nine minutes after
the onset.

## Impact

Measured on the span metrics in the snapshot (SERVER spans; counters are cumulative, so a difference of two samples
counts the calls in between):

- **Orders**: 60 PlaceOrder calls were made between 07:55 and 08:06
  (`sum(traces_span_metrics_calls_total{service_name="checkout",span_name="oteldemo.CheckoutService/PlaceOrder"})`,
  73 then 133); **3 of them failed** (5 %; the same selector with `status_code="STATUS_CODE_ERROR"`, absent before
  the onset, 3 at 08:06). Over the five minutes to 08:00:00, 17.9 % of checkout's SERVER spans failed
  (`sum(rate(...{service_name="checkout",span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}[5m])) /
  sum(rate(...{service_name="checkout",span_kind="SPAN_KIND_SERVER"}[5m]))`), against no failed span on the healthy
  shop.
- **Product pages**: 26 GetProduct calls of product-catalog failed (the error counter reached 26 by 08:06, out of
  about 1,030 GetProduct calls in the window), and with them 27 `GET /api/products/[productId]` pages,
  19 `GET /api/recommendations` calls and 6 `POST /api/checkout` calls of the frontend
  (`sum by (span_name) (increase(...{service_name="frontend",status_code="STATUS_CODE_ERROR"}[11m]))` at 08:06).
  The frontend's SERVER error ratio was 6.8 % over the five minutes to 08:01:00.
- **Slow pages and orders**: the p95 over five minutes of product-catalog, recommendation and the frontend reached
  15,000 ms, the top bucket, from 07:58 to 08:04 (23 ms, 7 ms and 46 ms on the healthy shop at 07:50:26);
  checkout's p95 reached 12,250 ms at 08:04 (91 ms healthy). Two orders took more than 5 s
  (`calls_total - duration_milliseconds_bucket{le="5000"}` of PlaceOrder, 0 at 07:55, 2 at 08:06).
- **Recommendations without cache**: recommendation's container memory moved only from 53.5 MB to 57.1 MB
  (`container_memory_usage_total_bytes{container_name="recommendation"}`, 07:55 to 08:06); its latency was already
  at the ceiling because of the stalled catalogue, so the cache failure's own share cannot be told apart in nine
  minutes.

## Root Causes

Three flags of the shop's flag provider switched to failing values together. productCatalogFailure made
product-catalog answer GetProduct with an error for one product of the catalogue, so every order and every product
page holding that product failed. productCatalogLockContention made product-catalog's reads wait on a lock for up to
30 s, so every caller of the catalogue - the frontend's pages, recommendation's ListProducts, checkout's order
preparation - waited with it. recommendationCacheFailure disabled the recommendation service's cache, a resource
fault whose memory growth had barely started when it was switched off. What was already wrong: flags that can fail or
stall the one service every page depends on are switchable at runtime by a source that overrides the shop's own flag
file, with no change record and no alert that names them; and product-catalog is a single dependency of checkout,
the frontend and recommendation with no timeout shorter than its stall.

## Trigger

At 07:55:26 UTC (the onset, the first sample of the injector's fault series) the flag source served the three
failing variants, and flagd picked them up on its next poll. Nothing was deployed; the change was a configuration
change of feature flags.

## Resolution

After reading the live flag state (`curl http://localhost:18090/flags.json`, 08:00:04) the on-call switched the
three flags off one at a time through the injector, in order of user impact, watching each: productCatalogFailure at
08:00:09 (orders and pages failing; checkout had no failed span over the three minutes to 08:01:57),
productCatalogLockContention at 08:02:01 (the stalls; product-catalog's three-minute p95 fell from 15,000 ms to
4,250 ms and recommendation's to 5 ms by 08:04:01), recommendationCacheFailure at 08:04:27. The fault series went to
0 at 08:04:31. That is a workaround in ITIL's sense; the cause (flags that can be switched to failing values) stays.

## Detection

The first alert to fire after the onset was the P3 ServiceLatencyRaised on product-catalog (with the same rule on
recommendation, in the same evaluation), at 07:58:38 (MTTD 192 s); it reached chat at 07:58:48 together with the P2
FrontendLatencyHigh. The P1 CheckoutErrorRate fired a minute later, at 07:59:39, and its page reached the pager at
07:59:49; from then on the inhibit rule muted the P2 and P3 alerts. So the on-call learned of the incident from the
page, 71 s after the formal detection by a chat message that nobody is required to watch. Most of the 192 s is
structural: the shop's metrics arrive once a minute, the rules use 5-minute windows and `for: 1m`. Without the
alerts, shoppers would have noticed first: 15-second product pages from 07:58.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Page on the frontend's latency (P1, p95 above 5 s over 5 m) next to checkout's, so a stalled catalogue pages within the same minute as the chat alert instead of a minute later | mitigate | on-call | ITSM-101 |
| Put the P3 cause alerts in the same rule group as the P1 pages, so that a page and its cause start on the same evaluation and the page is the detecting alert | process | on-call | ITSM-102 |
| Record every runtime flag change as a change in svcdesk, and export the count of failing flags as a metric the dashboards show | prevent | platform team | ITSM-103 |
| Give the frontend's and checkout's calls to product-catalog a 2-second timeout with a cached fallback for product data, so a stalled catalogue degrades pages instead of stalling them | mitigate | shop team | ITSM-104 |
| Add a runbook step "read /flags.json first" for checkout and frontend pages | process | on-call | ITSM-105 |

## Lessons Learned

### What went well

The page came 10 s after the P1 fired, and the ticket was created and acknowledged 8 s after the page. Reading what
changed (the flag state) right after the symptoms named the three flags at once; switching them off one at a time
showed which flag caused what: checkout's errors stopped after productCatalogFailure went off, the 15-second
latencies fell after productCatalogLockContention went off.

### What went wrong

The detecting alert was a P3 in a separate rule group, which fired a minute before any P1: the page waited for
checkout's error ratio to stay above 5 % for a minute, while the latency of every page was already at 15 s. The
recorded MTTA (79 s) is mostly that minute, not the on-call's reaction. The resource fault (recommendation cache)
left no signal any of the rules could separate from the catalogue stall.

### Where we got lucky

The errors hit one product in ten, not checkout itself, so 95 % of orders still went through, and the stall made
pages slow rather than failed. A heavier draw (payment failing at 50 %) would have failed half the orders for the
same three minutes before anyone was paged.

## Timeline

All times UTC, 11 October 2026.

- 07:28:45 - first start of the playground; a P1 (CheckoutLatencyHigh) fired on the warming-up shop from 07:32:29
  to 07:33:59. The injector was armed at 07:39:01 without waiting for that P1 to leave the 10-minute window, so the
  run was abandoned with `down -v` before any onset (no fault series had started).
- 07:40:31 - the playground starts again; the injector begins a new 10-minute baseline. A practice ticket at
  07:42:23 proves svcdesk's requests reach Prometheus.
- 07:51:02 - baseline 10 min; `max_over_time(ALERTS{alertstate="firing", severity="P1"}[10m])` returns nothing and
  no alert is firing.
- 07:51:14 - the injector is armed (onset window 2 to 6 minutes).
- 07:55:26 - **onset**: the injector's fault series starts.
- 07:57:38 - ServiceLatencyRaised (product-catalog and recommendation p95 above 1 s) and FrontendLatencyHigh pending.
- 07:58:38 - **detection**: ServiceLatencyRaised fires (P3); FrontendLatencyHigh (P2) fires at 07:58:39; both reach
  chat at 07:58:48.
- 07:59:39 - CheckoutErrorRate fires (P1); 07:59:49 the page reaches the pager.
- 07:59:57 - the P1 ticket 23b2e067-02e9-441b-8f1c-4ce22042bd54 is created and **acknowledged**.
- 08:00:04 - symptoms: checkout, frontend and product-catalog failing, p95 of product-catalog, recommendation and
  the frontend at 15 s; what changed: `/flags.json` shows productCatalogFailure, productCatalogLockContention and
  recommendationCacheFailure on.
- 08:00:09 - productCatalogFailure switched off (`changed: true`).
- 08:01:39 - CheckoutLatencyHigh fires (P1), paged at 08:01:49.
- 08:01:57 - no failed checkout span over the last three minutes; latencies still at 15 s.
- 08:02:01 - productCatalogLockContention switched off.
- 08:03:39 - CheckoutErrorRate resolved (pager 08:03:49); 08:04:39 CheckoutLatencyHigh resolved (pager 08:04:49).
- 08:04:27 - recommendationCacheFailure switched off; 08:04:31 the fault series goes to 0.
- 08:05:38 - **recovery** as the rules define it: ServiceLatencyRaised's firing run ends (chat resolved 08:05:48).
- 08:06:11 to 08:28:00 - the AI investigators (qwen3:1.7b, then qwen3:4b-instruct) run; their hypotheses are scored
  in `ai-rca-eval.json` and `ai-rca-eval-2.json`. None was acted on: the flags were off before they answered. The
  only entry with a true prediction, H1 of `ai-rca-eval.json` (checkout failing, but no outage), was confirmed by
  `(checkout's SERVER error ratio > 0.05) unless on() (the same ratio > 0.5)`: 14.4 % at 08:01:00, nothing at the
  baseline instant 07:50:26.
- 08:28:19 - final snapshot taken.

## Supporting information

`itsmlab incident 4` on the committed snapshot printed onset 07:55:26, detection 07:58:38 (ServiceLatencyRaised),
acknowledgement 07:59:57, recovery 08:05:38, MTTD 192 s, MTTA 79 s, MTTR 612 s. The pager's log shows seven
notifications: chat at 07:58:48 (ServiceLatencyRaised on product-catalog and recommendation) and 07:58:49
(FrontendLatencyHigh), before the P1 fired; pager firing at 07:59:49 (CheckoutErrorRate) and 08:01:49
(CheckoutLatencyHigh), resolved at 08:03:49 and 08:04:49; chat resolved at 08:05:48. The AI ledgers are
`ai-rca-eval.json` (qwen3:1.7b) and `ai-rca-eval-2.json` (qwen3:4b-instruct), compared in `ai-rca/COMPARISON.md`.
The rules are `prometheus/demo-alerts.yml`, the routes `alertmanager/alertmanager.yml`.

## Problem record

- Incident record: 23b2e067-02e9-441b-8f1c-4ce22042bd54 (P1, acknowledged 07:59:57 UTC, service restored 08:04:31 UTC)
- Root cause: runtime feature flags can switch product-catalog into failing and stalling modes and recommendation out of its cache, with no change record, no review and no metric that names a failing flag; callers of product-catalog have no timeout shorter than its stall
- Known error: when productCatalogFailure, productCatalogLockContention or recommendationCacheFailure is on, GetProduct fails for one product in ten, catalogue reads stall up to 30 s, recommendations lose their cache
- Workaround: read the flag source's state and switch the failing flags off one at a time (`POST /flags/<flag>/off`), watching checkout's errors and the frontend's latency after each
