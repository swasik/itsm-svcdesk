#!/usr/bin/env bash
# ai-generated: 0% - the course's helper, unchanged
# send.sh - Stretch 2 (DATA-SPEC.md D-22): sends every line of requests.jsonl to Alternator with curl, in order, and
# prints each answer's body on one line - so responses.jsonl's line i is the answer to requests.jsonl's line i.
#
#   bash stretch/alternator/send.sh < stretch/alternator/requests.jsonl > stretch/alternator/responses.jsonl
#   bash stretch/alternator/send.sh http://127.0.0.1:18000/ < ...       # another port (RING_ALTERNATOR_PORT)
#
# A request line is {"target": "DynamoDB_20120810.<Operation>", "body": {...}}: the target goes into the
# X-Amz-Target header, the body is posted as it is. Needs curl and jq (Lab 6 used both).
# An error is an answer too: DynamoDB puts it in the body ({"__type": "...#ConditionalCheckFailedException", ...}),
# so it lands in responses.jsonl like any other and the checker expects the same error back.
set -euo pipefail
url=${1:-http://127.0.0.1:8000/}
while IFS= read -r line || [[ -n $line ]]; do
  [[ -z ${line//[[:space:]]/} ]] && continue
  target=$(jq -r .target <<<"$line")
  body=$(jq -c .body <<<"$line")
  curl -sS "$url" -H "X-Amz-Target: $target" -H 'Content-Type: application/x-amz-json-1.0' -d "$body"
  echo
done
