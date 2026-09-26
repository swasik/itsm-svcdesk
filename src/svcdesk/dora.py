# ai-generated: 100% - Claude Opus 5 wrote this file from design/LAB2.md section 3; the lecturer ran the tests
"""The DORA metric engine of Lab 2 (design/LAB2.md section 3).

Standard library only, on purpose: Tier B stage 2 imports this module as a library to compute the
withheld expected values, and stage 2 must run without FastAPI, pydantic or any student code. The
HTTP layer in `app.py` is the only caller that knows about the web.

Every rule id below (R-01 .. R-21) is published to students in `student-package/lab2/METRIC-SPEC.md`;
this module is the executable form of exactly those rules and of nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

SPEC_VERSION = "1.0.0"
PRODUCTION = "production"
MAIN_BRANCH = "main"
SECONDS_PER_DAY = 86400
RATIO_PLACES = Decimal("0.000001")          # R-03: six decimal places
EVENT_TYPES = ("commit", "deployment", "incident")
OUTCOMES = ("success", "failure")
PHASES = ("opened", "resolved")
MAX_ID = 64


class DoraError(ValueError):
    """A malformed request or a malformed log (design/LAB2.md 1.2 and 4.1). The HTTP layer maps this to 400."""


# ---------------------------------------------------------------------------- parsing


def parse_instant(text: object, where: str) -> datetime:
    """RFC 3339 with an offset, compared as an instant and normalised to UTC (R-03)."""
    if not isinstance(text, str) or not text:
        raise DoraError(f"{where}: expected an RFC 3339 instant, got {_short(text)}")
    candidate = text.strip()
    if candidate.endswith(("z", "Z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise DoraError(f"{where}: not an RFC 3339 instant: {text!r}") from exc
    if parsed.tzinfo is None:
        raise DoraError(f"{where}: instant has no UTC offset: {text!r}")
    return parsed.astimezone(timezone.utc)


def _short(value: object, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _require_id(value: object, where: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_ID:
        raise DoraError(f"{where}: expected a string of 1..{MAX_ID} characters, got {_short(value)}")
    return value


def _require_bool(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise DoraError(f"{where}: expected true or false, got {_short(value)}")
    return value


def _optional_id(value: object, where: str) -> str | None:
    if value is None:
        return None
    return _require_id(value, where)


@dataclass(frozen=True)
class Commit:
    event_id: str
    at: datetime
    sha: str
    branch: str
    change_id: str | None
    reverts: str | None


@dataclass(frozen=True)
class Deployment:
    event_id: str
    at: datetime
    deployment_id: str
    environment: str
    outcome: str
    commits: tuple[str, ...]
    unplanned: bool
    caused_by: str | None


@dataclass(frozen=True)
class IncidentEvent:
    event_id: str
    at: datetime
    incident_id: str
    phase: str
    deployments: tuple[str, ...]


@dataclass
class Incident:
    incident_id: str
    opened_at: datetime | None = None
    resolved_at: datetime | None = None
    deployments: set[str] = field(default_factory=set)


@dataclass
class Log:
    commits: dict[str, Commit]                  # by sha
    deployments: dict[str, Deployment]          # by deployment_id
    incidents: dict[str, Incident]              # by incident_id
    change_of: dict[str, str]                   # sha -> resolved change_id (R-06)
    revert_commits: int                         # commits with a non-null `reverts` (R-06)


def parse_log(raw_events: object) -> Log:
    """Validate and index an event list (design/LAB2.md 1.1, 1.2). Raises DoraError on anything malformed."""
    if not isinstance(raw_events, list):
        raise DoraError("events: expected an array")

    seen: set[str] = set()
    commits: dict[str, Commit] = {}
    deployments: dict[str, Deployment] = {}
    incident_events: list[IncidentEvent] = []

    for index, raw in enumerate(raw_events):
        where = f"events[{index}]"
        if not isinstance(raw, dict):
            raise DoraError(f"{where}: expected an object, got {_short(raw)}")
        event_id = _require_id(raw.get("event_id"), f"{where}.event_id")
        if event_id in seen:          # R-05: the first occurrence wins, later ones are not an error
            continue
        seen.add(event_id)
        kind = raw.get("type")
        if kind not in EVENT_TYPES:
            raise DoraError(f"{where}.type: expected one of {', '.join(EVENT_TYPES)}, got {_short(kind)}")
        at = parse_instant(raw.get("at"), f"{where}.at")
        if kind == "commit":
            commit = _parse_commit(raw, at, event_id, where)
            if commit.sha in commits:
                raise DoraError(f"{where}.sha: {commit.sha!r} is used by more than one commit")
            commits[commit.sha] = commit
        elif kind == "deployment":
            deployment = _parse_deployment(raw, at, event_id, where)
            if deployment.deployment_id in deployments:
                raise DoraError(f"{where}.deployment_id: {deployment.deployment_id!r} is used more than once")
            deployments[deployment.deployment_id] = deployment
        else:
            incident_events.append(_parse_incident(raw, at, event_id, where))

    incidents = _fold_incidents(incident_events)
    _check_references(commits, deployments, incidents)
    change_of = resolve_changes(commits)
    revert_commits = sum(1 for commit in commits.values() if commit.reverts is not None)
    return Log(commits=commits, deployments=deployments, incidents=incidents,
               change_of=change_of, revert_commits=revert_commits)


def _parse_commit(raw: dict, at: datetime, event_id: str, where: str) -> Commit:
    sha = _require_id(raw.get("sha"), f"{where}.sha")
    branch = raw.get("branch")
    if not isinstance(branch, str) or not branch:
        raise DoraError(f"{where}.branch: expected a non-empty string, got {_short(branch)}")
    change_id = _optional_id(raw.get("change_id"), f"{where}.change_id")
    reverts = _optional_id(raw.get("reverts"), f"{where}.reverts")
    # design/LAB2.md 1.2: a commit carries a change_id exactly when it is not a revert
    if reverts is None and change_id is None:
        raise DoraError(f"{where}: a commit that reverts nothing must carry a change_id")
    if reverts is not None and change_id is not None:
        raise DoraError(f"{where}: a revert commit must not carry a change_id of its own (R-06)")
    if reverts is not None and reverts == sha:
        raise DoraError(f"{where}.reverts: a commit cannot revert itself")
    return Commit(event_id=event_id, at=at, sha=sha, branch=branch, change_id=change_id, reverts=reverts)


def _parse_deployment(raw: dict, at: datetime, event_id: str, where: str) -> Deployment:
    deployment_id = _require_id(raw.get("deployment_id"), f"{where}.deployment_id")
    environment = raw.get("environment")
    if not isinstance(environment, str) or not environment:
        raise DoraError(f"{where}.environment: expected a non-empty string, got {_short(environment)}")
    outcome = raw.get("outcome")
    if outcome not in OUTCOMES:
        raise DoraError(f"{where}.outcome: expected one of {', '.join(OUTCOMES)}, got {_short(outcome)}")
    raw_commits = raw.get("commits")
    if not isinstance(raw_commits, list):
        raise DoraError(f"{where}.commits: expected an array, got {_short(raw_commits)}")
    shas = tuple(_require_id(sha, f"{where}.commits[{i}]") for i, sha in enumerate(raw_commits))
    return Deployment(event_id=event_id, at=at, deployment_id=deployment_id, environment=environment,
                      outcome=outcome, commits=shas,
                      unplanned=_require_bool(raw.get("unplanned"), f"{where}.unplanned"),
                      caused_by=_optional_id(raw.get("caused_by"), f"{where}.caused_by"))


def _parse_incident(raw: dict, at: datetime, event_id: str, where: str) -> IncidentEvent:
    phase = raw.get("phase")
    if phase not in PHASES:
        raise DoraError(f"{where}.phase: expected one of {', '.join(PHASES)}, got {_short(phase)}")
    raw_deployments = raw.get("deployments")
    if not isinstance(raw_deployments, list):
        raise DoraError(f"{where}.deployments: expected an array, got {_short(raw_deployments)}")
    return IncidentEvent(
        event_id=event_id, at=at,
        incident_id=_require_id(raw.get("incident_id"), f"{where}.incident_id"), phase=phase,
        deployments=tuple(_require_id(d, f"{where}.deployments[{i}]") for i, d in enumerate(raw_deployments)),
    )


def _fold_incidents(events: list[IncidentEvent]) -> dict[str, Incident]:
    incidents: dict[str, Incident] = {}
    for event in events:
        incident = incidents.setdefault(event.incident_id, Incident(incident_id=event.incident_id))
        if event.phase == "opened":
            if incident.opened_at is not None:
                raise DoraError(f"incident {event.incident_id!r}: opened more than once")
            incident.opened_at = event.at
        else:
            if incident.resolved_at is not None:
                raise DoraError(f"incident {event.incident_id!r}: resolved more than once")
            incident.resolved_at = event.at
        incident.deployments.update(event.deployments)
    for incident in incidents.values():
        if incident.opened_at is None:
            raise DoraError(f"incident {incident.incident_id!r}: resolved without ever being opened")
    return incidents


def _check_references(commits: dict[str, Commit], deployments: dict[str, Deployment],
                      incidents: dict[str, Incident]) -> None:
    for commit in commits.values():
        if commit.reverts is not None and commit.reverts not in commits:
            raise DoraError(f"commit {commit.sha!r}: reverts {commit.reverts!r}, which is not in the log")
    for deployment in deployments.values():
        for sha in deployment.commits:
            if sha not in commits:
                raise DoraError(f"deployment {deployment.deployment_id!r}: carries commit {sha!r}, "
                                "which is not in the log")
        if deployment.caused_by is not None and deployment.caused_by not in incidents:
            raise DoraError(f"deployment {deployment.deployment_id!r}: caused_by {deployment.caused_by!r}, "
                            "which is not in the log")
    for incident in incidents.values():
        for deployment_id in sorted(incident.deployments):
            if deployment_id not in deployments:
                raise DoraError(f"incident {incident.incident_id!r}: names deployment {deployment_id!r}, "
                                "which is not in the log")


def resolve_changes(commits: dict[str, Commit]) -> dict[str, str]:
    """R-06: a revert commit inherits, transitively, the change of the commit it reverts."""
    resolved: dict[str, str] = {}

    def walk(sha: str, seen: tuple[str, ...]) -> str:
        if sha in resolved:
            return resolved[sha]
        if sha in seen:
            raise DoraError("revert cycle: " + " -> ".join((*seen, sha)))
        commit = commits[sha]
        if commit.reverts is None:
            assert commit.change_id is not None       # guaranteed by _parse_commit
            answer = commit.change_id
        else:
            answer = walk(commit.reverts, (*seen, sha))
        resolved[sha] = answer
        return answer

    for sha in commits:
        walk(sha, ())
    return resolved


# ---------------------------------------------------------------------------- arithmetic


def round_seconds(value: float) -> int:
    """R-03: whole seconds, half-up."""
    return int(Decimal(repr(float(value))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_ratio(value: float) -> float:
    """R-03: six decimal places, half-up."""
    return float(Decimal(repr(float(value))).quantize(RATIO_PLACES, rounding=ROUND_HALF_UP))


def median_seconds(values: list[float]) -> int | None:
    """R-04 over durations, then R-03 rounding. No values -> None."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return round_seconds(ordered[middle])
    return round_seconds((ordered[middle - 1] + ordered[middle]) / 2)


