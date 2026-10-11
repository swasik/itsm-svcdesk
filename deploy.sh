#!/usr/bin/env bash
# ai-generated: 60% - the course's skeleton (plumbing); an AI assistant drafted the gate loop and the record prose from my
# design (shadow first, absolute counters, a stable control, the stall rule) and I tuned it on the practice seeds
#
# deploy-skeleton.sh - the plumbing of a Lab 6 deploy.sh, and NO gate.
#
# Copy it to deploy.sh at your repository root (chmod +x deploy.sh), then write the section marked
# "TODO: your gate". Everything above that marker is helpers: arguments and environment (R-12, R-13), reading
# deploy.config.yaml (R-07, R-11), Caddy's admin API (R-06, R-14), a Prometheus query, the canary (R-14) and the
# change record (R-23, R-24). Unchanged, the script rolls back every candidate: that is a constant strategy, and
# it fails L6-CORE-3.03 on the honest candidate.
#
#   ./deploy.sh <candidate image reference>          # e.g. ghcr.io/swasik/svcdesk-v2-seeded:2.1.0-rc.1
#
# Exit status (R-15): 0 = promoted, 3 = rolled back; 1 = the script failed (a run without an outcome).
#
# Run by the course (itsmlab release 6, itsmlab verify 6, the grader): inside the checker image, on your stack's
# network, with stdin at end-of-file and every variable of R-13 set. Run by hand: on your machine against the stack
# you started with `docker compose -f release/compose.yml up -d --wait`, with the defaults below. By hand it needs
# bash 4 or newer, curl, jq, yq v4 (https://github.com/mikefarah/yq) and docker with Compose v2, as the checker
# image has; nothing else. It never reads stdin: nobody is there to answer (R-12).
set -euo pipefail

if [ -z "${BASH_VERSINFO:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
  echo "deploy.sh: needs bash 4 or newer (macOS ships 3.2: brew install bash, or run it with itsmlab release 6)" >&2
  exit 1
fi

# --- arguments ----------------------------------------------------------------------------------------------------
if [[ $# -ne 1 || -z ${1:-} || $1 == -* ]]; then
  echo "usage: ./deploy.sh <candidate image reference>" >&2
  exit 1
fi
CANDIDATE=$1                               # the reference exactly as given: it goes into CHANGE.md verbatim (R-25)

# --- environment (R-13); the defaults are for running by hand -----------------------------------------------------
# COMPOSE_FILE: the course sets your stack plus its override; use `docker compose` without -f and -p.
export COMPOSE_FILE=${COMPOSE_FILE:-release/compose.yml}
# COMPOSE_PROJECT_NAME: the course sets it. Unset, Compose takes `name:` from release/compose.yml (svcdesk-release
# in the template), which is the project `docker compose -f release/compose.yml up` started. Leave it unset by hand
# unless you started the stack with -p.
# PROMETHEUS_URL: the course sets http://prometheus:9090. By hand: the port release/compose.yml publishes.
PROMETHEUS_URL=${PROMETHEUS_URL:-http://127.0.0.1:${PROMETHEUS_PORT:-9090}}
# CADDY_ADMIN_URL: the course sets http://edge:2019. By hand it is unset, because the template does not publish the
# admin API on your machine (and should not: it can reconfigure the proxy). Unset, every admin call runs curl
# INSIDE the edge container, `docker compose exec -T edge curl http://127.0.0.1:2019/...`: the same API, reached
# from where it listens. Set it yourself only if you publish the port on loopback and point it there.
CADDY_ADMIN_URL=${CADDY_ADMIN_URL:-}
CADDY_SERVICE=${CADDY_SERVICE:-edge}       # the compose service that runs caddy:2.11.4 (exec mode only)
# RELEASE_RECORD_DIR: the course gives an empty directory per run. By hand: a new temporary directory, printed at
# the end (never under changes/: that is for the four runs `itsmlab verify 6 --save` records, R-26).
if [[ -z ${RELEASE_RECORD_DIR:-} ]]; then
  RELEASE_RECORD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/lab6-change.XXXXXX")
fi
RELEASE_STRATEGY=${RELEASE_STRATEGY:-canary}   # canary, or flag in Stretch 2's runs (R-31)
CONFIG_FILE=${CONFIG_FILE:-deploy.config.yaml}

# --- logging and time -----------------------------------------------------------------------------------------------
# Everything the script says goes to stderr, so that helpers can print values on stdout for $(...). The course keeps
# both streams as run.log (R-26): say what you read and what you decided, with the numbers.
log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }        # ISO 8601 UTC with Z (R-23)
now_s() { date -u +%s; }
STARTED=$(now_utc)
STARTED_S=$(now_s)
elapsed_s() { echo $(( $(now_s) - STARTED_S )); }

# calc <expression>: floating-point arithmetic, which bash does not have.   calc '10 * (1 - 0.995)'  ->  0.05
calc() { awk "BEGIN { printf \"%.10g\n\", ($1) }"; }
# check <condition>: true when the awk condition holds.                     if check "$share > $threshold"; then ...
check() { awk "BEGIN { exit !($1) }"; }

# dur_seconds <Prometheus duration>: 45s -> 45, 1m30s -> 90, 500ms -> 0.5 (R-07: durations are Prometheus durations)
dur_seconds() {
  local d=$1 total=0 n u
  [[ $d =~ ^([0-9]+(ms|s|m|h|d|w|y))+$ ]] || die "not a Prometheus duration: '$d'"
  while [[ $d =~ ^([0-9]+)(ms|s|m|h|d|w|y)(.*)$ ]]; do
    n=${BASH_REMATCH[1]}; u=${BASH_REMATCH[2]}; d=${BASH_REMATCH[3]}
    case $u in
      ms) total=$(calc "$total + $n / 1000") ;;
      s) total=$(calc "$total + $n") ;;
      m) total=$(calc "$total + $n * 60") ;;
      h) total=$(calc "$total + $n * 3600") ;;
      d) total=$(calc "$total + $n * 86400") ;;
      w) total=$(calc "$total + $n * 604800") ;;
      y) total=$(calc "$total + $n * 31536000") ;;
    esac
  done
  echo "$total"
}

