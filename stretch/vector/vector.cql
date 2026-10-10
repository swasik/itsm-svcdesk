-- ai-generated: 20% - started from the course's vector.example.cql; the table, the four axes and the rows are mine
-- Stretch 1 (DATA-SPEC.md D-21): my svcdesk's tickets with a hand-made 4-dimensional embedding, one axis per
-- support topic, so that "which earlier tickets look like this one?" is a nearest-neighbour query.
-- Axes: [access/login, network/VPN, hardware, email]. A model's embeddings would have hundreds of dimensions.
-- The keyspace is of D-03's kind (NetworkTopologyStrategy, RF 3, tablets): a vector index is accepted there,
-- unlike a secondary index (Stretch 3), because it is not a materialized view.

CREATE KEYSPACE IF NOT EXISTS vec
  WITH replication = {'class': 'NetworkTopologyStrategy', 'replication_factor': 3};

CREATE TABLE IF NOT EXISTS vec.ticket_vectors (
  ticket_id text PRIMARY KEY,
  title text,
  priority text,
  embedding vector<float, 4>             -- axes: access, network, hardware, email
);

CREATE CUSTOM INDEX IF NOT EXISTS ticket_vectors_embedding_idx ON vec.ticket_vectors (embedding) USING 'vector_index'
  WITH OPTIONS = {'similarity_function': 'COSINE'};

INSERT INTO vec.ticket_vectors (ticket_id, title, priority, embedding) VALUES ('T-101', 'Locked out after password change', 'P3', [1.0, 0.0, 0.0, 0.1]);
INSERT INTO vec.ticket_vectors (ticket_id, title, priority, embedding) VALUES ('T-102', 'VPN drops every ten minutes', 'P2', [0.1, 1.0, 0.0, 0.0]);
INSERT INTO vec.ticket_vectors (ticket_id, title, priority, embedding) VALUES ('T-103', 'Laptop does not charge', 'P4', [0.0, 0.0, 1.0, 0.0]);
INSERT INTO vec.ticket_vectors (ticket_id, title, priority, embedding) VALUES ('T-104', 'Mailbox full, cannot send', 'P3', [0.0, 0.0, 0.0, 1.0]);
INSERT INTO vec.ticket_vectors (ticket_id, title, priority, embedding) VALUES ('T-105', 'Cannot log in to the VPN portal', 'P2', [0.7, 0.7, 0.0, 0.0]);
INSERT INTO vec.ticket_vectors (ticket_id, title, priority, embedding) VALUES ('T-106', 'MFA prompt never arrives by email', 'P2', [0.8, 0.0, 0.0, 0.6]);

-- The query of transcript.md: a new ticket "login fails over VPN" is [0.8, 0.5, 0.0, 0.0]; LIMIT is required.
-- SELECT ticket_id, title FROM vec.ticket_vectors ORDER BY embedding ANN OF [0.8, 0.5, 0.0, 0.0] LIMIT 3;