def _elapsed(later: datetime, earlier: datetime) -> tuple[float, bool]:
    """Seconds between two instants; R-03 clamps a negative result to zero and says it was clamped."""
    seconds = (later - earlier).total_seconds()
    return (0.0, True) if seconds < 0 else (seconds, False)


# ---------------------------------------------------------------------------- the metrics


def compute(raw_events: object, window_from: datetime, window_to: datetime) -> dict:
    """The metric object of design/LAB2.md 4.1. `window_to` must be strictly after `window_from` (R-02)."""
    if window_to <= window_from:
        raise DoraError("window: `to` must be strictly after `from`")
    log = parse_log(raw_events)
    return compute_from_log(log, window_from, window_to)


def compute_from_log(log: Log, window_from: datetime, window_to: datetime) -> dict:
    in_window = [d for d in log.deployments.values()
                 if d.environment == PRODUCTION and window_from <= d.at < window_to]   # R-01, R-02
    in_window.sort(key=lambda d: (d.at, d.deployment_id))
    successful = [d for d in in_window if d.outcome == "success"]
    failed = [d for d in in_window if d.outcome == "failure"]

    lead_pairs, negative_pairs = _lead_times(successful, log)                            # R-08, E1
    recovery_times, open_failures = _recovery_times(failed, log)                         # R-12, E5
    window_days = (window_to - window_from).total_seconds() / SECONDS_PER_DAY

    deployments = len(in_window)
    rework = [d for d in in_window if d.unplanned and d.caused_by is not None]           # R-15
    delivered, true_lead_times = _ground_truth(successful, log)                          # R-16, R-17

    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": _iso(window_from), "to": _iso(window_to)},
        "deployment_frequency_per_day": round_ratio(deployments / window_days),          # R-11
        "change_lead_time_seconds_p50": median_seconds(lead_pairs),                      # R-08
        "failed_deployment_recovery_time_seconds_p50": median_seconds(recovery_times),   # R-12
        "change_fail_rate": _ratio(len(failed), deployments),                            # R-14
        "deployment_rework_rate": _ratio(len(rework), deployments),                      # R-15
        "counts": {
            "deployments": deployments,
            "successful_deployments": len(successful),
            "failed_deployments": len(failed),
            "recovered_failures": len(recovery_times),
            "open_failures": open_failures,
            "rework_deployments": len(rework),
            "lead_time_pairs": len(lead_pairs),
            "changes": len(set(log.change_of.values())),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,                                  # E1
            "deployments_without_commits": sum(1 for d in in_window if not d.commits),   # E4
            "commits_never_on_main": _commits_never_on_main(in_window, log),             # E3
            "revert_chains_collapsed": log.revert_commits,                               # E2
            "overlapping_incident_pairs": _overlapping_pairs(log, window_to),            # E6
        },
        "ground_truth": {
            "changes_delivered": delivered,                                              # R-16
            "true_change_lead_time_seconds_p50": median_seconds(true_lead_times),        # R-17
        },
    }


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round_ratio(numerator / denominator)


