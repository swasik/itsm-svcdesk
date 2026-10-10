CREATE KEYSPACE gh WITH REPLICATION_FACTOR 3 AND NETWORK_TOPOLOGY_STRATEGY 'NetworkTopologyStrategy' ('datacenter1' 'three_nodes');

CREATE TABLE gh.events_by_repo (
    event_id text,
    type text,
    actor text,
    repo text,
    org text,
    created_at timestamp,
    day date,
    hour int,
    minute int,
    bucket int,
    PRIMARY KEY (event_id, day, hour, minute)
);

CREATE TABLE gh.events_by_actor (
    event_id text,
    type text,
    actor text,
    repo text,
    org text,
    created_at timestamp,
    day date,
    hour int,
    minute int,
    bucket int,
    PRIMARY KEY (event_id, day, hour, minute)
);

CREATE TABLE gh.events_by_ticket (
    ticket_id text,
    at timestamp,
    phase text,
    priority text,
    state text,
    day date,
    PRIMARY KEY (ticket_id, day, hour, minute)
);
