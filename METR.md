---
actual_minutes: 62
---
<!-- ai-generated: 0% - the lecturer wrote this reflection after the feature was finished -->

# n=1 METR replication

Predicted 45 minutes, actual 62 minutes. Ratio actual/predicted = **1.38**.

METR's 2025 randomised controlled trial found experienced open-source developers were 19 % *slower* with AI
assistance on their own mature repositories while believing themselves about 20 % faster. This is one
observation, not a replication of that result: n=1, no control, no randomisation, and the person measuring
is the person predicting. What it can do is put a number on the gap between the estimate and the clock,
which is the part of the METR finding that transfers.

Where the seventeen minutes went is the interesting part, and it is not where the prediction assumed. The
projection itself took about ten minutes. The ordering key took another five. The remaining time went on
the `in_progress` question the prediction had already flagged as the risk: deciding that a stream may only
carry instants the service actually holds, writing that down in the endpoint contract so Lab 7 can rely on
it, and then fixing the two tests that had assumed a five-phase stream. The estimate was wrong about the
size of the work it had already identified as uncertain, which is the ordinary shape of an underestimate.

The direction of this result carries no marks either way. Had the ratio come out at 0.72 the lab would score
the same, because what is graded is that the prediction was made first, in public, and measured honestly
afterwards. That is the anti-Goodhart rule of the course applied to its own measurement exercise: a number
that is rewarded for pointing one way stops being a measurement.