def _lead_times(successful: list[Deployment], log: Log) -> tuple[list[float], int]:
    """R-08: one pair per sha, at its first successful production deployment in the window.

    R-09 (E3): the branch is never consulted. R-10 (E4): an empty `commits` contributes nothing.
    """
    pairs: list[float] = []
    negative = 0
    paired: set[str] = set()
    for deployment in successful:                       # already sorted by (at, deployment_id)
        for sha in deployment.commits:
            if sha in paired:
                continue
            paired.add(sha)
            seconds, clamped = _elapsed(deployment.at, log.commits[sha].at)
            negative += 1 if clamped else 0             # E1: clamped to zero and counted, never discarded
            pairs.append(seconds)
    return pairs, negative


def _recovery_times(failed: list[Deployment], log: Log) -> tuple[list[float], int]:
    """R-12: per failed deployment, from its covering incident. R-13 (E6): never per incident, never summed."""
    times: list[float] = []
    open_failures = 0
    for deployment in failed:
        covering = _covering_incident(deployment.deployment_id, log)
        if covering is None or covering.resolved_at is None:
            open_failures += 1                          # E5
            continue
        seconds, _ = _elapsed(covering.resolved_at, deployment.at)
        times.append(seconds)
    return times, open_failures


def _covering_incident(deployment_id: str, log: Log) -> Incident | None:
    """R-12: the incident covering this deployment whose `opened` is earliest; ties by incident id."""
    candidates = [i for i in log.incidents.values() if deployment_id in i.deployments]
    if not candidates:
        return None
    return min(candidates, key=lambda i: (i.opened_at, i.incident_id))


