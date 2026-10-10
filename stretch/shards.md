<!-- ai-generated: 30% - Claude Code ran the commands and drafted the prose with me; the query results are Prometheus's as printed -->
# Stretch 4 - shard per core (D-24)

A throwaway ring (project `itsm-lab7-shards`, `RING_NET=172.28.71`, `RING_CQL_PORT=19042`), my own ring stopped
meanwhile, started with `stretch/shards/compose.override.yml`: `n3` with `--smp 2`, `n1` and `n2` with `--smp 1`,
and `prom/prometheus:v3.15.0` on the ring's network scraping `n1:9180`, `n2:9180`, `n3:9180` (all three targets
`up`). The node with two shards is **n3** (`172.28.71.13`). Removed afterwards with `down -v`.

```
$ curl -s -G http://127.0.0.1:9091/api/v1/query --data-urlencode 'query=group by (instance, shard) (scylla_reactor_utilization)'
{"metric":{"instance":"n1:9180","shard":"0"},"value":"1"}
{"metric":{"instance":"n3:9180","shard":"0"},"value":"1"}
{"metric":{"instance":"n3:9180","shard":"1"},"value":"1"}
{"metric":{"instance":"n2:9180","shard":"0"},"value":"1"}
$ curl -s -G http://127.0.0.1:9091/api/v1/query --data-urlencode 'query=scylla_memory_total_memory'
{"metric":{"instance":"n1:9180","shard":"0"},"value":"1021313024"}
{"metric":{"instance":"n3:9180","shard":"0"},"value":"484442112"}
{"metric":{"instance":"n3:9180","shard":"1"},"value":"484442112"}
{"metric":{"instance":"n2:9180","shard":"0"},"value":"1021313024"}
```

What I read in it: `group by (instance, shard) (scylla_reactor_utilization)` has one series per (node, shard)
pair - `n1:9180` and `n2:9180` with `shard="0"` only, `n3:9180` with `shard="0"` and `shard="1"`. Every metric of
ScyllaDB is per shard because a shard is a whole engine of its own: its own core, its own memory, its own slice
of the data, no locks shared with the other shard. `scylla_memory_total_memory` shows the memory half of it:
`--memory 1G` is the node's total, so `n1`'s single shard has 1,021,313,024 bytes and each of `n3`'s two shards
484,442,112 - together 968,884,224, exactly 50 MiB (52,428,800 bytes) less than one shard gets: the second
engine has its own overhead. A query that sums a metric over a node has to sum over `shard`; a dashboard that shows one series per node
silently drops a shard.
