# ai-generated: 100% - Claude Opus 5 wrote this file from design/LAB2.md sections 3 and 11; the lecturer ran it
"""Worked examples for the Lab 2 metric engine (design/LAB2.md section 11).

Every number asserted here is computed by hand in `grader/lab2/EXAMPLES.md`. These examples are the
published side of the lab: they are rules, not data, so nothing here is withheld from students.
"""

from __future__ import annotations

import pytest

from svcdesk.dora import DoraError, compute, parse_instant

WFROM = parse_instant("2026-09-01T00:00:00Z", "from")
WTO = parse_instant("2026-09-08T00:00:00Z", "to")           # 7.0 days
DAY = 86400


def commit(event_id, sha, at, change_id="CHG-1", branch="main", reverts=None):
    return {"event_id": event_id, "type": "commit", "at": at, "sha": sha, "branch": branch,
            "change_id": change_id, "reverts": reverts}


def deployment(event_id, deployment_id, at, commits=(), outcome="success", environment="production",
               unplanned=False, caused_by=None):
    return {"event_id": event_id, "type": "deployment", "at": at, "deployment_id": deployment_id,
            "environment": environment, "outcome": outcome, "commits": list(commits),
            "unplanned": unplanned, "caused_by": caused_by}


def incident(event_id, incident_id, at, phase, deployments=()):
    return {"event_id": event_id, "type": "incident", "at": at, "incident_id": incident_id,
            "phase": phase, "deployments": list(deployments)}


def run(events, window_from=WFROM, window_to=WTO):
    return compute(events, window_from, window_to)


# --------------------------------------------------------------- A: the five metrics on a happy log


EXAMPLE_A = [
    commit("c1", "s1", "2026-09-01T00:00:00Z", "CHG-1"),
    commit("c2", "s2", "2026-09-02T00:00:00Z", "CHG-2"),
    deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1", "s2"]),
]


def test_example_a_five_metrics():
    result = run(EXAMPLE_A)
    assert result["spec_version"] == "1.0.0"
    assert result["deployment_frequency_per_day"] == 0.142857          # R-11: 1 / 7 days
    assert result["change_lead_time_seconds_p50"] == 129600            # R-04: mean of 86400 and 172800
    assert result["failed_deployment_recovery_time_seconds_p50"] is None
    assert result["change_fail_rate"] == 0.0
    assert result["deployment_rework_rate"] == 0.0
    assert result["counts"] == {"deployments": 1, "successful_deployments": 1, "failed_deployments": 0,
                                "recovered_failures": 0, "open_failures": 0, "rework_deployments": 0,
                                "lead_time_pairs": 2, "changes": 2}
    assert result["ground_truth"] == {"changes_delivered": 2, "true_change_lead_time_seconds_p50": 129600}
    assert result["window"] == {"from": "2026-09-01T00:00:00Z", "to": "2026-09-08T00:00:00Z"}


def test_example_a_is_order_independent_and_idempotent():
    """Checks 2.05 and 2.06: reversing the log and duplicating every event change nothing (R-05)."""
    baseline = run(EXAMPLE_A)
    assert run(list(reversed(EXAMPLE_A))) == baseline
    assert run([*EXAMPLE_A, *EXAMPLE_A]) == baseline


# --------------------------------------------------------------- B: E1, clock skew


def test_example_b_negative_lead_time_is_clamped_and_counted():
    """E1 / R-08: a commit timestamped after its deployment gives 0, is counted, and is never dropped."""
    result = run([
        commit("c1", "s1", "2026-09-03T00:10:00Z", "CHG-1"),       # ten minutes after the deployment
        commit("c2", "s2", "2026-09-01T00:00:00Z", "CHG-2"),
        deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1", "s2"]),
    ])
    assert result["anomalies"]["negative_lead_time_pairs"] == 1
    assert result["counts"]["lead_time_pairs"] == 2                # clamped, not discarded
    assert result["change_lead_time_seconds_p50"] == 86400         # mean of 0 and 172800
    assert result["ground_truth"]["true_change_lead_time_seconds_p50"] == 86400


