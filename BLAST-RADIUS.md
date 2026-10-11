---
lab6_blast_radius:
  postmortem_action: {bug: ITSM-103, commit: 29fa11000e20511c4a9067044c2c37703d70790b}
---
<!-- ai-generated: 40% - an AI assistant drafted the prose from my run logs and my arithmetic; the numbers are my runs' and I checked each one -->

# Blast radius

## Gate

**Baseline: my own Lab 3 SLO** (`baselines: {lab3: student}`): 28 days, availability 99.5 %, latency 99 % within
0.3 s. My threshold is 0.3 s, under the 1 s limit. My Lab 3 stack ran `kb-index` with the profile
`itsm-reference`; R-02 wants my login in the release stack, so `release/compose.yml` runs the profile `swasik`
(commit b62f9ec), and that profile too lets 2.0.0 meet both objectives with room to spare (below), so I had no reason
to take the checkpoint.

**Thresholds as burn rates.** `max_burn_rate: 10` on both SLIs: a step fails when the canary's 5xx share exceeds
10 x (1 - 0.995) = **5 %**, or its share slower than 0.3 s exceeds 10 x (1 - 0.99) = **10 %**. The floor my stable
build showed: in the traffic table about 9 failures in 3,600 searches (0.25 %, burn 0.5) and a p99 of 230-260 ms;
over the checker's warm-ups 0.15-0.27 % 5xx and 0.00-0.05 % slower than 0.3 s with `itsm-reference`, and with
`swasik` 0.19-0.25 % 5xx and 0.00 % slow over 4,808 warm-up answers (advisory `stable-vs-gate`, against
half-thresholds of 2.5 % and 5 %). So the honest floor sits 20 to 200 times below my thresholds, and every errors or
slow candidate (at least 30 %, burn 60 and 30) sits 6 and 3 times above them. A burn rate of 1 (0.5 %) would sit on
top of kb-index's 0.4 % worst profile; 40 (20 %) would leave only a factor 1.5 to the weakest bad candidate. 10 is
the middle of that gap on a log scale.

