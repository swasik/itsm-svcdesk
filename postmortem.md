---
lab4_postmortem:
  ticket: "61e3fa62-3f3f-44cc-970c-8185d6bffdff"
  detecting_alert: ServiceLatencyRaised
  onset: 2026-10-10T23:07:36Z
  detection: 2026-10-10T23:11:08Z
  acknowledgement: 2026-10-10T23:11:25Z
  recovery: 2026-10-10T23:13:08Z
  mttd_seconds: 212
  mtta_seconds: 17
  mttr_seconds: 332
  identified_flags: [productCatalogFailure, intlShippingSlowdown, recommendationCacheFailure]
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) worked the incident as the student and wrote this postmortem from its own notes and queries -->

# Postmortem: one order in twelve failed and product pages broke for eight minutes

## Date

The incident happened on Saturday 10 October 2026 (UTC) between 23:07:36 and 23:15:31; this postmortem was written
the same night, about half an hour after the last flag was switched off.

## Authors

The on-call engineer for the shop, who was paged, opened and acknowledged the P1 ticket, switched the flags off and
scored the AI investigator.

## Status

Complete for the incident: service restored at 23:15:31 and the ticket acknowledged. Action items in progress; the
problem record below stays open.

## Summary

From 23:07:36 to 23:15:31 UTC three feature flags failed at once. Product-catalog's GetProduct failed for one product
in ten, which failed one order in twelve and broke product and recommendation pages; non-US orders slowed by ten
seconds in shipping; and the recommendation service ran without its cache. Switching the three flags off restored
service within eight minutes of the onset.

## Impact

Measured on the span metrics in the snapshot (SERVER spans; counters are cumulative, so the error counts are the
values the error series reached, which started at the onset):

- **Orders**: 50 PlaceOrder calls were made between 23:07:30 and 23:16:00
  (`sum(traces_span_metrics_calls_total{service_name="checkout",span_name="oteldemo.CheckoutService/PlaceOrder"})`,
  91 then 141); **4 of them failed** (8 %), `max_over_time(traces_span_metrics_calls_total{service_name="checkout",
  status_code="STATUS_CODE_ERROR"}[20m])` = 4. At its worst, 16 % of checkout's SERVER spans failed over five
  minutes (23:12:00).
- **Product pages**: 38 GetProduct calls of product-catalog failed, and so did 38 `GET /api/products/[productId]`
  pages and 30 `GET /api/recommendations` calls of the frontend (the recommended products are fetched through the
  same GetProduct); 8 `POST /api/checkout` calls of the frontend failed. The frontend's SERVER error ratio was 7.5 %
  over the five minutes to 23:12:00 (`sum(rate(...{service_name="frontend",status_code="STATUS_CODE_ERROR"}[5m])) /
  sum(rate(...{service_name="frontend"}[5m]))`), against 0 on the healthy baseline.
- **Slow orders**: shipping's p95 reached 2600 ms over five minutes at 23:12:00 (185 ms healthy); one order took
  longer than 5 s in shipping and in checkout (`calls_total - duration_milliseconds_bucket{le="5000"}`, 0 before
  and 1 after). Checkout's p95 crossed 3 s for one minute (CheckoutLatencyHigh, 23:12:09 to 23:12:59).
- **Recommendations without cache**: no visible user impact within the eight minutes; recommendation's resident
  memory grew from 73.0 MB to 76.0 MB (`process_runtime_cpython_memory_bytes{service_name="recommendation",type="rss"}`)
  and its p95 stayed under 10 ms.

## Root Causes

Three flags of the demo's flag provider switched to failing values together. productCatalogFailure made
product-catalog answer GetProduct with an error for one product of the catalogue, so every order and every product
page containing that product failed. intlShippingSlowdown (variant 10sec) made shipping's ShipOrder ten seconds
slower for non-US addresses, which slowed the orders that shipped abroad. recommendationCacheFailure disabled the
recommendation service's cache, a resource fault whose memory and latency growth had not become visible when it was
switched off. What was already wrong: flags that can fail production paths are switchable at runtime by a source
that overrides the shop's own flag file, with no change record and no alert that names them.

## Trigger

