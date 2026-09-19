---
svcdesk_decisions:
  C1: wallclock    # wallclock | business
  C2: immutable    # reopen | immutable
  C3: vip          # matrix | vip
---
<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote the six candidate resolutions in make_decisions.py from design/LAB1.md section 2; this file is its output for C1=wallclock C2=immutable C3=vip -->

# Decisions

The requirements document contains three pairs of requirements that cannot both hold: R-13 and R-14 (which
clock the P1 targets run on), R-09 and R-10 (whether a closed ticket can be reopened) and R-05 and R-06
(whether a VIP reporter changes the priority). Each conflict is resolved by rejecting the minimal conflicting
part of one requirement and keeping everything else in the pair, so both sides of each pair are still
implemented and tested. The running service exhibits exactly the combination declared in the front matter:
`SVCDESK_C1`, `SVCDESK_C2` and `SVCDESK_C3` switch the service, and `python make_decisions.py C1 C2 C3`
regenerates this file so the declaration and the behaviour never disagree.

## C1 - SLA clock for P1

**Decision:** P1 acknowledgement (15 min) and resolution (4 h) run on the wall clock, around the clock; P2 to
P4 targets pause outside business hours (Monday to Friday, 08:00 to 16:00 Europe/Warsaw). The minimal
conflicting part of R-13, the words "any SLA target", is narrowed to "any P2 to P4 target"; the rest of R-13
and all of R-14 stand.

**Rejected alternative:** Every priority, including P1, pauses outside business hours, so that a P1 raised on
Friday at 17:00 is due for acknowledgement on Monday at 08:15 (R-14's "around the clock" rejected).

**Reason:** R-14 exists because a P1 means the whole organisation has stopped work. An SLA that lets a
Friday-evening outage wait until Monday measures nothing the customer cares about, and it makes the one target
with a pager behind it meaningless for 128 of the 168 hours in a week. Narrowing R-13 to P2 to P4 keeps its
purpose, which is not to penalise the desk for hours it is not staffed for routine work, while keeping the
single promise that justifies an on-call rota. It also matches how the desk is staffed: on-call covers P1
only, so a wall-clock target for P2 to P4 would generate breaches nobody is rostered to prevent.

**Service owner:** The Service Desk Manager, who owns the incident management practice, staffs the P1 on-call
rota and signs the SLA with the business; the Service Level Manager countersigns the target table.

**Customer outcome:** A P1 raised on Friday at 17:00 is acknowledged by 17:15 and worked until resolved; the
customer whose organisation has stopped is never told to wait for Monday. Customers with P2 to P4 issues get
the published business-hours targets, which are the ones the desk can actually staff and report on honestly.

## C2 - Closed tickets and reopening

**Decision:** A closed ticket is immutable. Reopen works from resolved only, within 7 days of resolved_at; a
reopen request on a closed ticket answers 409 whatever its age, and further work on the same issue is a new
ticket that references the closed one via related_to. The minimal conflicting part of R-10, the words "or
closed" and "or closure", is rejected; reopening a resolved ticket, the rest of R-10, stands together with all
of R-09.

**Rejected alternative:** Reopen allowed from closed as well, within 7 days of closed_at, with the record
becoming immutable only after that window.

**Reason:** Closure is the point where the record becomes evidence: it feeds SLA attainment reports, problem
records and the monthly service review, and a record that can silently change after that point makes every
report reproducible only by luck. The 7-day reopen window after resolution already gives the reporter the "the
fix did not work" path that R-10 is for; the resolved state exists precisely so that closure can wait until
the reporter has confirmed. A new ticket linked via related_to preserves the history of both records and gives
problem management a countable signal, how many closed tickets spawned follow-up work, instead of a mutated
one.

**Service owner:** The Incident Manager, process owner of incident management, who signs off the closure rules
because closure is what makes the incident record trustworthy for reporting and problem management.

**Customer outcome:** A reporter whose fix failed within a week reopens the resolved ticket without friction;
once the ticket is closed, the customer raises a linked ticket and the history of both is preserved, so the
reports the customer relies on (SLA attainment, recurring issues) stay true.

## C3 - VIP reporters and the priority matrix

**Decision:** After the matrix, a ticket whose reporter has vip = true and that landed on P3 or P4 is raised
to P2; P1 and P2 are unchanged. The minimal conflicting part of R-05, the words "from nothing else", is
narrowed to "from nothing the client sends as a priority": a priority field in the request is still ignored,
and neither reporter nor agent can request one. All of R-06 stands.

**Rejected alternative:** The matrix alone decides and reporter.vip is stored but ignored; VIP visibility is
handled by a queue filter on the flag (R-06's uplift rejected).

**Reason:** The purpose of R-05 is to stop reporters and agents negotiating priorities ticket by ticket. The
VIP flag is not such a negotiation: it is a standing decision by management about a small set of people whose
blocked work has an outsized business cost, and it is maintained by the desk, not chosen by the reporter.
Capping the uplift at P2 keeps P1 reserved for genuine organisation-wide impact, so the on-call rota is never
paged for an executive's cosmetic issue, while the ticket reaches the desk board within the hour, which is the
whole point of R-06.

**Service owner:** The Service Desk Manager, who owns the desk's queue policy and maintains the VIP list
together with the business relationship manager; the Service Level Manager is informed because P2 volumes
change.

**Customer outcome:** An executive's blocked laptop is seen within the hour instead of by the end of the day,
without displacing an organisation-wide outage; every other reporter keeps the published matrix and can see
exactly why a ticket has the priority it has.