# --- tools ------------------------------------------------------------------------------------------------------------
for tool in curl jq yq docker awk; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is missing (R-12 lists what the checker image has; by hand, install it or use itsmlab release 6)"
done
yq --version 2>&1 | grep -q 'mikefarah' || die "yq is not mikefarah's yq v4 (https://github.com/mikefarah/yq): $(yq --version 2>&1 | head -n 1)"
docker compose version >/dev/null 2>&1 || die "docker compose (Compose v2) is missing"

# --- deploy.config.yaml (R-07, R-11) ----------------------------------------------------------------------------------
[[ -f $CONFIG_FILE ]] || die "$CONFIG_FILE not found: copy deploy.config.example.yaml to deploy.config.yaml and fill it in"

# cfg <path below lab6_deploy>: one value of the file, or an error when it is missing or null.
cfg() {
  local v
  v=$(yq -e ".lab6_deploy.$1" "$CONFIG_FILE" 2>/dev/null) || die "$CONFIG_FILE: lab6_deploy.$1 is missing or null (R-07)"
  printf '%s\n' "$v"
}

SLO_WINDOW=$(cfg slo.window)
AVAILABILITY_OBJECTIVE=$(cfg slo.availability.objective)
LATENCY_OBJECTIVE=$(cfg slo.latency.objective)
LATENCY_THRESHOLD_S=$(cfg slo.latency.threshold_seconds)
AVAILABILITY_MAX_BURN=$(cfg gate.availability.max_burn_rate)
LATENCY_MAX_BURN=$(cfg gate.latency.max_burn_rate)
MIN_REQUESTS=$(cfg gate.min_requests)
interval=$(cfg gate.interval)
INTERVAL_S=$(dur_seconds "$interval")
timeout=$(cfg timeout)
TIMEOUT_S=$(dur_seconds "$timeout")
mapfile -t STEP_WEIGHTS < <(yq '.lab6_deploy.steps[].weight' "$CONFIG_FILE")
mapfile -t step_durations < <(yq '.lab6_deploy.steps[].min_duration' "$CONFIG_FILE")
(( ${#STEP_WEIGHTS[@]} > 0 )) || die "$CONFIG_FILE: lab6_deploy.steps is empty (R-10)"
STEP_MIN_S=()                              # STEP_WEIGHTS[i] per cent for at least STEP_MIN_S[i] seconds
for d in "${step_durations[@]}"; do
  STEP_MIN_S+=("$(dur_seconds "$d")")
done

# time_left_s: seconds until your own deadline (lab6_deploy.timeout). The course kills the script at 180 s, and a
# killed run has no outcome (R-15): leave yourself the time to roll back and write the record.
time_left_s() { calc "$TIMEOUT_S - $(elapsed_s)"; }

# --- the stack ----------------------------------------------------------------------------------------------------------
# stack_curl <curl arguments...>: curl as seen from inside the stack's network. Run by the course the script is on
# that network already; by hand (CADDY_ADMIN_URL unset) it runs inside the edge container, which has curl.
stack_curl() {
  if [[ -n $CADDY_ADMIN_URL ]]; then
    curl "$@"
  else
    docker compose exec -T "$CADDY_SERVICE" curl "$@"
  fi
}

# caddy_admin <METHOD> <path> [<content type> <body>]: one call of Caddy's admin API; prints the answer.
caddy_admin() {
  local method=$1 path=$2 base=${CADDY_ADMIN_URL:-http://127.0.0.1:2019}
  local args=(-sS --fail-with-body --max-time 10 -X "$method")
  if [[ $# -ge 4 ]]; then
    args+=(-H "Content-Type: $3" --data-binary "$4")
  fi
  stack_curl "${args[@]}" "${base%/}$path"
}

# The stack as Compose resolves it (with the course's override, when the course runs the script).
STACK_JSON=$(docker compose config --format json) || die "docker compose config failed for COMPOSE_FILE=$COMPOSE_FILE"

# The Caddyfile is the one in release/compose.yml (the config named $CADDYFILE_CONFIG, as `docker compose config`
# resolves it); set_weights changes the numbers after weighted_round_robin and nothing else, so the stack's file
# and what the script loads never drift apart. Keep `admin 0.0.0.0:2019` in it: POST /load replaces the WHOLE
# configuration, the admin listener included, and without that line the admin API moves to the container's own
# localhost, where the course's runner no longer reaches it.
CADDYFILE_CONFIG=${CADDYFILE_CONFIG:-caddyfile}
CADDYFILE_TEMPLATE=$(jq -er --arg c "$CADDYFILE_CONFIG" '.configs[$c].content' <<<"$STACK_JSON") \
  || die "no config '$CADDYFILE_CONFIG' with inline content in the stack (R-01: configuration goes in through configs: content:)"
n=$(grep -cE 'weighted_round_robin([[:space:]]+[0-9]+)+' <<<"$CADDYFILE_TEMPLATE" || true)
[[ $n == 1 ]] || die "the Caddyfile must have exactly one 'lb_policy weighted_round_robin <weights>' line (it has $n)"

# caddyfile_with_weights <w1> <w2> ...: the stack's Caddyfile with these weights.
caddyfile_with_weights() {
  sed -E "s/weighted_round_robin([[:space:]]+[0-9]+)+/weighted_round_robin $*/" <<<"$CADDYFILE_TEMPLATE"
}

# get_weights: the weights Caddy runs now, space-separated in upstream order, e.g. "90 10".
# weights_by_upstream: the same as lines "<upstream> <weight>", e.g. "svcdesk-canary:8080 10".
WRR='[.. | objects | select(.handler? == "reverse_proxy" and .load_balancing.selection_policy.policy? == "weighted_round_robin")] | first // empty'
get_weights() {
  caddy_admin GET /config/ | jq -r "$WRR"' | .load_balancing.selection_policy.weights | map(tostring) | join(" ")'
}
weights_by_upstream() {
  caddy_admin GET /config/ \
    | jq -r "$WRR"' | [.upstreams, .load_balancing.selection_policy.weights] | transpose[] | "\(.[0].dial) \(.[1])"'
}

# set_weights <stable> <canary>: load the Caddyfile with these weights (whole numbers, in upstream order; a stack
# with a third upstream, such as Stretch 1's recipe, passes three). Refuses all-zero weights (R-06: Caddy 2.11.4
# then answers no request at all), then reads the weights back and fails unless Caddy runs exactly these.
set_weights() {
  local w sum=0 got body
  (( $# >= 2 )) || die "set_weights needs one weight per upstream, e.g. set_weights 90 10"
  for w in "$@"; do
    [[ $w =~ ^[0-9]+$ ]] || die "set_weights: '$w' is not a whole number"
    sum=$(( sum + w ))
  done
  (( sum > 0 )) || die "set_weights $*: refused - with every weight at 0 Caddy 2.11.4 answers no request at all (R-06)"
  body=$(caddyfile_with_weights "$@")
  [[ -n $body ]] || die "set_weights: empty Caddyfile"
  caddy_admin POST /load text/caddyfile "$body" >/dev/null \
    || { log "set_weights $*: Caddy refused the configuration"; return 1; }
  got=$(get_weights) || { log "set_weights $*: could not read the weights back"; return 1; }
  [[ $got == "$*" ]] || { log "set_weights $*: Caddy runs '$got'"; return 1; }
  log "weights now $*"
}

# start_canary <image>: put an image into svcdesk-canary, the one command R-14 allows for it. Only svcdesk-canary is
# recreated; it keeps whatever weight Caddy gives it (put it at 0 first). Waits until the new container answers
# /health. Your own requests to svcdesk-canary are not the users' (R-14), but a search you send counts towards the
# hang's onset like any other (RELEASE-SPEC.md R-30).
start_canary() {
  local image=$1 i
  CANARY_IMAGE=$image docker compose up -d --no-deps --wait svcdesk-canary >&2 \
    || { log "start_canary: compose could not start svcdesk-canary with $image"; return 1; }
  for i in $(seq 1 30); do
    if stack_curl -fsS --max-time 2 http://svcdesk-canary:8080/health >/dev/null 2>&1; then
      log "svcdesk-canary runs $image"
      return 0
    fi
    sleep 1
  done
  log "start_canary: svcdesk-canary did not answer /health within 30 s"
  return 1
}

# --- Prometheus -----------------------------------------------------------------------------------------------------
# prom_query <PromQL>: one instant query against your Prometheus. The query must return exactly one number (use
# sum(...) around a vector). Prints it and returns:
#   0  a number (possibly +Inf);
#   1  Prometheus did not answer, refused the query, or returned more than one series;
#   2  NO DATA: an empty result, or NaN (0 divided by 0: nothing to count yet).
# 2 is not a pass and not a failure: what it means for your gate is your decision (the empty-data case, R-28).
# Under set -e, call it inside `if` or with `||`, never bare:
#   if share=$(prom_query "$q"); then ...; else rc=$?; ...; fi
prom_query() {
  local body n value
  body=$(curl -sS --fail-with-body --max-time 5 "${PROMETHEUS_URL%/}/api/v1/query" --data-urlencode "query=$1" 2>&1) \
    || { log "prom_query: no answer from $PROMETHEUS_URL, or an error: ${body:0:300}"; return 1; }
  [[ $(jq -r '.status' <<<"$body" 2>/dev/null) == success ]] \
    || { log "prom_query: ${body:0:300}"; return 1; }
  case $(jq -r '.data.resultType' <<<"$body") in
    scalar) value=$(jq -r '.data.result[1]' <<<"$body") ;;
    vector)
      n=$(jq '.data.result | length' <<<"$body")
      (( n == 0 )) && return 2
      (( n == 1 )) || { log "prom_query: $n series, expected one (aggregate with sum): $1"; return 1; }
      value=$(jq -r '.data.result[0].value[1]' <<<"$body") ;;
    *) log "prom_query: a range or string result, expected one number: $1"; return 1 ;;
  esac
  [[ $value == NaN ]] && return 2
  printf '%s\n' "$value"
}

# --- the change record (R-23, R-24, R-27) ---------------------------------------------------------------------------
# Your decisions about this change, the same for every run. The record check accepts only the values listed.
CHANGE_TYPE=standard             # standard | normal | emergency - pre-authorised: see record_body
RISK=low                         # low | medium | high
ROLLBACK_PLAN="Caddy weights back to stable 100 / canary 0 through the admin API in one call (never 0 0); in a flag run the flag off first. The stable build serves throughout and is never restarted."

STABLE_IMAGE=$(jq -r '.services["svcdesk-stable"].image // empty' <<<"$STACK_JSON")
[[ -n $STABLE_IMAGE ]] || die "the stack has no service svcdesk-stable (R-01)"

ACTIONS=()
RECORD_WRITTEN=0

# yaml_str <text>: a quoted YAML string (a JSON string is one).
yaml_str() { jq -Rn --arg s "$1" '$s'; }

# record_action <autonomy> <what the script did> [<approval>]: one entry of `actions`, stamped now. The autonomy
# ladder of Lecture 6: read-only, suggest, approve-then-act, closed-loop. approve-then-act needs the approval that
# existed before the run (a change ticket, a CAB decision): nobody can approve during it (R-24).
record_action() {
  local autonomy=$1 text=$2 approval=${3:-} entry
  case $autonomy in
    read-only|suggest|approve-then-act|closed-loop) ;;
    *) die "record_action: autonomy '$autonomy' is not one of read-only, suggest, approve-then-act, closed-loop" ;;
  esac
  entry="{at: $(now_utc), action: $(yaml_str "$text"), autonomy: $autonomy"
  if [[ $autonomy == approve-then-act ]]; then
    [[ ${#approval} -ge 5 ]] || die "record_action: approve-then-act needs the approval it acts on (R-24)"
    entry+=", approval: $(yaml_str "$approval")"
  fi
  ACTIONS+=("$entry}")
  log "action [$autonomy] $text"
}

# record_body: the prose below the front matter, read by the lecturer (R-27). Write yours: it is the same reasoning
# for every run, and you may add what this run saw (the variables of the script are in scope).
record_body() {
  cat <<EOF
# Change record

## Why this change type

A standard change: this procedure is pre-authorised once, for every candidate of svcdesk 2.x that the course
pipeline built, and runs with nobody at the keyboard. It earns the pre-authorisation because its risk is bounded by
construction, not by a person watching: the candidate first gets only a mirrored copy of the traffic (the shadow,
whose answers nobody sees), then 10 % of the users, then 50 %, and every step is judged against my Lab 3 SLO as burn
rates - 5xx above $(pct "$AVAIL_THR") % or slower than ${LATENCY_THRESHOLD_S} s above $(pct "$LAT_THR") % fails it, as does a canary whose
searches stop arriving. My four practice runs and the practice seeds are the evidence that the procedure is well
understood. It would become a normal change - assessed and authorised by a person before the run - for anything
outside that envelope: a candidate that changes the API or the data, a plan with a first step above 20 %, a gate
change that has not yet been through the practice seeds, or a stack without the shadow. An emergency change would
skip the shadow and the 45 s step; I would give up the bound on the blast radius, and only for a fix that stops a
larger outage.

## Risk and what bounds it

Users can be hurt only once the candidate answers them. In the shadow phase that never happens: users get 2.0.0
through nginx, and a bad candidate is rolled back there. If a bad candidate passed the shadow, the 10 % step bounds
it: failures ~ c + R x w x q x D = 5 + 40 x 0.1 x q x D; for errors at q = 0.6 and D = 12 s that is about 34, for a
hang (q = 1, c = 0, D = the 12 s stall rule + a scrape + a look, about 22 s) about 88 - under the ceiling of 150.
What my gate cannot see: a candidate that breaks only routes other than /kb/search, and a fault that starts after
promotion.

This run: candidate $CANDIDATE, strategy $RELEASE_STRATEGY.
EOF
}

# write_record <promoted|rolled-back> <reason>: $RELEASE_RECORD_DIR/CHANGE.md with R-23's front matter.
write_record() {
  local outcome=$1 reason=$2 finished a
  finished=$(now_utc)
  case $CHANGE_TYPE in standard|normal|emergency) ;; *) log "WARNING: change_type '$CHANGE_TYPE' is not standard, normal or emergency" ;; esac
  case $RISK in low|medium|high) ;; *) log "WARNING: risk '$RISK' is not low, medium or high" ;; esac
  (( ${#ROLLBACK_PLAN} >= 20 )) || log "WARNING: rollback_plan is shorter than 20 characters"
  (( ${#reason} >= 10 )) || log "WARNING: reason is shorter than 10 characters"
  (( ${#ACTIONS[@]} >= 3 )) || log "WARNING: ${#ACTIONS[@]} actions recorded; R-24 wants at least three"
  mkdir -p "$RELEASE_RECORD_DIR"
  {
    echo "---"
    echo "lab6_change:"
    echo "  id: CHG-${STARTED//[-:]/}"
    echo "  candidate: $(yaml_str "$CANDIDATE")"
    echo "  stable: $(yaml_str "$STABLE_IMAGE")"
    echo "  strategy: $RELEASE_STRATEGY"
    echo "  change_type: $CHANGE_TYPE"
    echo "  risk: $RISK"
    echo "  rollback_plan: $(yaml_str "$ROLLBACK_PLAN")"
    echo "  started: $STARTED"
    echo "  finished: $finished"
    echo "  outcome: $outcome"
    echo "  reason: $(yaml_str "$reason")"
    echo "  actions:"
    for a in "${ACTIONS[@]}"; do
      echo "    - $a"
    done
    echo "---"
    record_body
  } >"$RELEASE_RECORD_DIR/CHANGE.md"
  RECORD_WRITTEN=1
  log "record: $RELEASE_RECORD_DIR/CHANGE.md"
}

# finish <promoted|rolled-back> <reason>: write the record and exit 0 or 3 (R-15). Call it only once the routing it
# reports is in place. In a canary run it checks Caddy first - promoted: every upstream but svcdesk-canary at 0;
# rolled back: svcdesk-canary at 0 - and exits 1, a run without an outcome, when the weights disagree.
finish() {
  local outcome=$1 reason=$2 weights canary others
  case $outcome in promoted|rolled-back) ;; *) die "finish: the outcome is promoted or rolled-back, not '$outcome'" ;; esac
  if [[ $RELEASE_STRATEGY == canary ]]; then
    weights=$(weights_by_upstream) || die "finish: could not read Caddy's weights"
    canary=$(awk '$1 == "svcdesk-canary:8080" { print $2 }' <<<"$weights")
    others=$(awk '$1 != "svcdesk-canary:8080" { s += $2 } END { print s + 0 }' <<<"$weights")
    if [[ $outcome == promoted ]] && ! (( ${canary:-0} > 0 && others == 0 )); then
      die "finish promoted, but Caddy's weights are: $(tr '\n' ' ' <<<"$weights")- the stable build still takes requests"
    fi
    if [[ $outcome == rolled-back ]] && (( ${canary:-0} != 0 )); then
      die "finish rolled-back, but Caddy's weights are: $(tr '\n' ' ' <<<"$weights")- the candidate still takes requests"
    fi
  fi
  write_record "$outcome" "$reason"
  log "outcome: $outcome - $reason ($(elapsed_s) s)"
  if [[ $outcome == promoted ]]; then exit 0; else exit 3; fi
}

on_exit() {
  local rc=$?
  if (( RECORD_WRITTEN == 0 )); then
    log "exited with status $rc before finish: no record, no outcome (R-15, R-23)"
  fi
}
trap on_exit EXIT

log "candidate $CANDIDATE, stable $STABLE_IMAGE, strategy $RELEASE_STRATEGY"
log "config: SLO window $SLO_WINDOW; availability $AVAILABILITY_OBJECTIVE (max burn $AVAILABILITY_MAX_BURN);" \
    "latency $LATENCY_OBJECTIVE under ${LATENCY_THRESHOLD_S}s (max burn $LATENCY_MAX_BURN);" \
    "min_requests $MIN_REQUESTS; interval ${INTERVAL_S}s; timeout ${TIMEOUT_S}s;" \
    "steps ${STEP_WEIGHTS[*]} % for ${STEP_MIN_S[*]} s"
log "Prometheus $PROMETHEUS_URL; Caddy admin ${CADDY_ADMIN_URL:-via docker compose exec $CADDY_SERVICE}"

# =====================================================================================================================
# The gate (mine). Shadow first (Stretch 1), then the weighted steps, then promote; or, in a flag run (Stretch 2),
# the flag's steps instead of the weights. The same judgement in every phase:
#
#   n     canary searches observed in this phase (counter now minus counter at the phase's start - absolute
#         counters, no range window, so nothing from before the phase and no extrapolation);
#   bad   its 5xx answers, and slow = n minus those within the SLO threshold (the le bucket);
#   ctl   the same shares on the stable track over the same phase: the control. kb-index's floor and any host load
#         reach both builds alike.
#
#   FAIL  a share above max_burn_rate x (1 - objective), with at least MIN_BAD bad searches behind it, and above the
#         stable build's share by more than half the threshold; or
#         the canary's searches stop arriving: no new canary search for STALL_S seconds while the traffic should
#         have brought at least STALL_MIN_EXPECTED (a hang is never observed after its onset: no data IS the signal);
#         or Prometheus unreadable MAX_READ_ERRORS looks in a row (no evidence is no promotion).
#   PASS  min_duration over, n >= min_requests (shadow: its own min_requests), and no FAIL.
#   else  wait one interval; past my own deadline: roll back.
# =====================================================================================================================
MIN_BAD=$(yq '.lab6_deploy.gate.min_bad // 5' "$CONFIG_FILE")     # not an R-07 field; 5 unless the file says
STALL_S=12                       # > two scrapes (5 s) and a look: an honest canary is never silent that long
STALL_MIN_EXPECTED=20            # ... while the traffic should have brought it at least this many searches
MAX_READ_ERRORS=3
SAFETY_S=15                      # stop judging this many seconds before my deadline: time to roll back and record

AVAIL_THR=$(calc "$AVAILABILITY_MAX_BURN * (1 - $AVAILABILITY_OBJECTIVE)")
LAT_THR=$(calc "$LATENCY_MAX_BURN * (1 - $LATENCY_OBJECTIVE)")
# The le label as Prometheus 3 stores it: 0.3 -> "0.3", 1 -> "1.0" (RELEASE-SPEC.md section 2).
LE=$(awk -v t="$LATENCY_THRESHOLD_S" 'BEGIN { s = sprintf("%.10g", t); if (s !~ /[.e]/) s = s ".0"; print s }')
SHADOW_MIN=$(yq '.lab6_deploy.shadow.min_requests // 0' "$CONFIG_FILE")
log "gate: availability fails above $(calc "$AVAIL_THR * 100") % 5xx, latency above $(calc "$LAT_THR * 100") % slower than ${LATENCY_THRESHOLD_S}s (le=\"$LE\"); min_bad $MIN_BAD; stall ${STALL_S}s"

SEARCH='job="svcdesk", http_route="/kb/search"'

# All the counters of one look are read at ONE evaluation instant, 2 s in the past: six separate queries at "now"
# can straddle a scrape, and then a count and its le bucket come from different scrapes - a whole scrape's worth of
# searches (200 in the shadow) would read as slow. A scrape's samples share one timestamp and land together, so
# every query at the same past instant sees the same scrapes.
EVAL_AT=""
prom_query_at() {
  local body n value
  body=$(curl -sS --fail-with-body --max-time 5 "${PROMETHEUS_URL%/}/api/v1/query" --data-urlencode "query=$1" \
    --data-urlencode "time=$EVAL_AT" 2>&1) \
    || { log "prom_query_at: no answer from $PROMETHEUS_URL, or an error: ${body:0:300}"; return 1; }
  [[ $(jq -r '.status' <<<"$body" 2>/dev/null) == success ]] || { log "prom_query_at: ${body:0:300}"; return 1; }
  n=$(jq '.data.result | length' <<<"$body")
  (( n == 0 )) && return 2
  (( n == 1 )) || { log "prom_query_at: $n series, expected one: $1"; return 1; }
  value=$(jq -r '.data.result[0].value[1]' <<<"$body")
  [[ $value == NaN ]] && return 2
  printf '%s\n' "$value"
}

# counter <track> <extra matchers> <kind: all|5xx|fast>: the absolute counter at EVAL_AT, summed over the track.
counter() {
  local track=$1 extra=$2 kind=$3 sel
  sel="$SEARCH, track=\"$track\"${extra:+, $extra}"
  case $kind in
    all) prom_query_at "sum(http_server_request_duration_seconds_count{$sel}) or vector(0)" ;;
    5xx) prom_query_at "sum(http_server_request_duration_seconds_count{$sel, http_response_status_code=~\"5..\"}) or vector(0)" ;;
    fast) prom_query_at "sum(http_server_request_duration_seconds_bucket{$sel, le=\"$LE\"}) or vector(0)" ;;
  esac
}

# read_counters <mode>: sets C_N C_5 C_F (the canary, flag "on" only in flag mode), S_N S_5 S_F (the control: the
# stable track; in flag mode the canary's own "off" searches) and X_N (what the expected arrivals are counted from).
read_counters() {
  local mode=$1 c_extra="" s_track=stable s_extra=""
  if [[ $mode == flag ]]; then
    c_extra='feature_flag_variant="on"'; s_track=canary; s_extra='feature_flag_variant="off"'
  fi
  EVAL_AT=$(( $(now_s) - 2 ))
  C_N=$(counter canary "$c_extra" all) && C_5=$(counter canary "$c_extra" 5xx) && C_F=$(counter canary "$c_extra" fast) \
    && S_N=$(counter "$s_track" "$s_extra" all) && S_5=$(counter "$s_track" "$s_extra" 5xx) \
    && S_F=$(counter "$s_track" "$s_extra" fast) || return 1
  X_N=$S_N
}

share() { if check "$2 > 0"; then calc "$1 / $2"; else echo 0; fi; }
pct() { awk -v x="$1" 'BEGIN { printf "%.1f", x * 100 }'; }

# wait_fresh_scrape: the canary's series in Prometheus come from the new container only after a scrape that
# happened after it started.
wait_fresh_scrape() {
  local since=$1 ts i
  for i in $(seq 1 20); do
    if ts=$(prom_query 'max(timestamp(up{job="svcdesk", track="canary"}))') && check "$ts > $since"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# run_phase <label> <mode: shadow|canary|flag> <share: weight or percent> <min_duration_s> <min_requests>
# Returns 0 = passed, 1 = failed (REASON says why). The caller has already routed the traffic.
REASON=""
run_phase() {
  local label=$1 mode=$2 w=$3 min_s=$4 min_n=$5
  local t0 c0n c05 c0f s0n s05 s0f n bad slow sn sbad sslow a_sh l_sh sa_sh sl_sh read_err=0 looks=0
  local last_n=-1 last_change_t last_change_x expected x_since el
  read_counters "$mode" || { REASON="$label: Prometheus unreadable at the start of the phase"; return 1; }
  record_action read-only "$label: read the canary's and the stable build's search counters from Prometheus (phase start)"
  t0=$(now_s); c0n=$C_N; c05=$C_5; c0f=$C_F; s0n=$S_N; s05=$S_5; s0f=$S_F
  last_change_t=$t0; last_change_x=$X_N
  while :; do
    sleep "$INTERVAL_S"
    looks=$((looks + 1))
    if (( $(printf '%.0f' "$(time_left_s)") < SAFETY_S )); then
      REASON="$label: my deadline came before the phase passed (n=${n:-0} canary searches)"; return 1
    fi
    if ! read_counters "$mode"; then
      read_err=$((read_err + 1)); log "$label: Prometheus read failed ($read_err in a row)"
      if (( read_err >= MAX_READ_ERRORS )); then REASON="$label: Prometheus unreadable $read_err looks in a row - no evidence, no promotion"; return 1; fi
      continue
    fi
    read_err=0
    el=$(( $(now_s) - t0 ))
    n=$(calc "$C_N - $c0n"); bad=$(calc "$C_5 - $c05"); slow=$(calc "$n - ($C_F - $c0f)")
    sn=$(calc "$S_N - $s0n"); sbad=$(calc "$S_5 - $s05"); sslow=$(calc "$sn - ($S_F - $s0f)")
    a_sh=$(share "$bad" "$n"); l_sh=$(share "$slow" "$n"); sa_sh=$(share "$sbad" "$sn"); sl_sh=$(share "$sslow" "$sn")
    log "$label t+${el}s: canary n=$n 5xx=$bad ($(pct "$a_sh") %) slow=$slow ($(pct "$l_sh") %) | control n=$sn 5xx $(pct "$sa_sh") % slow $(pct "$sl_sh") %"
    # the two SLIs
    if check "$bad >= $MIN_BAD && $a_sh > $AVAIL_THR && $a_sh - $sa_sh > $AVAIL_THR / 2"; then
      REASON="$label: availability - $bad of $n canary searches answered 5xx ($(pct "$a_sh") %) against a $(pct "$AVAIL_THR") % threshold (stable $(pct "$sa_sh") %)"; return 1
    fi
    if check "$slow >= $MIN_BAD && $l_sh > $LAT_THR && $l_sh - $sl_sh > $LAT_THR / 2"; then
      REASON="$label: latency - $slow of $n canary searches slower than ${LATENCY_THRESHOLD_S}s ($(pct "$l_sh") %) against a $(pct "$LAT_THR") % threshold (stable $(pct "$sl_sh") %)"; return 1
    fi
    # the empty-data case: searches that should arrive and do not
    if [[ $n != "$last_n" ]]; then
      last_n=$n; last_change_t=$(now_s); last_change_x=$X_N
    else
      x_since=$(calc "$X_N - $last_change_x")
      case $mode in
        shadow) expected=$x_since ;;                                  # every user search is mirrored
        *) expected=$(calc "$x_since * $w / (100 - $w)") ;;           # the control gets 100 - w of them
      esac
      if (( $(now_s) - last_change_t >= STALL_S )) && check "$expected >= $STALL_MIN_EXPECTED"; then
        REASON="$label: the canary's searches stopped arriving - none observed for $(( $(now_s) - last_change_t )) s while about $(printf '%.0f' "$expected") should have (stuck at $n): a hung candidate"
        return 1
      fi
    fi
    if (( el >= ${min_s%.*} )) && check "$n >= $min_n"; then
      REASON="$label passed: $n canary searches, 5xx $(pct "$a_sh") % (<= $(pct "$AVAIL_THR") %), slow $(pct "$l_sh") % (<= $(pct "$LAT_THR") %), $looks looks"
      record_action read-only "$label: $looks reads of the canary's SLIs from Prometheus; passed with $n searches"
      return 0
    fi
  done
}

rollback() {   # rollback <reason>
  local reason=$1
  if [[ $RELEASE_STRATEGY == flag ]]; then
    change_flag 0 "roll back: every search on 2.0.0's path" || log "WARNING: flagd does not confirm the flag off"
  fi
  set_weights 100 0 "${SHADOW_W[@]}" || set_weights 100 0 "${SHADOW_W[@]}" || die "could not roll back the weights"
  record_action closed-loop "set weights 100/0 (roll back: the stable build serves every request)"
  finish rolled-back "$reason"
}

promote() {    # promote <reason>
  if [[ $RELEASE_STRATEGY == flag ]]; then
    change_flag 100 "promote" || rollback "flagd does not serve the flag on for everyone"
  else
    set_weights 0 100 "${SHADOW_W[@]}" || rollback "could not set the promotion weights"
    record_action closed-loop "set weights 0/100 (promote: the candidate serves every request)"
  fi
  finish promoted "$1"
}

# The stack's upstreams: a third one is the shadow (Stretch 1); its weight is 0 outside the shadow phase.
NUP=$(grep -oE 'weighted_round_robin([[:space:]]+[0-9]+)+' <<<"$CADDYFILE_TEMPLATE" | wc -w); NUP=$((NUP - 1))
SHADOW_W=(); (( NUP >= 3 )) && SHADOW_W=(0)
FLAG_NAME=$(yq '.lab6_deploy.flag.name // "svcdesk-2-1"' "$CONFIG_FILE")

# --- flag helpers (Stretch 2; the course's set-flag.sh) -------------------------------------------------------------
set_flag_percent() {
  local p=$1 f
  [[ $p =~ ^[0-9]+$ ]] && (( p <= 100 )) || die "set_flag_percent: '$p' is not a whole number from 0 to 100"
  f=$(mktemp)
  jq -n --arg name "$FLAG_NAME" --argjson p "$p" '{flags: {($name): {state: "ENABLED", variants: {on: true, off: false},
    defaultVariant: "off", targeting: {fractional: [["on", $p], ["off", (100 - $p)]]}}}}' >"$f"
  chmod 644 "$f"
  if ! docker compose cp "$f" flagd:/etc/flagd/flags.json >/dev/null 2>&1; then
    rm -f "$f"; log "set_flag_percent $p: docker compose cp into flagd failed"; return 1
  fi
  rm -f "$f"
  log "flag $FLAG_NAME on for $p % of searches"
}

# Postmortem action (Lab 4, "Record every runtime flag change as a change"): every flag change is an action of the
# record with its before and after, and is confirmed by reading the flag back from flagd itself (OFREP, 40
# evaluations with random keys) - the incident's flags changed with nobody recording or checking them, and flagd
# ignores a file it cannot read without saying so. A change flagd does not serve is a failed change.
FLAG_NOW=unknown
flag_readback() {   # flag_readback -> "<on> <of>" from 40 OFREP evaluations
  local args=() i
  for i in $(seq 1 40); do
    (( i > 1 )) && args+=(--next)
    args+=(-sS --max-time 2 -X POST -H "Content-Type: application/json"
      -d "{\"context\": {\"targetingKey\": \"deploy-$RANDOM-$i\"}}" "http://flagd:8016/ofrep/v1/evaluate/flags/$FLAG_NAME")
  done
  stack_curl "${args[@]}" 2>/dev/null | jq -s -r '[.[] | select(.value != null)] | "\([.[] | select(.value == true)] | length) \(length)"'
}
change_flag() {     # change_flag <percent> <why>
  local p=$1 why=$2 rb on of i ok=0
  set_flag_percent "$p" || return 1
  record_action closed-loop "flag $FLAG_NAME: $FLAG_NOW % -> $p % ($why)"
  for i in $(seq 1 8); do
    sleep 1
    rb=$(flag_readback) || rb="0 0"; read -r on of <<<"$rb"
    if (( of >= 30 )); then
      if (( p == 0 && on == 0 )) || (( p == 100 && on == of )) || (( p > 0 && p < 100 && on > 0 && on < of )); then ok=1; break; fi
      (( p > 0 && p < 100 && i >= 4 && of >= 30 )) && { ok=1; break; }     # a small share may show no "on" in 40
    fi
  done
  record_action read-only "read flag $FLAG_NAME back from flagd: $on of $of evaluations on (asked for $p %)"
  (( ok )) || { log "flagd does not serve $p % (readback $on/$of)"; return 1; }
  FLAG_NOW=$p
}

# --- the release ------------------------------------------------------------------------------------------------------
if [[ $RELEASE_STRATEGY == flag ]]; then
  # Dark first: the flag off for everyone, then the candidate behind all the weights (it runs 2.0.0's path).
  change_flag 0 "dark, before the candidate starts" || die "flagd does not serve the flag off: the candidate would not be dark"
fi

set_weights 100 0 "${SHADOW_W[@]}" || die "could not set the starting weights"
T_CANARY=$(now_s)
start_canary "$CANDIDATE" || rollback "the candidate did not start or did not answer /health"
record_action closed-loop "start svcdesk-canary with the candidate at weight 0"
wait_fresh_scrape "$T_CANARY" || log "WARNING: no fresh scrape of the canary yet"

if [[ $RELEASE_STRATEGY == flag ]]; then
  set_weights 0 100 "${SHADOW_W[@]}" || rollback "could not route the users to the dark candidate"
  record_action closed-loop "set weights 0/100: the candidate serves every user, dark (flag off)"
  mapfile -t FLAG_P < <(yq '.lab6_deploy.flag.steps[].percent' "$CONFIG_FILE")
  mapfile -t flag_d < <(yq '.lab6_deploy.flag.steps[].min_duration' "$CONFIG_FILE")
  (( ${#FLAG_P[@]} > 0 )) || rollback "flag run without flag.steps in $CONFIG_FILE"
  for i in "${!FLAG_P[@]}"; do
    change_flag "${FLAG_P[$i]}" "step $((i + 1))" || rollback "flagd does not serve the flag at ${FLAG_P[$i]} %"
    run_phase "flag ${FLAG_P[$i]} %" flag "${FLAG_P[$i]}" "$(dur_seconds "${flag_d[$i]}")" "$MIN_REQUESTS" || rollback "$REASON"
    log "$REASON"
  done
  promote "every flag step passed: $REASON"
fi

if (( NUP >= 3 )) && check "$SHADOW_MIN > 0"; then
  set_weights 0 0 100 || rollback "could not start the shadow"
  record_action closed-loop "set weights 0/0/100: the shadow phase (users on 2.0.0 through nginx, a copy to the candidate)"
  run_phase "shadow" shadow 100 10 "$SHADOW_MIN" || rollback "$REASON"
  log "$REASON"
fi

for i in "${!STEP_WEIGHTS[@]}"; do
  w=${STEP_WEIGHTS[$i]}
  set_weights $((100 - w)) "$w" "${SHADOW_W[@]}" || rollback "could not set the weights $((100 - w))/$w"
  record_action closed-loop "set weights $((100 - w))/$w"
  run_phase "step $((i + 1)) at $w %" canary "$w" "${STEP_MIN_S[$i]}" "$MIN_REQUESTS" || rollback "$REASON"
  log "$REASON"
done
promote "every step passed: $REASON"
