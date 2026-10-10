---
lab7_ai_draft:
  source: ai
  tool: "Ollama 0.35.0 (ollama/ollama:0.35.0 in Docker on my laptop), model qwen3:1.7b (digest 8f68893c685c), /api/chat with default options, 2026-10-11"
  verdict: refuted
  slice: practice
  slice_sha256: fd55ad9aaebfb382484d237f4bd49165ab0fcc35b466052f3db4cd7bb586c901
  scylla_yaml_sha256: 5806b13274cf2500f400e389d3280996e4797d7a83131a08925d5a6522f92766
  buckets: {events_by_repo: 1, events_by_actor: 1}
  reason: "CREATE KEYSPACE gh refused: SyntaxException line 1:24 no viable alternative at input 'REPLICATION_FACTOR'; then every CREATE TABLE refused: Can't find a keyspace gh"
lab7_stress:
  image: scylladb/cassandra-stress:3.21.1
  command: "write n=60000 cl=QUORUM -schema replication(strategy=NetworkTopologyStrategy,replication_factor=3) -rate threads=32 fixed=2000/s -node 172.28.70.11 -mode native cql3"
  op_rate: 2000
  p99_ms: 0.6
  p999_ms: 1.9
  max_ms: 5.0
---
<!-- ai-generated: 35% - Claude Code ran the ring commands with me and drafted parts of the prose; the transcripts are the database's output as printed, the keys and the arithmetic are mine -->

# Lab 7 evidence

## AI draft

The draft is the first answer of `qwen3:1.7b`, run locally in Ollama 0.35.0, to `ai/PROMPT.md` as its first and only
message (149 s on the CPU; the model "thought" for about 7,800 characters before answering, and its answer was CQL
only, without a code block and without any prose around it, so there is no prose to quote). It proposes a keyspace
`gh` with an invented syntax, `WITH REPLICATION_FACTOR 3 AND NETWORK_TOPOLOGY_STRATEGY 'NetworkTopologyStrategy'
('datacenter1' 'three_nodes')`, and three tables. `events_by_repo` and `events_by_actor` are identical: every
vocabulary column, including `bucket` (without a `-- buckets:` comment, so B = 1), and `PRIMARY KEY (event_id, day,
hour, minute)` - the partition key is `event_id`, one partition per event. `events_by_ticket` has the six ticket
columns and the same key, `(ticket_id, day, hour, minute)`, naming `hour` and `minute`, which that table does not
have.

What the database said, applying the file as written (`dc exec -T n1 cqlsh < db/ai-model-proposal.cql`):

```
<stdin>:2:SyntaxException: line 1:24 no viable alternative at input 'REPLICATION_FACTOR'
<stdin>:16:InvalidRequest: Error from server: code=2200 [Invalid query] message="Can't find a keyspace gh"
<stdin>:30:InvalidRequest: Error from server: code=2200 [Invalid query] message="Can't find a keyspace gh"
<stdin>:40:InvalidRequest: Error from server: code=2200 [Invalid query] message="Can't find a keyspace gh"
$ ./itsmlab.sh load 7 --keyspace-from db/ai-model-proposal.cql
itsmlab: loading the tables of ai-model-proposal.cql at 172.28.70.11:9042, 172.28.70.12:9042, 172.28.70.13:9042 with the practice slice (66249 events); B for a bucket column from nowhere: 1
gh.events_by_repo: does not exist on your ring (apply ai-model-proposal.cql first, or use --schema)
gh.events_by_actor: does not exist on your ring (apply ai-model-proposal.cql first, or use --schema)
gh.events_by_ticket: does not exist on your ring (apply ai-model-proposal.cql first, or use --schema)
$ ./itsmlab.sh guardrails 7 --keyspace gh
No table in gh
```

**Verdict: refuted** - the ring refused the draft's first statement, and with no keyspace every `CREATE TABLE`
after it. Nothing was loaded, so nothing could be convicted.

Would D-05's bounds have changed it? Not the verdict, and I checked what the draft would have done past the syntax
error: on my ring I created a scratch keyspace `aifix` with a correct `NetworkTopologyStrategy` RF 3 clause and
applied the draft's three tables to it unchanged (keyspace name only). `events_by_ticket` was refused again
(`Unknown definition hour referenced in PRIMARY KEY`); the other two loaded all 66,249 events and, flushed, were
not convicted on any node - a partition per event is one row, and no bound of D-05 can make it bigger. But the
query cannot be served: `SELECT event_id FROM aifix.events_by_actor WHERE actor = 'github-actions[bot]' AND
created_at >= ...` was refused with `Cannot execute this query as it might involve data filtering ... use ALLOW
FILTERING`. The draft avoids the hot partition by not having partitions anyone can ask for: it answers the
database's large-data judge and fails the query-first rule. I kept nothing of its keys; I kept the idea that
`event_id` belongs in every key, as the tie-breaker, not as the partition key. I dropped `aifix` afterwards.

