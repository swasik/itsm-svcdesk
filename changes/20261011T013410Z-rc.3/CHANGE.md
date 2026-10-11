---
lab6_change:
  id: CHG-20261011T013410Z
  candidate: "itsmlab.local/lab6-candidate:02482186182a"
  stable: "ghcr.io/swasik/svcdesk-v2-seeded:2.0.0"
  strategy: flag
  change_type: standard
  risk: low
  rollback_plan: "Caddy weights back to stable 100 / canary 0 through the admin API in one call (never 0 0); in a flag run the flag off first. The stable build serves throughout and is never restarted."
  started: 2026-10-11T01:34:10Z
  finished: 2026-10-11T01:35:23Z
  outcome: promoted
  reason: "every flag step passed: flag 50 % passed: 363 canary searches, 5xx 0.6 % (<= 5.0 %), slow 0.0 % (<= 10.0 %), 4 looks"
  actions:
    - {at: 2026-10-11T01:34:11Z, action: "flag svcdesk-2-1: unknown % -> 0 % (dark, before the candidate starts)", autonomy: closed-loop}
    - {at: 2026-10-11T01:34:12Z, action: "read flag svcdesk-2-1 back from flagd: 0 of 40 evaluations on (asked for 0 %)", autonomy: read-only}
    - {at: 2026-10-11T01:34:13Z, action: "start svcdesk-canary with the candidate at weight 0", autonomy: closed-loop}
    - {at: 2026-10-11T01:34:13Z, action: "set weights 0/100: the candidate serves every user, dark (flag off)", autonomy: closed-loop}
    - {at: 2026-10-11T01:34:13Z, action: "flag svcdesk-2-1: 0 % -> 10 % (step 1)", autonomy: closed-loop}
    - {at: 2026-10-11T01:34:14Z, action: "read flag svcdesk-2-1 back from flagd: 3 of 40 evaluations on (asked for 10 %)", autonomy: read-only}
    - {at: 2026-10-11T01:34:14Z, action: "flag 10 %: read the canary's and the stable build's search counters from Prometheus (phase start)", autonomy: read-only}
    - {at: 2026-10-11T01:35:00Z, action: "flag 10 %: 9 reads of the canary's SLIs from Prometheus; passed with 167 searches", autonomy: read-only}
    - {at: 2026-10-11T01:35:00Z, action: "flag svcdesk-2-1: 10 % -> 50 % (step 2)", autonomy: closed-loop}
    - {at: 2026-10-11T01:35:01Z, action: "read flag svcdesk-2-1 back from flagd: 28 of 40 evaluations on (asked for 50 %)", autonomy: read-only}
    - {at: 2026-10-11T01:35:02Z, action: "flag 50 %: read the canary's and the stable build's search counters from Prometheus (phase start)", autonomy: read-only}
    - {at: 2026-10-11T01:35:22Z, action: "flag 50 %: 4 reads of the canary's SLIs from Prometheus; passed with 363 searches", autonomy: read-only}
    - {at: 2026-10-11T01:35:22Z, action: "flag svcdesk-2-1: 50 % -> 100 % (promote)", autonomy: closed-loop}
    - {at: 2026-10-11T01:35:23Z, action: "read flag svcdesk-2-1 back from flagd: 40 of 40 evaluations on (asked for 100 %)", autonomy: read-only}
---
# Change record

## Why this change type

A standard change: this procedure is pre-authorised once, for every candidate of svcdesk 2.x that the course
pipeline built, and runs with nobody at the keyboard. It earns the pre-authorisation because its risk is bounded by
construction, not by a person watching: the candidate first gets only a mirrored copy of the traffic (the shadow,
whose answers nobody sees), then 10 % of the users, then 50 %, and every step is judged against my Lab 3 SLO as burn
rates - 5xx above 5.0 % or slower than 0.3 s above 10.0 % fails it, as does a canary whose
searches stop arriving. My four practice runs and the practice seeds are the evidence that the procedure is well
understood. It would become a normal change - assessed and authorised by a person before the run - for anything
outside that envelope: a candidate that changes the API or the data, a plan with a first step above 20 %, a gate
change that has not yet been through the practice seeds, or a stack without the shadow. An emergency change would
skip the shadow and the 45 s step; I would give up the bound on the blast radius, and only for a fix that stops a
larger outage.

## Risk and what bounds it

Users can be hurt only once the candidate answers them. In the shadow phase that never happens: users get 2.0.0
through nginx, and a bad candidate is rolled back there. If a bad candidate passed the shadow, the 10 % step bounds
it: failures ~ c + R x w x q x D = 5 + 40 x 0.1 x q x D; for errors at q = 0.6 and D = 12 s that is about 34, for a
hang (q = 1, c = 0, D = the 12 s stall rule + a scrape + a look, about 22 s) about 88 - under the ceiling of 150.
What my gate cannot see: a candidate that breaks only routes other than /kb/search, and a fault that starts after
promotion.

This run: candidate itsmlab.local/lab6-candidate:02482186182a, strategy flag.
