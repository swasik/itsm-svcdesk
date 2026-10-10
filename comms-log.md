---
lab4_comms:
  awareness: 2026-10-10T23:12:00Z
  detection: 2026-10-10T23:11:08Z
  classification: 2026-10-11T08:00:00Z
  nis2:
    early_warning_due: 2026-10-11T23:12:00Z       # awareness + 24 h
    notification_due: 2026-10-13T23:12:00Z        # awareness + 72 h
    notification_sent: 2026-10-12T09:00:00Z
    final_report_due: 2026-11-12T09:00:00Z        # one calendar month after notification_sent
  ksc:
    early_warning_due: 2026-10-11T23:11:08Z       # detection + 24 h
    notification_due: 2026-10-13T23:11:08Z        # detection + 72 h
    notification_sent: 2026-10-12T09:00:00Z
    final_report_due: 2026-11-12T09:00:00Z        # one calendar month after notification_sent
  dora:
    initial_due: 2026-10-11T12:00:00Z             # classification + 4 h, earlier than awareness + 24 h
    initial_sent: 2026-10-11T10:30:00Z
    intermediate_due: 2026-10-14T10:30:00Z        # initial_sent + 72 h
    intermediate_sent: 2026-10-13T09:00:00Z
    final_due: 2026-11-13T09:00:00Z               # one calendar month after intermediate_sent
  log:
    - {at: 2026-10-11T09:00:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-10-11T10:30:00Z, to: the financial supervisor, what: DORA initial notification}
    - {at: 2026-10-12T09:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-13T09:00:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) acting as the student chose the instants and computed the deadlines -->

# Communications log: the regulators' clocks

The shop is assumed to fall under NIS2, the Polish KSC act and DORA, with this incident significant under the first
two and major under the third. Every instant is UTC.

## The three instants we defend

- **Detection (KSC), 2026-10-10T23:11:08Z.** KSC counts "od momentu jego wykrycia", from the moment of detection.
  The first alert that fired after the onset, ServiceLatencyRaised, started at 23:11:08; that is the detection
  `itsmlab incident 4` recomputes, and the earliest instant our systems knew something was wrong.
- **Awareness (NIS2), 2026-10-10T23:12:00Z.** NIS2 counts from becoming aware of a *significant* incident. At
  23:11:25 the on-call had acknowledged the P1; by 23:12:00 the symptom queries showed failed orders (16 % of
  checkout's requests over five minutes) and broken product pages across the shop, and the flag state showed three
  failing flags: that is when the incident was known to be significant, not merely an alert.
- **Classification (DORA), 2026-10-11T08:00:00Z.** The classification as major needs the counts of affected
  clients and transactions and the duration, which the morning's analysis of the snapshot gave (50 orders, 4 failed,
  eight minutes). Classified within 24 hours of awareness, so the initial report is due at the earlier of
  classification + 4 h (12:00Z) and awareness + 24 h (23:12Z on 11 October): 12:00Z.

## The log

| when (UTC) | to | what | which clock |
|---|---|---|---|
| 2026-10-11 09:00 | the CSIRT | early warning | NIS2 (due 23:12Z) and KSC (due 23:11:08Z) on 11 October |
| 2026-10-11 10:30 | the financial supervisor | DORA initial notification | due 12:00Z on 11 October |
| 2026-10-12 09:00 | the CSIRT | incident notification | NIS2 (due 13 October 23:12Z) and KSC (due 13 October 23:11:08Z); final reports due 12 November 09:00Z |
| 2026-10-13 09:00 | the financial supervisor | DORA intermediate report | due 14 October 10:30Z; final report due 13 November 09:00Z |