**How the gate decides, and on how many searches.** Every 5 s (my `interval`, equal to the scrape interval) it
reads absolute counters - the canary's searches, its 5xx, its searches within 0.3 s (`le="0.3"`), and the same on
the stable track - and subtracts their values at the start of the phase. No range window: a `[5m]` window would
judge a 45 s step on the time before it (trap 4), and a `[5s]` window holds one sample and returns nothing. A step
fails when a share is above its threshold **and** rests on at least 5 bad searches **and** exceeds the stable
build's share over the same phase by more than half the threshold. The count of 5 kills the "first 5xx" trap: at a
0.4 % floor, P(at least 5 errors in the first 20 searches) is about 1e-8, and over a whole 45 s step at 10 % (180
searches) 5 errors are 0.08 % likely - and 5 of 180 is 2.8 %, under the 5 % threshold anyway. The control (stable's share)
removes what both builds share - kb-index's failures and a loaded host - so a slow laptop slows both tracks and fails
neither. A 30 % candidate is caught at the first look that sees about 17 of its searches (5 bad at 30 %).

The phases: **the shadow** (Stretch 1) mirrors every user search to the candidate, 40 a second, for at least 10 s and
150 searches; then **10 % for 45 s** (4 searches a second, about 180, `min_requests: 150` met after about 38 s);
then **50 % for 20 s** (about 400); then promote. Because the shadow sees 400 searches before any user does, the
weighted steps meet only candidates that already passed on that much evidence.

**No data.** Every count query ends in `or vector(0)`, so "no 5xx series" reads as 0 bad, never as "no data". The
empty case that matters is the hang: past its onset none of its searches is observed, so its counters freeze and
every share stays at its honest value. My gate therefore watches arrivals: if the canary's search counter has not
moved for 12 s (more than two scrapes and a look) while the traffic should have brought it at least 20 searches
(the stable track's increase, times w / (100 - w) - or all of it in the shadow, which mirrors everything), the
step fails: "the canary's searches stopped arriving". A hang answers at most 120 searches; my shadow wants 150, so
a hang always freezes inside the shadow, where no user waits on it. Three unreadable Prometheus looks in a row also
roll back: no evidence, no promotion. And 15 s before my own deadline (165 s) the gate stops and rolls back.

## Blast radius

The four practice runs of `itsmlab verify 6 --save` (seed `practice`, "practice table: course key": the published
`svcdesk-v2-seeded` images), and the two flag runs it saves for Stretch 2, in `changes/`:

| run | behaviour | outcome | measured blast radius | c | w | q | D (s) | predicted |
|---|---|---|---|---|---|---|---|---|
| `20261011T165046Z-rc.1` | hang (k = 40) | rolled back in the shadow, 28 s after the start: the canary's count stuck at 40 for 15 s while about 600 were mirrored | **0** | 0 | 0 (shadow) | 1 | about 20 | 0 |
| `20261011T165211Z-rc.2` | honest | promoted, 87 s: shadow (541 searches before the first user answer), 10 % for 45 s, 50 % for 20 s | **2** (4 candidate 5xx on 1,196 answers, floor 2) | - | 0.1, 0.5 | 0.0015 (kb-index) | - | about 0 |
| `20261011T165434Z-rc.3` | slow | rolled back in the shadow, 13 s: 36 of 111 searches over 0.3 s (32.4 %) against 10 % | **0** | 5 | 0 (shadow) | about 0.3 | about 8 | 0 |
| `20261011T165542Z-rc.4` | errors | rolled back in the shadow, 14 s: 77 of 182 searches 5xx (42.3 %) against 5 % | **0** | 5 | 0 (shadow) | about 0.42 | about 8 | 0 |
| `20261011T165652Z-rc.1` (flag) | hang (k = 40) | rolled back at flag 10 %, 37 s: no flag-on search for 15 s | **84** (all timeouts) | 0 | 0.10 | 1 | about 22 | 88 |
| `20261011T165824Z-rc.2` (flag) | honest | promoted, 78 s: flag 10 % for 45 s, 50 % for 20 s | **1** (8 candidate 5xx on 3,487 answers, floor 7) | - | 0.1, 0.5 | kb-index | - | about 0 |

Which slot did what is the course key's draw, not the one I first practised on (there rc.3 was honest and rc.2
slow): my gate has no notion of a slot, and the same commit gave the right outcome under both.

Prediction with `failures ~ c + R x w x q x D`: in the shadow phase **w = 0** for users - nginx answers every user
from 2.0.0 and throws the candidate's copy away - so R x w x q x D is 0 whatever D is, and c is paid by mirrored
copies, not by users. Every bad candidate was caught there; the measured blast radius of the three bad runs is
kb-index's ordinary noise, as the formula predicts. The honest run's few failures are kb-index's floor on the
candidate's answers, minus the floor the stable build's share predicts (R-19), not a cost of the release.

Without the shadow the same gate would pay at the 10 % step: errors at q = 0.6, c = 5, D = about 12 s (a scrape, a
look, the admin call): 5 + 40 x 0.1 x 0.6 x 12 = about 34; a hang (c = 0, q = 1) with D = 12 s of silence + up to 5 s
of scrape + 5 s of look = 22 s: 40 x 0.1 x 1 x 22 = 88. My flag runs measure that path, because a flag run has no
shadow: the hang above cost 84 against 88 predicted - D is the term that dominates: 15-16 s until my stall rule
(12 s without a new search, checked every 5 s) fires, up to 5 s of scrape before the last search shows, 2 s because
my looks read Prometheus 2 s in the past, and the admin call. The honest flag run's 8 candidate 5xx on 3,487 answers
(0.23 %) are kb-index's floor; the stable build's share (0.21 %) predicts 7 of them, so 1 counts. (My first flag practice run,
with the TEST builds, counted 10: its warm-up happened to have no 5xx, so its floor was 0.) What would push a run over
150: a first step of 25 % or more with the same D (40 x 0.25 x 1 x 22 = 220), a `[1m]` window that keeps the hang's old searches in view, or a gate that waits
for `min_requests` before it looks at arrivals at all.

Beyond the four runs: `itsmlab verify 6 --seed p01` .. `p16` (run against the course's TEST builds of the images,
before the published ones reached my machine), every one with the gate of commit 29fa110, gave the
right outcome in all 64 canary runs (blast radius 0 for every bad candidate - all caught in the shadow - and 0 to 4
for the honest one) and all 32 flag runs (bad: 8 to 23 for errors and slow, 67 to 100 for the hang). Six of them
(p02, p03, p05, p07, p13, p14) again with the current gate (one read instant per look, below): the same 36
right outcomes, the hang's flag runs at 77 to 97. That spread is the case for the
shadow: 100 is two thirds of the ceiling, and it is what the hang costs at 10 % with a 12 s stall rule.

One bug the logs showed me: my counters were six separate queries, and when a scrape landed between the count and
its `le` bucket, a whole scrape's searches read as slow or as negative (the control's slow share once read -100 %).
Read at the start of a step, after the shadow's 200 searches a scrape, that could have rolled back the honest
candidate. Every look now reads all its counters at one instant 2 s in the past (commit e3fae3d).

