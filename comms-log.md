---
lab4_comms:
  awareness: 2026-10-11T08:00:30Z
  detection: 2026-10-11T07:58:38Z
  classification: 2026-10-11T09:00:00Z
  nis2:
    early_warning_due: 2026-10-12T08:00:30Z       # awareness + 24 h
    notification_due: 2026-10-14T08:00:30Z        # awareness + 72 h
    notification_sent: 2026-10-12T09:00:00Z
    final_report_due: 2026-11-12T09:00:00Z        # one calendar month after notification_sent
  ksc:
    early_warning_due: 2026-10-12T07:58:38Z       # detection + 24 h
    notification_due: 2026-10-14T07:58:38Z        # detection + 72 h
    notification_sent: 2026-10-12T09:00:00Z
    final_report_due: 2026-11-12T09:00:00Z        # one calendar month after notification_sent
  dora:
    initial_due: 2026-10-11T13:00:00Z             # classification + 4 h, earlier than awareness + 24 h
    initial_sent: 2026-10-11T12:00:00Z
    intermediate_due: 2026-10-14T12:00:00Z        # initial_sent + 72 h
    intermediate_sent: 2026-10-13T09:00:00Z
    final_due: 2026-11-13T09:00:00Z               # one calendar month after intermediate_sent
  log:
    - {at: 2026-10-11T12:00:00Z, to: the financial supervisor, what: DORA initial notification}
    - {at: 2026-10-11T12:30:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-10-12T09:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-13T09:00:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) acting as the student chose the instants and computed the deadlines -->

# Communications log: the regulators' clocks

The shop is assumed to fall under NIS2, the Polish KSC act and DORA, with this incident significant under the first
two and major under the third. Every instant is UTC.

## The three instants we defend

- **Detection (KSC), 2026-10-11T07:58:38Z.** KSC counts "od momentu jego wykrycia", from the moment of detection.
  The first alert that fired after the onset, ServiceLatencyRaised on product-catalog, started at 07:58:38; that is
  the detection `itsmlab incident 4` recomputes, and the earliest instant our systems knew something was wrong - its
  chat message went out at 07:58:48, a minute before the page.
- **Awareness (NIS2), 2026-10-11T08:00:30Z.** NIS2 counts from becoming aware of a *significant* incident. At
  07:59:57 the on-call had acknowledged the P1; by 08:00:04 the symptom queries showed failed orders (17.9 % of
  checkout's requests over five minutes), 15-second product pages across the shop, and three failing flags; by
  08:00:30 the first flag was off and the effect of the fault on every customer was clear. That is when the incident
  was known to be significant, not merely an alert.
- **Classification (DORA), 2026-10-11T09:00:00Z.** The classification as major needs the counts of affected clients
  and transactions and the duration, which the morning's analysis of the snapshot gave (60 orders, 3 failed, 27
  product pages failed, every page slow for nine minutes). Classified within 24 hours of awareness, so the initial
  report is due at the earlier of classification + 4 h (13:00Z) and awareness + 24 h (08:00:30Z on 12 October):
  13:00Z on 11 October.

## The log

| when (UTC) | to | what | which clock |
|---|---|---|---|
| 2026-10-11 12:00 | the financial supervisor | DORA initial notification | due 13:00Z on 11 October |
| 2026-10-11 12:30 | the CSIRT | early warning | NIS2 (due 12 October 08:00:30Z) and KSC (due 12 October 07:58:38Z) |
| 2026-10-12 09:00 | the CSIRT | incident notification | NIS2 (due 14 October 08:00:30Z) and KSC (due 14 October 07:58:38Z); final reports due 12 November 09:00Z |
| 2026-10-13 09:00 | the financial supervisor | DORA intermediate report | due 14 October 12:00Z; final report due 13 November 09:00Z |
