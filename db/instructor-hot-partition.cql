-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from design/LAB7.md D-14; the lecturer reviews it
-- The course's hot-partition schema (DATA-SPEC.md D-14): the obvious model of GitHub's events - one partition per
-- repository, one per actor. The database convicts events_by_actor on every slice:
-- one bot account, github-actions[bot], writes more than 1,000 events in every 15-minute window.
-- Without AI, copy this file to db/ai-model-proposal.cql as your draft (D-15, source: instructor).
CREATE KEYSPACE IF NOT EXISTS instructor
  WITH replication = {'class': 'NetworkTopologyStrategy', 'replication_factor': 3};

CREATE TABLE IF NOT EXISTS instructor.events_by_repo (
  repo text,
  created_at timestamp,
  event_id text,
  type text,
  actor text,
  PRIMARY KEY (repo, created_at, event_id)
) WITH CLUSTERING ORDER BY (created_at DESC, event_id ASC);

CREATE TABLE IF NOT EXISTS instructor.events_by_actor (
  actor text,
  created_at timestamp,
  event_id text,
  type text,
  repo text,
  PRIMARY KEY (actor, created_at, event_id)
) WITH CLUSTERING ORDER BY (created_at DESC, event_id ASC);