## Guardrails

The instructor's schema on my ring, the practice slice loaded with `./itsmlab.sh load 7 --keyspace-from
db/instructor-hot-partition.cql` (66,249 rows into each table), then read before and after flushing every node:

```
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT keyspace_name, table_name, partition_key, rows, partition_size FROM system.large_partitions WHERE keyspace_name = 'instructor' AND table_name = 'events_by_actor';"

 keyspace_name | table_name | partition_key | rows | partition_size
---------------+------------+---------------+------+----------------


(0 rows)
$ docker compose -f ring/compose.yml exec n1 nodetool flush instructor
$ docker compose -f ring/compose.yml exec n2 nodetool flush instructor
$ docker compose -f ring/compose.yml exec n3 nodetool flush instructor
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT keyspace_name, table_name, partition_key, rows, partition_size FROM system.large_partitions WHERE keyspace_name = 'instructor' AND table_name = 'events_by_actor';"

 keyspace_name | table_name      | partition_key       | rows  | partition_size
---------------+-----------------+---------------------+-------+----------------
    instructor | events_by_actor | github-actions[bot] | 10792 |         713133

(1 rows)
$ docker compose -f ring/compose.yml exec n2 cqlsh -e "SELECT keyspace_name, table_name, partition_key, rows, partition_size FROM system.large_partitions WHERE keyspace_name = 'instructor' AND table_name = 'events_by_actor';"

 keyspace_name | table_name      | partition_key       | rows  | partition_size
---------------+-----------------+---------------------+-------+----------------
    instructor | events_by_actor | github-actions[bot] | 10792 |         713133

(1 rows)
$ docker compose -f ring/compose.yml exec n3 cqlsh -e "SELECT keyspace_name, table_name, partition_key, rows, partition_size FROM system.large_partitions WHERE keyspace_name = 'instructor' AND table_name = 'events_by_actor';"

 keyspace_name | table_name      | partition_key       | rows  | partition_size
---------------+-----------------+---------------------+-------+----------------
    instructor | events_by_actor | github-actions[bot] | 10792 |         713133