At 23:07:36 UTC (the onset, the first sample of the injector's fault series) the flag source served the three
failing variants, and flagd picked them up on its next 5-second poll. Nothing was deployed; the change was a
configuration change of feature flags.

## Resolution

After reading the live flag state (`curl http://localhost:18090/flags.json`, 23:11:42) the on-call switched the
three flags off one at a time through the injector, in order of user impact, watching each: productCatalogFailure
at 23:11:53 (orders and pages failing; errors stopped within the next scrape), intlShippingSlowdown at 23:14:06
(slow orders abroad), recommendationCacheFailure at 23:15:30 (no user impact seen yet). The fault series went to 0
at 23:15:31. That is a workaround in ITIL's sense; the cause (flags that can be switched to failing values) stays.

## Detection

The first alert to fire after the onset was the P3 ServiceLatencyRaised on shipping, at 23:11:08 (MTTD 212 s); one
second later the P1 CheckoutErrorRate fired, and its page reached the pager at 23:11:19. Because the P1 fired, the
inhibit rule (`system="shop"`) muted the P3 in chat, so the alert that formally detected the incident notified no
one: the page did. Most of the 212 s is structural: the shop's metrics arrive once a minute, the rules use 5-minute
rates (the first failing minute moves a 5-minute ratio only a little) and `for: 1m`. Without the alert, shoppers
would have noticed first - 4 failed orders and 38 broken product pages in eight minutes.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Put the P3 cause alerts in the same rule group as the P1 pages, so that a page and its cause start on the same evaluation and the page is the detecting alert | process | on-call | none |
| Shorten `for:` on CheckoutErrorRate to 30 s and add a 1-minute-sample-aware burn-rate rule, to bring MTTD under two minutes | prevent | on-call | none |
| Record every runtime flag change as a change in svcdesk, and export the failing-flag count as a metric the dashboards show | prevent | platform team | none |
| Add a recommendation memory-growth alert to chat (cache failure is otherwise invisible for many minutes) | mitigate | on-call | none |
| Keep a runbook step "read /flags.json first" for checkout pages | process | on-call | none |

## Lessons Learned

### What went well

The page came 10 s after the P1 fired and the ticket was acknowledged 17 s after detection. Reading what changed
(the flag state) right after the symptoms named the three flags in under a minute; switching them off one at a time
showed which one caused the errors (they stopped after productCatalogFailure went off).

### What went wrong

The detecting alert by the rules was a P3 in a separate rule group that fired one second before the page and ended
at 23:13:08, two minutes before the last flag was off, so the recorded MTTR (332 s) is shorter than the real
recovery (475 s to 23:15:31). CheckoutLatencyHigh fired for one minute only: one slow order in a small sample moved
the p95 across 3 s and back. The resource fault (recommendation cache) left no signal any of the rules watched.

### Where we got lucky

The errors hit one product in ten, not checkout itself, so 92 % of orders still went through; and the shipping
slowdown hit few non-US orders in this window. A heavier draw (payment failing at 50 %) would have failed half the
orders for the same 212 s before anyone was paged.

## Timeline

All times UTC, 10 October 2026.

- 22:51:47 - the playground starts; the injector begins its 10-minute baseline. A practice ticket at 22:52:49
  proves svcdesk's requests reach Prometheus.
- 23:02:12 - `max_over_time(ALERTS{alertstate="firing", severity="P1"}[10m])` returns nothing; no alert at all.
- 23:02:14 - the injector is armed (onset window 2 to 6 minutes).
- 23:07:36 - **onset**: the injector's fault series starts.
- 23:10:08 - ServiceLatencyRaised (shipping p95 > 1 s) pending; 23:10:09 CheckoutErrorRate pending.
- 23:11:08 - **detection**: ServiceLatencyRaised fires (P3, routed to chat, inhibited by the P1 a second later).
- 23:11:09 - CheckoutErrorRate fires (P1); 23:11:19 the page reaches the pager.
- 23:11:25 - the P1 ticket 61e3fa62-3f3f-44cc-970c-8185d6bffdff is created and **acknowledged** at 23:11:25.
- 23:11:28 - symptoms: product-catalog GetProduct, frontend product pages and recommendations, checkout PlaceOrder
  failing; shipping p95 2.6 s, checkout p95 5 s.
- 23:11:42 - what changed: `/flags.json` shows productCatalogFailure on, intlShippingSlowdown 10sec,
  recommendationCacheFailure on.
- 23:11:53 - productCatalogFailure switched off (`changed: true`).
- 23:12:09 - CheckoutLatencyHigh fires (P1); paged at 23:12:19, resolved at 23:13:19.
- 23:13:08 - **recovery** as the rules define it: ServiceLatencyRaised's firing run ends.
- 23:14:03 - no new errors in any service over the last two minutes.
- 23:14:06 - intlShippingSlowdown switched off.
- 23:14:59 - CheckoutErrorRate's last firing sample; its resolved notification reaches the pager at 23:15:19.
- 23:15:30 - recommendationCacheFailure switched off; 23:15:31 the fault series goes to 0.
- 23:15:49 - the AI investigator (qwen3:1.7b) runs; its four hypotheses are scored in `ai-rca-eval.json`. None was
  acted on: the flags were off before it answered. Its best entry, H4 (product-catalog errors), was confirmed by
  `sum(rate(...{service_name="product-catalog",status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(...)) > 0.01`,
  7.3 % at 23:12:00 and nothing at 23:02:36.
- 23:20:19 - snapshot taken.

## Supporting information

`itsmlab incident 4` on the committed snapshot printed onset 23:07:36, detection 23:11:08 (ServiceLatencyRaised),
acknowledgement 23:11:25, recovery 23:13:08, MTTD 212 s, MTTA 17 s, MTTR 332 s. The pager's log shows four
notifications, all to `pager` (CheckoutErrorRate firing 23:11:19 and resolved 23:15:19; CheckoutLatencyHigh
firing 23:12:19 and resolved 23:13:19) and none to chat: every P2 and P3 was inhibited by a firing shop P1. The AI
ledgers are `ai-rca-eval.json` (qwen3:1.7b) and `ai-rca-eval-2.json` (qwen3:4b-instruct), compared in
`ai-rca/COMPARISON.md`. The rules are `prometheus/demo-alerts.yml`, the routes `alertmanager/alertmanager.yml`.

## Problem record

- Incident record: 61e3fa62-3f3f-44cc-970c-8185d6bffdff (P1, acknowledged 23:11:25 UTC, service restored 23:15:31 UTC)
- Root cause: runtime feature flags can switch product-catalog, shipping and recommendation into failing modes with no change record, no review and no metric that names a failing flag
- Known error: when productCatalogFailure, intlShippingSlowdown or recommendationCacheFailure is on, GetProduct fails for one product, non-US shipping slows by 5-10 s, recommendations lose their cache
- Workaround: read the flag source's state and switch the failing flags off one at a time (`POST /flags/<flag>/off`), watching checkout's errors and latency after each
