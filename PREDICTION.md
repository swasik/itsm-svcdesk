---
feature: GET /dora/ticket-events, the lifecycle stream Lab 7 consumes
predicted_minutes: 45
predicted_at: 2026-09-26T09:40:00Z
feature_path: src/svcdesk/ticketevents.py
---
<!-- ai-generated: 0% - the lecturer wrote this prediction before the first commit of the feature -->

# Prediction

Forty-five minutes to write `GET /dora/ticket-events` and its tests: the data is already in the ticket
row, so this is a projection and an ordering, not a computation. The risk is the `in_progress` question -
Lab 1 stores no timestamp for it, so either the phase is dropped or the model changes. I expect to drop it
and say so in the contract.

This file was receipted through the submissions repository before the feature's first commit; the grader
checks that ordering against the receipt, not against any date in this file.
