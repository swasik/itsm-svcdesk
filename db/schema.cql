-- ai-generated: 20% - Claude Code wrote the CQL from my key and bucket choices; the keys and the arithmetic are mine (EVIDENCE.md, ## Model)
-- Lab 7 model (DATA-SPEC.md D-03, D-06 to D-11). Query-first: each table answers exactly one query of db/model.yaml.
--
-- Bucket rule: B is the smallest number that keeps the AVERAGE bucket at D-05's bound at or below half the
-- 1,000-row threshold, so that a bucket would need twice its share to be convicted.
--   events_by_actor: 12,000 events of one actor / 24 = 500 rows per bucket on average (sd about 22)
--   events_by_repo:   1,500 events of one repository / 3 = 500 rows per bucket on average (sd about 18)
-- event_id is bigint: bucket = event_id mod B, and it is the tie-breaker that keeps two events of the same second apart.

CREATE KEYSPACE IF NOT EXISTS gh
  WITH replication = {'class': 'NetworkTopologyStrategy', 'replication_factor': 3};

-- repo_events: WHERE repo = :repo AND day = :day AND bucket IN :buckets AND created_at >= :from_ts AND created_at < :to_ts
CREATE TABLE IF NOT EXISTS gh.events_by_repo (
  repo text,
  day date,
  bucket int,
  created_at timestamp,
  event_id bigint,
  type text,
  actor text,
  org text,
  PRIMARY KEY ((repo, day, bucket), created_at, event_id)
) WITH CLUSTERING ORDER BY (created_at ASC, event_id ASC);

-- actor_events: WHERE actor = :actor AND day = :day AND bucket IN :buckets AND created_at >= :from_ts AND created_at < :to_ts
CREATE TABLE IF NOT EXISTS gh.events_by_actor (
  actor text,
  day date,
  bucket int,
  created_at timestamp,
  event_id bigint,
  type text,
  repo text,
  org text,
  PRIMARY KEY ((actor, day, bucket), created_at, event_id)
) WITH CLUSTERING ORDER BY (created_at ASC, event_id ASC);

-- ticket_events: WHERE ticket_id = :ticket_id. At most four events per ticket (created, acknowledged, resolved,
-- closed), so one partition per ticket holds at most four rows: no bucket. (at, phase) keeps two phases of the same
-- instant apart (a ticket acknowledged at the instant it was created).
CREATE TABLE IF NOT EXISTS gh.events_by_ticket (
  ticket_id text,
  at timestamp,
  phase text,
  priority text,
  state text,
  day date,
  PRIMARY KEY ((ticket_id), at, phase)
) WITH CLUSTERING ORDER BY (at ASC, phase ASC);
