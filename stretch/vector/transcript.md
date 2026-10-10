<!-- ai-generated: 30% - Claude Code ran the commands and drafted the prose with me; the transcript is the ring's output as printed -->
# Stretch 1 - vector search beside the ring (D-21)

`stretch/vector/vector.cql` stores tickets of my `svcdesk` with a hand-made 4-dimensional embedding, one axis per
support topic: `[access/login, network/VPN, hardware, email]`. The question it answers is the one a desk agent asks
when a new ticket comes in: which earlier tickets look like this one? A new ticket "login fails over the VPN" is
`[0.8, 0.5, 0.0, 0.0]`.

Ring started with `docker compose -f ring/compose.yml -f stretch/vector/compose.override.yml up -d --wait`
(vector-store 1.11.0, about 28 s for the three nodes to restart), `vector.cql` applied with `exec -T n1 cqlsh`.

```
$ docker compose -f ring/compose.yml -f stretch/vector/compose.override.yml exec n1 curl -s http://vector-store:6080/api/v1/indexes
[{"keyspace":"vec","index":"ticket_vectors_embedding_idx","options":{"type":"vector","dimensions":4,"maximum_node_connections":16,"construction_beam_width":128,"search_beam_width":64,"similarity_function":"COSINE","quantization":"F32"},"status":"SERVING","count":6,"build_progress":100.0}]
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT ticket_id, title FROM vec.ticket_vectors ORDER BY embedding ANN OF [0.8, 0.5, 0.0, 0.0] LIMIT 3;"

 ticket_id | title
-----------+-----------------------------------
     T-105 |   Cannot log in to the VPN portal
     T-101 |  Locked out after password change
     T-106 | MFA prompt never arrives by email

(3 rows)
$ docker compose -f ring/compose.yml exec n1 cqlsh -e "SELECT ticket_id, title, priority FROM vec.ticket_vectors ORDER BY embedding ANN OF [0.1, 0.0, 0.0, 0.9] LIMIT 2;"

 ticket_id | title                             | priority
-----------+-----------------------------------+----------
     T-104 |         Mailbox full, cannot send |       P3
     T-106 | MFA prompt never arrives by email |       P2

(2 rows)
```

What I read in it:

- The cosine similarities by hand for the first query: T-105 `[0.7, 0.7, 0, 0]` 0.975, T-101 `[1, 0, 0, 0.1]` 0.844,
  T-106 `[0.8, 0, 0, 0.6]` 0.679, T-102 (VPN only) 0.612. The ring returned exactly the top three in that order, so
  the ANN answer is the exact one here (six rows; with millions of rows HNSW is approximate by design).
- `LIMIT` is always filled: T-106 is third although it is mostly an email ticket - "nearest" is not "similar enough".
  A desk would need a similarity cut-off on top.
- The keyspace is of D-03's kind (tablets, RF 3) and accepted the vector index, while the same keyspace refuses a
  secondary index (Stretch 3): a vector index lives in vector-store's memory, built from the table's change log, not
  in a materialized view of the ring.
- ScyllaDB's docs call vector search "available only in ScyllaDB Cloud"; here it ran self-hosted, which is why the
  lab never makes it graded-critical.
