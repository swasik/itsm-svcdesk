---
lab6_change:
  id: CHG-20261011T013226Z
  candidate: "itsmlab.local/lab6-candidate:a31685f87c87"
  stable: "ghcr.io/swasik/svcdesk-v2-seeded:2.0.0"
  strategy: flag
  change_type: standard
  risk: low
  rollback_plan: "Caddy weights back to stable 100 / canary 0 through the admin API in one call (never 0 0); in a flag run the flag off first. The stable build serves throughout and is never restarted."
  started: 2026-10-11T01:32:26Z
  finished: 2026-10-11T01:33:16Z
  outcome: rolled-back
  reason: "flag 10 %: the canary's searches stopped arriving - none observed for 15 s while about 60 should have (stuck at 87): a hung candidate"
  actions:
    - {at: 2026-10-11T01:32:27Z, action: "flag svcdesk-2-1: unknown % -> 0 % (dark, before the candidate starts)", autonomy: closed-loop}
    - {at: 2026-10-11T01:32:28Z, action: "read flag svcdesk-2-1 back from flagd: 0 of 40 evaluations on (asked for 0 %)", autonomy: read-only}
    - {at: 2026-10-11T01:32:29Z, action: "start svcdesk-canary with the candidate at weight 0", autonomy: closed-loop}
    - {at: 2026-10-11T01:32:33Z, action: "set weights 0/100: the candidate serves every user, dark (flag off)", autonomy: closed-loop}
    - {at: 2026-10-11T01:32:33Z, action: "flag svcdesk-2-1: 0 % -> 10 % (step 1)", autonomy: closed-loop}
    - {at: 2026-10-11T01:32:34Z, action: "read flag svcdesk-2-1 back from flagd: 9 of 40 evaluations on (asked for 10 %)", autonomy: read-only}
    - {at: 2026-10-11T01:32:34Z, action: "flag 10 %: read the canary's and the stable build's search counters from Prometheus (phase start)", autonomy: read-only}
    - {at: 2026-10-11T01:33:15Z, action: "flag svcdesk-2-1: 10 % -> 0 % (roll back: every search on 2.0.0's path)", autonomy: closed-loop}
    - {at: 2026-10-11T01:33:16Z, action: "read flag svcdesk-2-1 back from flagd: 0 of 40 evaluations on (asked for 0 %)", autonomy: read-only}
    - {at: 2026-10-11T01:33:16Z, action: "set weights 100/0 (roll back: the stable build serves every request)", autonomy: closed-loop}
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

This run: candidate itsmlab.local/lab6-candidate:a31685f87c87, strategy flag.