def _commits_never_on_main(in_window: list[Deployment], log: Log) -> int:
    """E3: distinct shas carried by a production deployment in the window whose commit is not on `main`."""
    shas = {sha for d in in_window for sha in d.commits}
    return sum(1 for sha in shas if log.commits[sha].branch != MAIN_BRANCH)


def _overlapping_pairs(log: Log, window_to: datetime) -> int:
    """R-13 (E6): unordered pairs of incidents whose [opened, resolved) intervals intersect.

    An incident that never resolved runs to the window's end.
    """
    intervals = sorted(
        (incident.opened_at, incident.resolved_at or window_to) for incident in log.incidents.values()
    )
    overlapping = 0
    for index, (start, end) in enumerate(intervals):
        for other_start, other_end in intervals[index + 1:]:
            if other_start >= end:      # sorted by start: nothing later can intersect either
                break
            if start < other_end:
                overlapping += 1
    return overlapping


def _ground_truth(successful: list[Deployment], log: Log) -> tuple[int, list[float]]:
    """R-16 and R-17: per change, not per (deployment, commit) pair, and from the change's earliest commit."""
    first_commit_at: dict[str, datetime] = {}
    for sha, change_id in log.change_of.items():
        at = log.commits[sha].at
        if change_id not in first_commit_at or at < first_commit_at[change_id]:
            first_commit_at[change_id] = at                                              # R-07

    first_delivery: dict[str, datetime] = {}
    for deployment in successful:
        for sha in deployment.commits:
            change_id = log.change_of[sha]
            if change_id not in first_delivery or deployment.at < first_delivery[change_id]:
                first_delivery[change_id] = deployment.at

    lead_times = [_elapsed(delivered_at, first_commit_at[change_id])[0]
                  for change_id, delivered_at in first_delivery.items()]
    return len(first_delivery), lead_times
