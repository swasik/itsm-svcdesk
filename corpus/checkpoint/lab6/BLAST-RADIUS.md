---
lab6_blast_radius:
  postmortem_action: {bug: ITSM-42, commit: 0000000000000000000000000000000000000000}
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this from design/LAB6.md sections 3 and 10 and its own calibration runs of 30 September 2026; the lecturer reviews it -->

# Blast radius of the svcdesk 2.1 release

`deploy.sh` releases one candidate at a time through `release/compose.yml`: Caddy (`edge`) splits the users'
searches by weight between the stable build, the candidate and `shadow`, an nginx that answers from the stable build
and copies each search to the candidate; a gate reads the candidate's own SLIs from Prometheus. The numbers below are
what `deploy.config.yaml` says and why. Every run quoted here is the course's traffic (40 searches a second, 1 s
patience from the scheduled instant) through this stack, on 30 September 2026, with the TEST-key images and the
practice seeds `p01`..`p16`.

## Gate

The baseline is the checkpoint `slo.md` (`itsmlab.yaml`: `baselines: {lab3: checkpoint}`): availability 99.5 % and
latency 99 % under 0.3 s, both over 28 days. Their error budgets are 0.5 % and 1 % of the searches. The gate's
thresholds are burn rates of those budgets: with `max_burn_rate: 10` on both, a phase fails when more than
**10 x 0.5 % = 5 %** of the candidate's searches answer 5xx, or more than **10 x 1 % = 10 %** take longer than 0.3 s.
That is far below what a bad candidate does (every one reaches at least 30 %: burn 60 on availability, 30 on latency)
and far above what an honest one does: over the steps of the 17 honest runs the candidates answered 12 of 8,796
searches with a 5xx (0.14 %, `kb-index`'s own failures: burn 0.3) and none took over 0.3 s on the `itsm-reference`
profile.

How many searches before a bad share can be told from that floor. The gate judges a share only over at least 20
canary searches and only when at least 12 of them were bad (the two fixed guards in `deploy.sh`), and it looks every
5 s - 20 searches a look at weight 10. For this profile any bad count would do; the 12 is for the slowest kb-index
profile the course has, with 4.5 % of its searches over the threshold. With at least 5 bad, such an honest candidate
would be rolled back in 4.8 % of runs (exact binomial over the looks of both steps: 5/40 is already 12.5 %); with 12,
in 0.73 %. A candidate at the lowest bad share the images draw (30 %) is then caught by the second look (40 searches)
with probability 0.56, by the third with 0.97 and by the fourth with 0.999 - and still by the fifth with 0.99 at the
loosest threshold R-09 allows (20 %). Measured, the 12 costs nothing visible: the first look that sees 20 searches
usually sees 30 with 12-16 bad among them (errors q 0.31-0.32: 14, 27 and 19 failed requests with 12; 15, 13 and 25
with 5).

What the empty-data case decides. **No data never passes**: a step needs its `min_duration` and `min_requests: 150`
searches it counted itself. A hung candidate answers at most 120 searches before it stops, so it can never collect
150, and because it is not observed at all, its 5xx and latency shares look perfect. What catches it is the collapse
rule: over a 15 s window (three scrapes), the candidate's share of all processed searches must be at least a quarter
of what its weight sends it (2.5 % at weight 10, 12.5 % at 50 %, and 12.5 % in the shadow, where it should process a
copy of every search, i.e. half of all). If Prometheus has no searches at all over the window, the phase fails too;
a read Prometheus does not answer is a missed read, never zero. The window lies inside every phase (steps last 45 s
and 20 s), and the shadow needs 200 copies, more than the 120 after which a hang stops: a hang can pass neither.

## Blast radius

Lecture 6's estimate is **failures ~ c + R x w x q x D**: R = 40 searches a second, w the candidate's weight while it
misbehaves, q its bad share (1 for a hang once it has stopped), D how long it misbehaves under that weight before the
rollback is in place, and c what the script breaks by itself. Here c is at most 1: every change of the routing is one
`POST /load` to Caddy, which never restarts anything, and in 66 runs 10 loads dropped one kept-alive user request each
(a headerless failure). The honest runs' 0-3 are that and the candidate's own `kb-index` 5xx above the stable-derived
floor that R-19 subtracts.

| run | release | behaviour | outcome | blast radius (headerless + candidate 5xx - floor) | D | c + R w q D | script |
|---|---|---|---|---|---|---|---|
| p01 rc.4 | shadow + canary | honest | promoted | 2 (0 + 4 - 2) | - | 0 | 91 s |
| p02 rc.2 | shadow + canary | honest | promoted | 0 (0 + 1 - 2) | - | 0 | 88 s |
| p03 rc.3 | shadow + canary | honest | promoted | 0 (0 + 1 - 2) | - | 0 | 88 s |
| p04 rc.2 | shadow + canary | honest | promoted | 0 (0 + 0 - 4) | - | 0 | 91 s |
| p05 rc.1 | shadow + canary | honest | promoted | 2 (1 + 2 - 1) | - | 0 | 89 s |
| p06 rc.3 | shadow + canary | honest | promoted | 0 (0 + 0 - 3) | - | 0 | 88 s |
| p07 rc.4 | shadow + canary | honest | promoted | 3 (3 + 2 - 3) | - | 0 | 92 s |
| p08 rc.4 | shadow + canary | honest | promoted | 1 (1 + 0 - 2) | - | 0 | 89 s |
| p09 rc.4 | shadow + canary | honest | promoted | 1 (1 + 2 - 2) | - | 0 | 89 s |
| p10 rc.3 | shadow + canary | honest | promoted | 0 (0 + 2 - 2) | - | 0 | 88 s |
| p13 rc.1 | shadow + canary | errors, q 0.51 | rolled back in the shadow | 0 (0 + 0 - 0) | 0 | 0 | 14 s |
| p16 rc.2 | shadow + canary | errors, q 0.32 | rolled back in the shadow | 1 (1 + 0 - 0) | 0 | 0 | 15 s |
| p02 rc.3 | shadow + canary | slow, q 0.51, +2.0 s | rolled back in the shadow | 0 (0 + 0 - 0) | 0 | 0 | 12 s |
| p13 rc.2 | shadow + canary | slow, q 0.33, +1.7 s | rolled back in the shadow | 1 (1 + 0 - 0) | 0 | 0 | 17 s |
| p14 rc.2 | shadow + canary | hang after 80 | rolled back in the shadow | 0 (0 + 0 - 0) | 0 | 0 | 23 s |
| p09 rc.2 | shadow + canary | hang after 110 | rolled back in the shadow | 0 (0 + 0 - 0) | 0 | 0 | 25 s |
| p02 rc.4 | canary only | errors, q 0.31 | rolled back | 14 (0 + 14 - 0) | 8 s | 10 | 13 s |
| p06 rc.2 | canary only | errors, q 0.31 | rolled back | 27 (0 + 27 - 0) | 13 s | 17 | 20 s |
| p08 rc.1 | canary only | errors, q 0.32 | rolled back | 19 (0 + 19 - 0) | 13 s | 17 | 18 s |
| p01 rc.3 | canary only | errors, q 0.49 | rolled back | 29 (1 + 28 - 0) | 14 s | 26 | 18 s |
| p12 rc.1 | canary only | errors, q 0.60 | rolled back | 38 (0 + 38 - 0) | 13 s | 32 | 19 s |
| p08 rc.3 | canary only | slow, q 0.32, +1.9 s | rolled back | 20 (20 + 0 - 0) | 18 s | 23 | 23 s |
| p15 rc.1 | canary only | slow, q 0.34, +1.5 s | rolled back | 24 (24 + 0 - 0) | 18 s | 25 | 23 s |
| p12 rc.3 | canary only | slow, q 0.38, +1.8 s | rolled back | 21 (21 + 0 - 0) | 13 s | 20 | 18 s |
| p10 rc.4 | canary only | slow, q 0.39, +1.4 s | rolled back | 27 (27 + 0 - 0) | 18 s | 29 | 25 s |
| p04 rc.1 | canary only | slow, q 0.54, +2.0 s | rolled back | 30 (30 + 0 - 0) | 13 s | 29 | 19 s |
| p04 rc.3 | canary only | hang after 115 | rolled back | 45 (45 + 0 - 0) | 11 s hung | 45 | 45 s |
| p09 rc.2 | canary only | hang after 110 | rolled back | 50 (50 + 0 - 0) | 14 s hung | 55 | 43 s |
| p07 rc.3 | canary only | hang after 108 | rolled back | 52 (52 + 0 - 0) | 14 s hung | 54 | 46 s |
| p12 rc.4 | canary only | hang after 46 | rolled back | 54 (54 + 0 - 0) | 13 s hung | 54 | 32 s |
| p05 rc.2 | canary only | hang after 48 | rolled back | 52 (52 + 0 - 0) | 13 s hung | 53 | 28 s |
| p11 rc.3 | canary only | honest | promoted | 3 (0 + 5 - 2) | - | 0 | 70 s |
| p12 rc.2 | canary only | honest | promoted | 1 (0 + 2 - 1) | - | 0 | 70 s |
| p13 rc.4 | flag | honest | promoted | 0 (0 + 2 - 2) | - | 0 | 75 s |
| p14 rc.4 | flag | honest | promoted | 0 (0 + 4 - 9) | - | 0 | 74 s |
| p14 rc.3 | flag | errors, q 0.36 | rolled back | 23 (0 + 24 - 1) | 11 s | 16 | 19 s |
| p16 rc.4 | flag | slow, q 0.44, +1.5 s | rolled back | 33 (32 + 2 - 1) | 22 s | 38 | 26 s |
| p15 rc.2 | flag | hang after 104 | rolled back | 53 (53 + 3 - 5) | 14 s hung | 56 | 46 s |
| p05 rc.2 | flag | hang after 48 | rolled back | 71 (71 + 1 - 2) | 15 s hung | 61 | 32 s |

The practice runs committed under `changes/` (`itsmlab verify 6 --save`, seed `practice`) fit the same estimate:
rc.1 (hang after 87), rc.2 (slow), rc.3 (honest) and rc.4 (errors) cost 0 each - every bad one was rolled back in
the shadow, after 87, 408 and 407 copies, and the honest one had 610 before its first user answer - and of the two
flag runs, rc.3 (honest) cost 1 (R-19's floor noise) and rc.1 (hang) 43: it stopped answering 26 s into the run and
the flag went off at 37 s, 40 x 0.1 x 11 s = 44.

"Canary only" is this script with `shadow: null`, the Core release every student builds; D runs from the first
user search the candidate answered (a hang: from its last answer) to the script's exit. The estimate holds within a
few requests in every run, and it says where the budget goes: D is 8-18 s for a bad share (the first look with 20
searches, plus one scrape and one look of lag) and 11-15 s for a hang (the collapse window). At weight 10 the worst
run cost 54 of the ceiling's 150; the ceiling allows D up to 150 / (40 x 0.1) = 37 s for a hang, room for a window of
about 30 s. With the shadow, no bad candidate answered a single user search (R-29), and the release takes 88-92 s to
promote, 12-25 s to roll back.

Why not the plans that are shorter to write, each measured on the same day with the same gate: **100 % at once**
cost 125 and 119 for errors and slow at q 0.31 and 0.32 (under the ceiling only because the gate reacted in 10 s;
R-22 fails it anyway) and 698-768 for a hang; **25 % first** cost 46 (errors), 41 (slow) and 120-154 for a hang,
straddling the ceiling; **a 60 s window** cost 185-214 for a hang; **no collapse rule** let the hang run to the
deadline, 508-604; **a gate that passes on empty data** promoted the hang, 1,079-1,146 and no outcome; **weights
`0 0` on rollback** turned an errors rollback into an outage, 636-643 and no outcome.

## Change classification

A run of `deploy.sh` is a **standard change**: the procedure - this script with this `deploy.config.yaml` - is
reviewed and authorised once, before any run, and every run follows it without a human decision. The three
properties ITIL asks of a standard change hold and are measured: it is **pre-authorised** (the approval is of the
procedure, recorded by the commit it runs from, never given during a run - stdin is at end of file, so nobody could
approve anything then), **low risk** (at most 3 user requests failed in any run of the reference with its shadow,
and 54 in any run of its canary gate alone, against a ceiling of 150), and **well understood** (each of the four
behaviours a candidate can have was released five times or more, with the outcomes above, 39 of 39 right). It stops
being standard - and becomes a normal change that someone reviews - when the procedure changes: another plan, other
thresholds, or a candidate the gate cannot read (a build without the histogram, another scrape interval).

Risk is **low** because exposure is bounded before anything is known (copies first; then 10 % of the searches until
150 have been judged), detection is fast (8-18 s for a bad share of 30 % or more, 11-15 s for a hang), and recovery
is one admin-API call that the stable build, which never stops, absorbs at once.

The autonomy classes in every record follow Lecture 6's ladder. Everything the script changes - starting the
candidate, the weights, the shadow, the flag, promoting, rolling back - is **closed-loop**: the gate decides and the
script acts, because no human is there to ask. Everything it reads to decide - the candidate's build and every gate
phase's readings from Prometheus - is **read-only**. Nothing is `suggest` or `approve-then-act`: an approval inside
the run cannot exist, and one before it is the standard change itself. What keeps closed-loop safe here is that the
loop can only move towards the stable build without a passed gate: any unexpected error rolls back, and a rollback
that fails exits 1, which the runner records as a run without an outcome instead of a claimed one.

## Postmortem action

The Lab 4 baseline is the checkpoint postmortem (`itsmlab.yaml`: `baselines: {lab4: checkpoint}`), whose incident
was three feature flags switched on at full strength at once: nothing stood between the flip and every user. Its
action item **ITSM-42** is "Put the payment and shipping flags behind a percentage rollout that starts at 1 %".
This repository's release has the same kind of switch - svcdesk 2.1's new code is behind the flag `svcdesk-2-1` -
and the commit named in the front matter gives it that rollout: `RELEASE_STRATEGY=flag` deploys the candidate dark
(flag off: 2.0.0's code on every search), then raises the flag through flagd's `fractional` in the steps of
`deploy.config.yaml`'s `flag:`, lets the gate judge only the searches that got `on`, and turns the flag on for
everyone only after the last step passed; any failed step turns it off for everyone within about a second. Every
change of the flag is an action in `CHANGE.md`, with its time and its autonomy class, which is the record ITSM-41
asked an alert for.

The first step is 10 %, not the 1 % of the action item, and that is arithmetic rather than neglect. The shop's 1 %
was sized for the shop's traffic; here 1 % of 40 searches a second is 0.4 a second, so the gate's 150 searches would
take 375 s, over twice the 170 s deadline, and even the 20 searches before any bad share is judged take 50 s. What
carries over is the principle - a first exposure small enough that the gate knows before many users do - and its
measure is the number of users a bad step can hurt: in the six flag runs above, 0 for the honest candidate and 23,
33, 53 and 71 for the bad ones, all rolled back by the flag alone, against the 150 a release may cost.