## Change classification

My records declare a **standard** change, risk **low**. A standard change is pre-authorised because its procedure
is well understood and its risk bounded; here the bound is not a promise but a mechanism I measured: the shadow
keeps a bad candidate away from every user (blast radius 0 in all bad practice runs), and if it did not, the 10 %
step caps the worst case near 90 failed searches, under the 150 ceiling. The evidence is the four committed runs and
sixteen practice seeds of the checker, each with four candidates. What would make it a **normal** change: a
candidate that changes the API or the data (the gate only watches `/kb/search`), a stack without the shadow, a
first step above 20 %, or any change to the gate itself until it has been through the practice seeds again - then a
person approves before the run, because nobody can during it.

The autonomy of each action, as the records list it:

- **start the candidate at weight 0 - closed-loop.** It changes nothing a user sees, and the procedure as a whole
  is pre-authorised; no person decides it per run.
- **read Prometheus, read the flag back from flagd - read-only.** They change nothing; they are the evidence.
- **set a weight or a flag share up a step - closed-loop.** The gate decides from its own readings that the last
  step passed. A person could not do better at 5 s intervals, and a `suggest` here would stall an unattended run.
- **roll back - closed-loop.** The cheapest, best-understood action: stable never stopped serving; one admin call.
- **promote - closed-loop**, and the one I would move to **approve-then-act** outside a course lab: in production
  the approval would be the standard-change model itself, signed by the service owner before the release window,
  and I would want a person to approve the promotion of a candidate that changes the data or the API.

What would change my classification: a false rollback of an honest candidate in practice (the procedure is not
well understood), or a bad candidate reaching users through the shadow (the bound does not hold).

## Postmortem action

My Lab 4 postmortem (`postmortem.md`, my own: `baselines: {lab4: student}`) found that the incident was three
feature flags switched on together in the shop's flagd, with nobody recording the change: the on-call found them
only by reading `/flags.json` after the symptoms. Its action item **ITSM-103** (type prevent, owner platform team)
asks to "Record every runtime flag change as a change in svcdesk, and export the count of failing flags as a metric
the dashboards show". None of my five action items is a release-gate change in the strict sense - ITSM-101 and
ITSM-102 are alerting rules, ITSM-104 is a timeout in the shop's code, ITSM-105 a runbook step - and ITSM-103 is the
one a release process can honestly implement, because my `deploy.sh` itself changes a runtime flag (`svcdesk-2-1`,
Stretch 2).

Commit 29fa110 implements the first half for every flag change my release process makes: each one goes through
`change_flag`, which writes it into the change record as a closed-loop action with its before and after ("flag
svcdesk-2-1: 10 % -> 50 % (step 2)"), and then reads the flag back from flagd itself - 40 OFREP evaluations with
random targeting keys - and records what flagd actually serves as a read-only action ("17 of 40 evaluations on").
A change flagd does not serve is a failed change: going dark fails the run before the candidate starts, and a step
that flagd does not apply rolls back. That matters because flagd silently ignores a flag file it cannot read; without
the read-back the record would claim a change that never happened - the opposite of what ITSM-103 wants. My practice
flag runs show it working: the honest flag run's record (`changes/20261011T165824Z-rc.2/CHANGE.md`) lists 0 -> 10 -> 50 -> 100 % with
read-backs of 0/40, 4/40, 19/40 and 40/40, and the hang's flag run records 0 -> 10 -> 0 % with each read back.

Where it stops short: the record is `CHANGE.md` in this repository, not a change in svcdesk's own records; it covers
the flags this release changes, not a flag someone flips by hand in the shop's flagd (the Lab 4 incident's case);
and the second half, a failing-flag metric on the dashboards, is not done - a record per release is not a time
series. Closing those needs the flag change to go through one tool that both writes the svcdesk change and exports
the gauge, which is the platform team's part of ITSM-103.
