-- ai-generated: 20% - started from the course's index.example.cql; the table copy, the indexed column and the reasoning are mine
-- Stretch 3 (DATA-SPEC.md D-23): a secondary index is a materialized view. My keyspace gh (D-03: tablets, RF 3)
-- refuses an index on the one-rack ring (not RF-rack-valid), so the index goes on a copy of gh.events_by_repo in a
-- keyspace with tablets disabled. The indexed column is `type`: about fifteen distinct values for 66,249 events, so
-- the index's view - partitioned by `type` - puts thousands of rows into one partition (stretch/index.md).

CREATE KEYSPACE IF NOT EXISTS gh_vnodes
  WITH replication = {'class': 'NetworkTopologyStrategy', 'replication_factor': 3}
  AND tablets = {'enabled': false};

-- the copy of gh.events_by_repo: the same columns, types and key (db/schema.cql)
-- buckets: 3
CREATE TABLE IF NOT EXISTS gh_vnodes.events_by_repo (
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

-- the index on type: its view is gh_vnodes.events_by_repo_type_idx_index
CREATE INDEX IF NOT EXISTS events_by_repo_type_idx ON gh_vnodes.events_by_repo (type);