(1 rows)
```

Before the flush the same query answered `(0 rows)`: the 66,249 rows were still in the memtables, and the
large-data records are written into an SSTable's metadata when the SSTable is written, so there was nothing to
read yet. After `nodetool flush instructor` on all three nodes every node lists the partition, because with RF 3 on
three nodes each node holds a full replica and judges only its own SSTables. The 10,792 rows are exactly
`github-actions[bot]`'s events in the slice (`itsmlab slice 7` printed the same number): one partition per actor
puts every event of the bot in one partition, ten times the 1,000-row threshold, in 713,133 bytes (about 66 bytes a
row, so this partition is convicted for rows, not yet for size).

## Model

The queries came first (`db/model.yaml`):

```
repo_events:   SELECT event_id FROM gh.events_by_repo  WHERE repo = :repo   AND day = :day AND bucket IN :buckets AND created_at >= :from_ts AND created_at < :to_ts
actor_events:  SELECT event_id FROM gh.events_by_actor WHERE actor = :actor AND day = :day AND bucket IN :buckets AND created_at >= :from_ts AND created_at < :to_ts
ticket_events: SELECT at, phase FROM gh.events_by_ticket WHERE ticket_id = :ticket_id
```

**Keys.** `events_by_actor` is `PRIMARY KEY ((actor, day, bucket), created_at, event_id)`: the `WHERE` names every
partition-key column - `actor` and `day` with `=`, `bucket` with `IN` over all B values - so the coordinator knows
exactly which B partitions to read, and `created_at` is the first clustering column, so the half-open window
`[from_ts, to_ts)` is a slice of each partition's sorted rows: no `ALLOW FILTERING`. `event_id` is the last
clustering column because many events share a second (21 of the bot's in the first two seconds of the slice), and
without it they would overwrite each other. `events_by_repo` is the same with `repo` in place of `actor`.
`events_by_ticket` is `PRIMARY KEY ((ticket_id), at, phase)`: one partition per ticket; `at` alone is not unique,
because my `svcdesk` stamps `created`, `acknowledged` and `resolved` with the same second when they come quickly
(my own ticket did: three events, all at 22:57:01), so `phase` is in the key too. `ticket_id` is `text`: my ids are
UUID strings, and `text` takes any id the stream sends.

**Buckets, against D-05, not against the practice slice.** My rule: B is the smallest number that keeps the
*average* bucket at D-05's bound at or below 500 rows, half the 1,000-row threshold, so that a bucket would need
twice its share to be convicted. With `bucket = event_id mod B` an actor's n events fall into B buckets as a
binomial: average n / B, standard deviation sqrt(n x (1/B) x (1 - 1/B)).

- `events_by_actor`: 12,000 events of one actor / B = 24 is 500 rows per bucket, standard deviation about 22. To
  reach 1,001 rows a bucket would have to be 500 rows - about 23 standard deviations - above its average. B = 12
  (average 1,000) would convict about half the buckets; B = 16 (750, sd 27) passes on paper with 9 sd, but on the
  practice slice the largest of 20 buckets was 11 % above its average (600 against 540), more than the binomial
  predicts, so the event ids are not perfectly uniform mod B; I want room for that. At 24 even a bucket 50 % over
  its average is 750 rows.
- `events_by_repo`: 1,500 events of one repository / B = 3 is 500 rows per bucket, sd about 18; B = 1 would be a
  1,500-row partition (convicted), B = 2 750 (sd 19; passes, with less room).
- Measured on the practice slice (the bot's 10,792 events, the largest repository's 521): with B = 24 the bot's
  buckets hold 412 to 485 rows (average 450); with B = 3 the repository's hold 154 to 192. After loading and flushing
  every node, `./itsmlab.sh guardrails 7` printed `0 record(s)` on n1, n2 and n3 and `convicted: none`.
- Size: the instructor's partition was 713,133 bytes for 10,792 rows, about 66 bytes a row; my rows carry one more
  short column (`org`), so a 500-row bucket is a few tens of KB, far from the 1 MB partition threshold. Rows, not
  bytes, are the binding limit.

**What `day` does and does not do.** Every event of a slice has the same UTC day, so `day` divides nothing inside a
window: without the bucket, the bot's 12,000 events would still be one partition. What `day` bounds is growth over
time: a real table keeps every day, and without `day` an actor's partition would grow for as long as the actor
exists. The bucket bounds the window; the day bounds the calendar.

**What a bucket costs the reader.** `bucket IN :buckets` reads 24 partitions to answer one actor's window (3 for a
repository), and at RF 3 each of them can live on another node: more coordinator work and more requests than a
single-partition read. That is why I stopped at the smallest B my rule allows rather than taking 32 or 100.

**`events_by_ticket` needs no bucket.** A ticket has at most four phases (`created`, `acknowledged`, `resolved`,
`closed`), so its partition holds at most four rows, plus one more pair per reopen; nothing D-05 bounds makes a
ticket's partition grow, so the arithmetic is 4 against 1,000.

| table | partition key | clustering columns | B | rows per partition at D-05's bound | against 1,000 |
|---|---|---|---|---|---|
| `events_by_repo` | `(repo, day, bucket)` | `created_at, event_id` | 3 | 1,500 / 3 = 500, sd about 18 | 500 rows of margin, about 27 sd |
| `events_by_actor` | `(actor, day, bucket)` | `created_at, event_id` | 24 | 12,000 / 24 = 500, sd about 22 | 500 rows of margin, about 23 sd |
| `events_by_ticket` | `(ticket_id)` | `at, phase` | - | at most 4 (one per phase) | far below |

## CAP

My `actor_events` with values in place of the markers (B = 24, the bot, the first two seconds of the slice), all
three nodes up beforehand; the commands in order, each with its output as it came (stderr included):

```
$ docker compose -f ring/compose.yml stop n2 n3
 Container itsm-lab7-n3-1 Stopping 
 Container itsm-lab7-n2-1 Stopping 
 Container itsm-lab7-n3-1 Stopped 
 Container itsm-lab7-n2-1 Stopped 
