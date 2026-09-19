#!/usr/bin/env bash
# ai-generated: 100% - Claude Code (Fable 5.1) wrote this script from design/LAB1.md section 8.2; the lecturer ran it
# Start the reference under each of the eight resolution combinations with Docker Compose, run the compose
# `tests` service against it, and print one line per combination with the ITSMLAB-TESTS summary.
#
#   PROJECT=refsvcdesk-build SVCDESK_PORT=18080 scripts/run_all_combinations.sh
#
# The image is built once; each combination gets a fresh named volume (down -v between runs).
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${PROJECT:-refsvcdesk-build}"
export SVCDESK_PORT="${SVCDESK_PORT:-18080}"
compose=(docker compose -p "$PROJECT")

cleanup() { "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

"${compose[@]}" build --quiet
failures=0
for c1 in wallclock business; do
  for c2 in reopen immutable; do
    for c3 in matrix vip; do
      export SVCDESK_C1="$c1" SVCDESK_C2="$c2" SVCDESK_C3="$c3"
      "${compose[@]}" up --wait svcdesk >/dev/null 2>&1
      health=$(curl -fsS "http://127.0.0.1:${SVCDESK_PORT}/health")
      last=$("${compose[@]}" --profile tests run --rm tests 2>/dev/null | tail -n 1) || true
      case "$last" in
        "ITSMLAB-TESTS: passed="*" failed=0") status=ok ;;
        *) status=FAIL; failures=$((failures + 1)) ;;
      esac
      printf '%-9s %-9s %-6s  %-4s  %s   health=%s\n' "$c1" "$c2" "$c3" "$status" "$last" "$health"
      "${compose[@]}" down -v >/dev/null 2>&1
    done
  done
done
echo "combinations failed: $failures"
exit "$failures"
