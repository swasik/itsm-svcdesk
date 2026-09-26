---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 40% - Claude Opus 5 drafted the structure from METRIC-SPEC.md; the lecturer wrote the reasoning -->

# Edge cases in the practice event log

Six of them, all covered by `METRIC-SPEC.md`, none covered by the definitions an assistant produces when
asked for "the DORA metrics". The counts above are what this service reports for
`fixtures/events-practice.jsonl` over the published window; the checker compares them with the service,
so they cannot be guessed.

## E1 - clock skew produces a negative lead time

- What the log contains: three commits whose `at` is later than the deployment that shipped them, by between
  thirty seconds and fifteen minutes. Two machines disagreed about the time, which is the ordinary cause.
- What a default definition would have done: `max(0, ...)` is rare; dropping the pair is common, and so is
  reporting a negative median. Dropping is the dangerous one, because it is silent.
- Why the rule is defensible: a clamped pair keeps the deployment in the denominator, so the median is not
  biased upward by discarding exactly the fastest-looking observations, and the anomaly count makes the
  measurement problem visible instead of hiding it inside a metric nobody questions.

## E2 - a revert of a revert

- What the log contains: two chains where a commit reverts a commit that is itself a revert. Under R-06 both
  revert commits inherit the original change, so three commits are one change.
- What a default definition would have done: count commits, not changes, and report three changes where there
  is one; or treat every revert as evidence of a failed change and inflate the rework rate.
- Why the rule is defensible: the unit DORA measures is a change that reaches users, and reverting a revert
  puts the original change back. Counting the round trip as three changes would reward churn, which is
  precisely the behaviour the instability metrics exist to detect.

## E3 - a hotfix that never touched `main`

- What the log contains: four commits on `hotfix/...` branches that were deployed straight to production, as
  hotfixes are. They never appear on `main` and never will.
- What a default definition would have done: filter commits on `branch == "main"`, which is what every tutorial
  query does, and lose the hotfixes - the very changes most worth measuring.
- Why the rule is defensible: the question the metric asks is how long a change took to reach production, and a
  hotfix reached production. A branch name is a workflow convention, not a fact about delivery.

## E4 - a deployment with zero linked commits

- What the log contains: four production deployments whose `commits` list is empty - a configuration rollout,
  a re-run of a failed job, and the two the failure injections produced.
- What a default definition would have done: drop the deployment (which understates deployment frequency and
  the change fail rate denominator) or divide by zero computing its lead time.
- Why the rule is defensible: a deployment happened, so deployment frequency must count it, and if it failed,
  the change fail rate must count it too. What it cannot do is contribute a lead time, because there is no
  commit to measure from. The two facts live in different metrics and the rule keeps them apart.

## E5 - a deployment that failed and never recovered

- What the log contains: one failed production deployment whose incident is still open at the end of the log.
- What a default definition would have done: treat the window's end as the recovery instant, which invents a
  number, or drop the deployment entirely, which quietly improves the change fail rate.
- Why the rule is defensible: an unrecovered failure has no recovery time, and inventing one would make the
  recovery median better the longer an incident stays open. Reporting it as an open failure and still counting
  it in the change fail rate keeps the bad news in exactly one place where it cannot be diluted.

## E6 - overlapping incidents

- What the log contains: eleven pairs of incidents whose intervals intersect. Most of the overlap comes from
  the open incident of E5, whose interval runs to the end of the window and therefore meets every incident
  opened after it.
- What a default definition would have done: merge overlapping incidents into one, or add their durations up
  and call the total "downtime", double counting wall-clock that was only lived through once.
- Why the rule is defensible: recovery is a property of a deployment, not of an incident, so a failed
  deployment takes the resolution of its own covering incident and nothing is summed. E5 also shows why
  merging is the worse of the two errors: one incident nobody closed would swallow every other incident in
  the window and produce a single enormous "outage" that never happened.