$ docker compose -f ring/compose.yml exec n1 nodetool status
Datacenter: datacenter1
=======================
Status=Up/Down/eXcluded
|/ State=Normal/Leaving/Joining/Moving
-- Address      Load     Tokens Owns Host ID                              Rack 
UN 172.28.70.11 14.55 MB 256    ?    c65d016a-dadf-4c3a-ad39-0c4323220612 rack1
DN 172.28.70.12 14.58 MB 256    ?    3ccf6ff2-c228-4740-824a-4e774c9dc688 rack1
DN 172.28.70.13 14.57 MB 256    ?    3fe97c89-68f1-4118-82fc-f2e0bb3c084b rack1

Note: Non-system keyspaces don't have the same replication settings, effective ownership information is meaningless
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "CONSISTENCY ONE; SELECT event_id FROM gh.events_by_actor WHERE actor = 'github-actions[bot]' AND day = '2025-01-15' AND bucket IN (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23) AND created_at >= '2025-01-15 15:00:00+0000' AND created_at < '2025-01-15 15:00:02+0000';"
Consistency level set to ONE.

 event_id
-------------
 45588038448
 45588038808
 45588038284
 45588038670
 45588038096
 45588039128
 45588038097
 45588038818
 45588038220
 45588039013
 45588038655
 45588038776
 45588038824
 45588038153
 45588039065
 45588038682
 45588039114
 45588038155
 45588038539
 45588038325
 45588038902

(21 rows)
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "CONSISTENCY QUORUM; SELECT event_id FROM gh.events_by_actor WHERE actor = 'github-actions[bot]' AND day = '2025-01-15' AND bucket IN (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23) AND created_at >= '2025-01-15 15:00:00+0000' AND created_at < '2025-01-15 15:00:02+0000';"
<stdin>:1:NoHostAvailable: ('Unable to complete the operation against any hosts', {<Host: 172.28.70.11:9042 datacenter1>: Unavailable('Error from server: code=1000 [Unavailable exception] message="Cannot achieve consistency level for cl QUORUM. Requires 2, alive 1" info={\'consistency\': \'QUORUM\', \'required_replicas\': 2, \'alive_replicas\': 1}')})
Consistency level set to QUORUM.
$ docker compose -f ring/compose.yml exec n1 cqlsh --request-timeout=90 -e "CREATE TABLE gh.cap_probe (pk int PRIMARY KEY);"
<stdin>:1:NoHostAvailable: ('Unable to complete the operation against any hosts', {<Host: 172.28.70.11:9042 datacenter1>: <Error from server: code=0000 [Server error] message="group [f8aa5070-c4fc-11f1-b800-ec0d42e7ef62] raft operation [read_barrier] timed out, there is no raft quorum, total voters count 3, alive voters count 1, dead voters [3ccf6ff2-c228-4740-824a-4e774c9dc688,3fe97c89-68f1-4118-82fc-f2e0bb3c084b]">})
$ docker compose -f ring/compose.yml start n2 n3
 Container itsm-lab7-n1-1 Waiting 
 Container itsm-lab7-n1-1 Waiting 
 Container itsm-lab7-n1-1 Healthy 
 Container itsm-lab7-n2-1 Starting 
 Container itsm-lab7-n1-1 Healthy 
 Container itsm-lab7-n3-1 Starting 
 Container itsm-lab7-n3-1 Started 
 Container itsm-lab7-n2-1 Started 
$ docker compose -f ring/compose.yml exec n1 nodetool status
Datacenter: datacenter1
=======================
Status=Up/Down/eXcluded
|/ State=Normal/Leaving/Joining/Moving
-- Address      Load     Tokens Owns Host ID                              Rack 
UN 172.28.70.11 14.55 MB 256    ?    c65d016a-dadf-4c3a-ad39-0c4323220612 rack1
UN 172.28.70.12 14.58 MB 256    ?    3ccf6ff2-c228-4740-824a-4e774c9dc688 rack1
UN 172.28.70.13 14.57 MB 256    ?    3fe97c89-68f1-4118-82fc-f2e0bb3c084b rack1