# --------------------------------------------------------------- C: E2, a revert of a revert


def test_example_c_revert_of_a_revert_is_one_change():
    """E2 / R-06: three commits, one change; both reverts are counted as collapsed."""
    result = run([
        commit("c1", "s1", "2026-09-01T00:00:00Z", "CHG-1"),
        commit("c2", "s2", "2026-09-02T00:00:00Z", change_id=None, reverts="s1"),
        commit("c3", "s3", "2026-09-02T12:00:00Z", change_id=None, reverts="s2"),
        deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1", "s2", "s3"]),
    ])
    assert result["counts"]["changes"] == 1
    assert result["anomalies"]["revert_chains_collapsed"] == 2
    assert result["counts"]["lead_time_pairs"] == 3                # still three commits deployed
    assert result["ground_truth"]["changes_delivered"] == 1
    # R-07: the change's first commit is s1, so its true lead time is two full days
    assert result["ground_truth"]["true_change_lead_time_seconds_p50"] == 2 * DAY


def test_revert_cycle_is_rejected():
    with pytest.raises(DoraError, match="revert cycle"):
        run([
            commit("c1", "s1", "2026-09-01T00:00:00Z", change_id=None, reverts="s2"),
            commit("c2", "s2", "2026-09-01T01:00:00Z", change_id=None, reverts="s1"),
        ])


# --------------------------------------------------------------- D: E3, a hotfix that never touched main


def test_example_d_branch_is_never_consulted():
    """E3 / R-09: the hotfix contributes a lead-time pair and is counted as off-main."""
    result = run([
        commit("c1", "s1", "2026-09-02T00:00:00Z", "CHG-1", branch="hotfix/pager"),
        deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1"]),
    ])
    assert result["counts"]["lead_time_pairs"] == 1
    assert result["change_lead_time_seconds_p50"] == DAY
    assert result["anomalies"]["commits_never_on_main"] == 1
    assert result["ground_truth"]["changes_delivered"] == 1


def test_off_main_counts_failed_deployments_too():
    """R-09: `commits_never_on_main` looks at every production deployment, successful or not."""
    result = run([
        commit("c1", "s1", "2026-09-02T00:00:00Z", "CHG-1", branch="hotfix/pager"),
        deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1"], outcome="failure"),
    ])
    assert result["anomalies"]["commits_never_on_main"] == 1
    assert result["counts"]["lead_time_pairs"] == 0                # R-08: failures deliver nothing


# --------------------------------------------------------------- E: E4, a deployment with no commits


