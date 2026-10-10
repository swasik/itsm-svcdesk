<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this from its two measurements; the lecturer reviews it -->
# The client-server gap on `/kb/search`

Toxiproxy sat between the load generator and `svcdesk` with a downstream latency toxic of 50 ms and 10 ms of
jitter: each chunk of the response is held for a uniformly drawn 40 to 59 ms before it is passed on. Measured twice
with the published open-loop command (30 s at 40 requests/s), the client saw a p99 of 283 and 291 ms, while the
service's own histogram, over the same requests, reported 234 and 237 ms: a gap of about 52 ms.

The histogram cannot see the gap because it lives outside the process. The service starts its clock when the request
reaches it and stops it when the last byte leaves; the toxic delays the bytes after that, on the way back. Everything
between the user and the service - a proxy, a load balancer, a slow network, TLS handshakes, a queue in front of the
workers - is spent in the same blind spot, which is why an SLO measured only at the server is an SLO about the server,
not about the user.

The gap at the p99 is not simply "latency plus jitter". The p99 of a sum is not the sum of the p99s: the slowest
server responses (the kb-index tail near 230 ms) meet a toxic delay drawn independently, so the client's p99 lands
between server p99 + 50 ms and server p99 + 59 ms, and a multi-chunk response ends at the largest of its chunk
delays, which pushes it towards the upper end. The two runs differ by 6 ms for the same reason the grader's p99
differs from a laptop's: forty tail samples per run.

What to do with it: measure latency where the user is when the user is what the SLO promises - a synthetic probe
through the same path, or client-side telemetry - and keep the server histogram for what it is good at, telling
which part of the service is slow.