Note: Non-system keyspaces don't have the same replication settings, effective ownership information is meaningless
```

Timings measured around each command: the read at `ONE` 0.6 s, the refusal at `QUORUM` 0.6 s (cqlsh's own start-up
included), the `CREATE TABLE` 60.6 s, `start n2 n3` 0.7 s, three `UN` five seconds later.

**Why `ONE` served and `QUORUM` did not.** Every partition of `gh` has three replicas, one on each node, and only
`n1` was alive. `ONE` needs one replica to answer, and `n1` holds one: it returned the 21 events, from its own
replica, with no way to know whether `n2` or `n3` had accepted a newer write meanwhile. `QUORUM` needs a majority
of the three replicas, 2; the coordinator knows from gossip that only 1 is alive, so it refuses before reading
anything - `Requires 2, alive 1`, in well under a second. That is the CAP choice per request: `ONE` chose
availability, `QUORUM` chose consistency and refused.

**Why the schema change waited a minute.** A `CREATE TABLE` is not a data write with a consistency level: schema
changes go through Raft group 0, and before changing the schema `n1` runs a read barrier, which needs a majority of
the three group-0 voters (2) to confirm it has the latest schema state. Only one voter was alive, so it waited for
another to come back, and after 60 s (the group-0 operation timeout) gave up with `there is no raft quorum, total
voters count 3, alive voters count 1`, naming the two dead voters by host id. With `--request-timeout=90` the client
outwaited the server, so the message is the database's, not cqlsh's `OperationTimedOut`. The table was not created.

**Data plane and control plane.** The data plane is tunable per request: with one node of three it can still serve
reads at `ONE` (stale-possible) and refuse at `QUORUM`. The control plane is not tunable: membership and schema
always need a Raft majority, so with two nodes down the ring cannot change its own shape at any consistency level,
even though it still answers some reads. A ring that "is up" for a reader at `ONE` may be frozen for everything an
operator does.

## Stress

All three nodes up, `cassandra-stress` as a sibling container on the ring's network:

```
$ docker run --rm --network itsm-lab7_ring scylladb/cassandra-stress:3.21.1 write n=60000 cl=QUORUM -schema "replication(strategy=NetworkTopologyStrategy,replication_factor=3)" -rate threads=32 fixed=2000/s -node 172.28.70.11 -mode native cql3
Results:
Op rate                   :    2,000 op/s  [WRITE: 2,000 op/s]
Partition rate            :    2,000 pk/s  [WRITE: 2,000 pk/s]
Row rate                  :    2,000 row/s [WRITE: 2,000 row/s]
Latency mean              :    0.3 ms [WRITE: 0.3 ms]
Latency median            :    0.3 ms [WRITE: 0.3 ms]
Latency 95th percentile   :    0.4 ms [WRITE: 0.4 ms]
Latency 99th percentile   :    0.6 ms [WRITE: 0.6 ms]
Latency 99.9th percentile :    1.9 ms [WRITE: 1.9 ms]
Latency max               :    5.0 ms [WRITE: 5.0 ms]
```

(The run took 39 s from `docker run` to exit: keyspace creation, 15,000 warm-up writes, then 30 s of measured
writes - `Total operation time : 00:00:29`, `Total errors : 0`.)

**Why p99 and max differ.** The p99 says 99 % of the 60,000 writes finished within 0.6 ms; the p99.9 that 60 writes
took longer than 1.9 ms; the max that the single slowest took 5.0 ms, eight times the p99. The per-second lines show
where: second 4 had its max at 5.0 ms and p99.9 3.4 ms, seconds 12, 15 and 18 had maxima of 4.1 to 4.5 ms, while
most seconds stayed under 2.5 ms. A median of 0.3 ms is one network round trip inside Docker's bridge plus a
memtable insert on two replicas; the few slow writes waited for something else - a memtable flush or a commitlog
segment switch on one of the two replicas the quorum needed, the reactor of a 1-core, overprovisioned node yielding
to the other containers on this laptop (Labs 4 and 5 were running beside the ring, load average about 3.5 on 22
cores), or the client's own thread or JVM pause. With `cl=QUORUM` the coordinator waits for the second-fastest of
three replicas, so one slow replica alone does not delay a write, but two do.

**What `fixed=2000/s` changed.** With a fixed rate the tool schedules each write at its intended instant and
measures latency from that instant, not from when a thread got round to sending it; a stall therefore shows up in
every write queued behind it, not only in the one that stalled. Without `fixed=` (the default, or `throttle=`) a
stall also stops the senders, the writes behind it start late and are timed as if nothing happened - coordinated
omission, which flatters the p99 and the max. The op rate of 2,000 op/s is exactly the fixed rate, so the ring
kept up and the percentiles are not inflated by a backlog. And `cl=QUORUM` on replication factor 3 asks, for every
write, that 2 of the 3 replicas acknowledge it before the client hears "done", which is what makes a later `QUORUM`
read see it; the tool's defaults (RF 1, `LOCAL_ONE`) would have measured one replica and no redundancy at all.