def test_example_e_deployment_without_commits():
    """E4 / R-10: it counts as a deployment everywhere and contributes no pair."""
    result = run([deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", [])])
    assert result["counts"]["deployments"] == 1
    assert result["counts"]["lead_time_pairs"] == 0
    assert result["change_lead_time_seconds_p50"] is None
    assert result["anomalies"]["deployments_without_commits"] == 1
    assert result["deployment_frequency_per_day"] == 0.142857
    assert result["change_fail_rate"] == 0.0
    assert result["ground_truth"] == {"changes_delivered": 0, "true_change_lead_time_seconds_p50": None}


# --------------------------------------------------------------- F: E5 and E6


EXAMPLE_F = [
    deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", [], outcome="failure"),
    deployment("d2", "DEP-2", "2026-09-02T01:00:00Z", [], outcome="failure"),
    incident("i1", "INC-1", "2026-09-02T00:10:00Z", "opened", ["DEP-1"]),
    incident("i2", "INC-1", "2026-09-02T02:10:00Z", "resolved", ["DEP-1"]),
    incident("i3", "INC-2", "2026-09-02T01:05:00Z", "opened", ["DEP-2"]),   # never resolved
]


def test_example_f_open_failure_and_overlapping_incidents():
    """E5 / R-12 and E6 / R-13."""
    result = run(EXAMPLE_F)
    assert result["counts"]["failed_deployments"] == 2
    assert result["counts"]["recovered_failures"] == 1
    assert result["counts"]["open_failures"] == 1                  # E5: excluded from the median
    assert result["failed_deployment_recovery_time_seconds_p50"] == 7800      # 2 h 10 min, DEP-1 only
    assert result["change_fail_rate"] == 1.0                       # E5: still counted here
    assert result["anomalies"]["overlapping_incident_pairs"] == 1  # E6: INC-2 runs to the window end


def test_overlap_is_not_merged_and_not_summed():
    """E6 / R-13: one incident covering two failed deployments gives both the same recovery instant."""
    result = run([
        deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", [], outcome="failure"),
        deployment("d2", "DEP-2", "2026-09-02T00:30:00Z", [], outcome="failure"),
        incident("i1", "INC-1", "2026-09-02T00:05:00Z", "opened", ["DEP-1", "DEP-2"]),
        incident("i2", "INC-1", "2026-09-02T01:00:00Z", "resolved", ["DEP-1", "DEP-2"]),
    ])
    # 3600 s and 1800 s, median 2700 - never 5400, which is what summing would give
    assert result["failed_deployment_recovery_time_seconds_p50"] == 2700
    assert result["anomalies"]["overlapping_incident_pairs"] == 0


def test_covering_incident_is_the_earliest_opened():
    """R-12: two incidents cover one deployment; the earlier-opened one supplies the recovery instant."""
    result = run([
        deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", [], outcome="failure"),
        incident("i1", "INC-1", "2026-09-02T00:10:00Z", "opened", ["DEP-1"]),
        incident("i2", "INC-1", "2026-09-02T01:00:00Z", "resolved", ["DEP-1"]),
        incident("i3", "INC-2", "2026-09-02T00:20:00Z", "opened", ["DEP-1"]),
        incident("i4", "INC-2", "2026-09-02T03:00:00Z", "resolved", ["DEP-1"]),
    ])
    assert result["failed_deployment_recovery_time_seconds_p50"] == 3600


def test_recovery_after_the_window_still_counts():
    """R-02: incidents are never filtered by the window; only deployments are."""
    result = run([
        deployment("d1", "DEP-1", "2026-09-07T23:00:00Z", [], outcome="failure"),
        incident("i1", "INC-1", "2026-09-07T23:10:00Z", "opened", ["DEP-1"]),
        incident("i2", "INC-1", "2026-09-09T23:00:00Z", "resolved", ["DEP-1"]),   # after `to`
    ])
    assert result["counts"]["recovered_failures"] == 1
    assert result["failed_deployment_recovery_time_seconds_p50"] == 2 * DAY


# --------------------------------------------------------------- scope, window, rework


def test_non_production_is_ignored_entirely():
    """R-01."""
    result = run([
        commit("c1", "s1", "2026-09-01T00:00:00Z", "CHG-1"),
        deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1"], environment="staging"),
    ])
    assert result["counts"] == {"deployments": 0, "successful_deployments": 0, "failed_deployments": 0,
                                "recovered_failures": 0, "open_failures": 0, "rework_deployments": 0,
                                "lead_time_pairs": 0, "changes": 1}
    assert result["deployment_frequency_per_day"] == 0.0
    assert result["change_fail_rate"] is None                       # R-14: no deployments, no ratio
    assert result["ground_truth"]["changes_delivered"] == 0


def test_window_is_half_open():
    """R-02: `from` is inside, `to` is outside."""
    at_from = run([deployment("d1", "DEP-1", "2026-09-01T00:00:00Z", [])])
    at_to = run([deployment("d1", "DEP-1", "2026-09-08T00:00:00Z", [])])
    assert at_from["counts"]["deployments"] == 1
    assert at_to["counts"]["deployments"] == 0


def test_a_commit_is_paired_at_its_first_successful_deployment_only():
    """R-08: a redeployed commit contributes one pair, measured at the earlier deployment."""
    result = run([
        commit("c1", "s1", "2026-09-01T00:00:00Z", "CHG-1"),
        deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", ["s1"]),
        deployment("d2", "DEP-2", "2026-09-05T00:00:00Z", ["s1"]),
    ])
    assert result["counts"]["lead_time_pairs"] == 1
    assert result["change_lead_time_seconds_p50"] == DAY
    assert result["ground_truth"]["true_change_lead_time_seconds_p50"] == DAY


def test_rework_needs_both_unplanned_and_an_incident():
    """R-15: `unplanned` alone is not rework; the deployment must answer an incident."""
    events = [
        deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", [], unplanned=True),                  # no incident
        deployment("d2", "DEP-2", "2026-09-02T02:00:00Z", [], unplanned=True, caused_by="INC-1"),
        deployment("d3", "DEP-3", "2026-09-02T04:00:00Z", []),
        incident("i1", "INC-1", "2026-09-02T01:00:00Z", "opened", []),
        incident("i2", "INC-1", "2026-09-02T01:30:00Z", "resolved", []),
    ]
    result = run(events)
    assert result["counts"]["rework_deployments"] == 1
    assert result["deployment_rework_rate"] == round(1 / 3, 6)


def test_a_failed_rework_deployment_is_counted_by_both_instability_metrics():
    """R-15: the overlap between change fail rate and rework rate is by design."""
    result = run([
        deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", [], outcome="failure",
                   unplanned=True, caused_by="INC-1"),
        incident("i1", "INC-1", "2026-09-02T00:00:00Z", "opened", []),
        incident("i2", "INC-1", "2026-09-02T00:30:00Z", "resolved", []),
    ])
    assert result["change_fail_rate"] == 1.0
    assert result["deployment_rework_rate"] == 1.0


# --------------------------------------------------------------- malformed input (checks 2.08 to 2.11)


@pytest.mark.parametrize("events, message", [
    ("not a list", "expected an array"),
    ([{"event_id": "x", "type": "nope", "at": "2026-09-01T00:00:00Z"}], "type"),
    ([{"event_id": "x", "type": "commit", "at": "yesterday"}], "RFC 3339"),
    ([{"event_id": "x", "type": "commit", "at": "2026-09-01T00:00:00", "sha": "s", "branch": "main",
       "change_id": "C", "reverts": None}], "no UTC offset"),
    ([commit("c1", "s1", "2026-09-01T00:00:00Z", change_id=None, reverts="nope")], "not in the log"),
    ([commit("c1", "s1", "2026-09-01T00:00:00Z", change_id="C", reverts="s2")], "must not carry a change_id"),
    ([{"event_id": "c1", "type": "commit", "at": "2026-09-01T00:00:00Z", "sha": "s1", "branch": "main",
       "change_id": None, "reverts": None}], "must carry a change_id"),
    ([deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", ["ghost"])], "not in the log"),
    ([deployment("d1", "DEP-1", "2026-09-02T00:00:00Z", [], caused_by="INC-9")], "not in the log"),
    ([incident("i1", "INC-1", "2026-09-02T00:00:00Z", "resolved", [])], "without ever being opened"),
    ([incident("i1", "INC-1", "2026-09-02T00:00:00Z", "opened", ["DEP-9"])], "not in the log"),
])
def test_malformed_logs_are_rejected(events, message):
    with pytest.raises(DoraError, match=message):
        run(events)


def test_window_must_be_non_empty():
    with pytest.raises(DoraError, match="strictly after"):
        run([], window_from=WTO, window_to=WTO)


def test_duplicate_sha_is_rejected():
    with pytest.raises(DoraError, match="more than one commit"):
        run([commit("c1", "s1", "2026-09-01T00:00:00Z", "CHG-1"),
             commit("c2", "s1", "2026-09-01T01:00:00Z", "CHG-2")])


def test_duplicate_event_id_keeps_the_first_occurrence():
    """R-05: the second occurrence is ignored, and it is not an error even when it disagrees."""
    result = run([
        commit("c1", "s1", "2026-09-01T00:00:00Z", "CHG-1"),
        commit("c1", "s9", "2026-09-04T00:00:00Z", "CHG-9"),       # same event_id, different content
        deployment("d1", "DEP-1", "2026-09-03T00:00:00Z", ["s1"]),
    ])
    assert result["counts"]["changes"] == 1
    assert result["change_lead_time_seconds_p50"] == 2 * DAY
