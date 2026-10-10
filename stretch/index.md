<!-- ai-generated: 30% - Claude Code ran the commands and drafted the prose with me; the transcripts are the ring's output as printed -->
# Stretch 3 - a secondary index is a materialized view (D-23)

My keyspace `gh` (D-03: tablets, RF 3) refuses an index on the one-rack ring:

```
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "CREATE INDEX x_idx ON gh.events_by_repo (type);"
<stdin>:1:InvalidRequest: Error from server: code=2200 [Invalid query] message="Materialized views and secondary indexes are not supported on the keyspace 'gh': The keyspace 'gh' is required to be RF-rack-valid. That condition is violated for DC 'datacenter1': RF=3 vs. rack count=1."
```

So `stretch/index.cql` creates `gh_vnodes` with `tablets = {'enabled': false}`, a copy of `gh.events_by_repo`
(same columns, types and key `((repo, day, bucket), created_at, event_id)`) and an index on `type`.
`system_schema.views` before and after, and the view's columns:

```
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT keyspace_name, view_name, base_table_name FROM system_schema.views;"

 keyspace_name | view_name | base_table_name
---------------+-----------+-----------------


(0 rows)
$ docker compose -f ring/compose.yml exec -T n1 cqlsh < stretch/index.cql
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT keyspace_name, view_name, base_table_name FROM system_schema.views;"

 keyspace_name | view_name                     | base_table_name
---------------+-------------------------------+-----------------
     gh_vnodes | events_by_repo_type_idx_index |  events_by_repo

(1 rows)
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT column_name, kind, position, type FROM system_schema.columns WHERE keyspace_name = 'gh_vnodes' AND table_name = 'events_by_repo_type_idx_index';"

 column_name | kind          | position | type
-------------+---------------+----------+-----------
      bucket |    clustering |        3 |       int
  created_at |    clustering |        4 | timestamp
         day |    clustering |        2 |      date
    event_id |    clustering |        5 |    bigint
   idx_token |    clustering |        0 |    bigint
        repo |    clustering |        1 |      text
        type | partition_key |        0 |      text

(7 rows)
```

The index is a table: `events_by_repo_type_idx_index`, partitioned by the indexed column `type`, with an
`idx_token` and then my whole primary key as clustering columns. That means the index has its own partition key,
and it is the worst one I could have picked: the practice slice has 15 event types for 66,249 events. I loaded the
practice slice into the copy (`./itsmlab.sh load 7 --keyspace-from stretch/index.cql`, B = 3 from the
`-- buckets: 3` comment) and flushed every node:

```
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT keyspace_name, table_name, partition_key, rows, partition_size FROM system.large_partitions WHERE keyspace_name = 'gh_vnodes' AND table_name = 'events_by_repo_type_idx_index';"

 keyspace_name | table_name                    | partition_key                 | rows  | partition_size
---------------+-------------------------------+-------------------------------+-------+----------------
     gh_vnodes | events_by_repo_type_idx_index |                     PushEvent | 40387 |        2696844
     gh_vnodes | events_by_repo_type_idx_index |                   CreateEvent |  7662 |         534316
     gh_vnodes | events_by_repo_type_idx_index |              PullRequestEvent |  4703 |         319333
     gh_vnodes | events_by_repo_type_idx_index |             IssueCommentEvent |  3024 |         197674
     gh_vnodes | events_by_repo_type_idx_index |                    WatchEvent |  2611 |         167785
     gh_vnodes | events_by_repo_type_idx_index |        PullRequestReviewEvent |  1943 |         127815
     gh_vnodes | events_by_repo_type_idx_index |                   DeleteEvent |  1842 |         124589
     gh_vnodes | events_by_repo_type_idx_index |                   IssuesEvent |  1182 |          76794
     gh_vnodes | events_by_repo_type_idx_index | PullRequestReviewCommentEvent |  1179 |          76157

(9 rows)
```

The base table, bucketed to at most 192 rows per partition on this slice, is not recorded anywhere; its index's
view is convicted with nine partitions, `PushEvent` at 40,387 rows and 2.7 MB - over both the row and the size
threshold. The hot partition I designed away came back through a table I never created: an index on a
low-cardinality column is a partition per value. (An index on `actor` would do the same with `github-actions[bot]`.)

One more thing the run showed: `./itsmlab.sh guardrails 7 --keyspace gh_vnodes` flushed the three nodes and printed
`convicted: none` and `0 record(s)` per node, although the same `SELECT` on `n2` (flushed only by that command)
lists the view's nine rows - the tool reads the keyspace's tables, not its views. Read `system.large_partitions`
by hand for a view.
