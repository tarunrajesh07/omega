#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  while IFS='=' read -r key value; do
    [[ -z "${key// }" || "${key:0:1}" == "#" ]] && continue
    key="${key%%[[:space:]]*}"
    value="${value%$'\r'}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    if [[ -n "$key" && -z "${!key:-}" ]]; then
      export "$key=$value"
    fi
  done < .env
fi

export DEMO_MODE=false
export CARLA_ROOT="${CARLA_ROOT:-/home/vkommera/Documents/Hackathons/CARLA_Latest}"
export CARLA_HOST="${CARLA_HOST:-localhost}"
export CARLA_PORT="${CARLA_PORT:-2000}"

if [[ -d "$CARLA_ROOT/PythonAPI/carla" ]]; then
  export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla:${PYTHONPATH:-}"
fi

SPAWN_VEHICLE="${SPAWN_VEHICLE:-true}"
ENABLE_AUTOPILOT="${ENABLE_AUTOPILOT:-true}"
KEEP_SPAWNER_ALIVE="${KEEP_SPAWNER_ALIVE:-true}"
SCENARIO="${SCENARIO:-live}"
export SCENARIO_RUN_ID="${SCENARIO_RUN_ID:-$(date +%s)-$$}"

if [[ "$SPAWN_VEHICLE" == "true" ]]; then
  args=(--host "$CARLA_HOST" --port "$CARLA_PORT")
  if [[ "$SCENARIO" == "arrival_landmark" || "$SCENARIO" == "reroute_request" ]]; then
    rm -f "${SCENARIO_STATE_FILE:-.omega_scenario_state.json}"
    args+=(
      --spawn-index "${SCENARIO_SPAWN_INDEX:-0}"
      --arrival-distance "${SCENARIO_ARRIVAL_DISTANCE:-8}"
      --curb-offset-feet "${SCENARIO_CURB_OFFSET_FEET:-0}"
      --start-curb-offset-feet "${SCENARIO_START_CURB_OFFSET_FEET:-0}"
      --curb-pull-over-seconds "${SCENARIO_CURB_PULL_OVER_SECONDS:-8}"
      --min-route-distance "${SCENARIO_MIN_ROUTE_DISTANCE:-20}"
      --scenario-state-file "${SCENARIO_STATE_FILE:-.omega_scenario_state.json}"
      --scenario-run-id "$SCENARIO_RUN_ID"
      --exact-spawn
      --destroy-existing-heroes
    )
    if [[ "$SCENARIO" == "reroute_request" ]]; then
      args+=(--arrive-at-spawn --reroute-target-index "${SCENARIO_REROUTE_TARGET_INDEX:-30}" --reroute-forward-meters "${SCENARIO_REROUTE_FORWARD_METERS:-0}")
    else
      args+=(--target-index "${SCENARIO_TARGET_INDEX:-1}")
    fi
  elif [[ "$ENABLE_AUTOPILOT" == "true" ]]; then
    args+=(--autopilot)
  fi
  if [[ "$KEEP_SPAWNER_ALIVE" == "true" ]]; then
    args+=(--keep-alive)
  fi

  python -u spawn_carla_vehicle.py "${args[@]}" &
  SPAWNER_PID=$!
  trap 'kill "$SPAWNER_PID" 2>/dev/null || true' EXIT
  sleep "${SPAWNER_STARTUP_SECONDS:-4}"
fi

python main.py --live "$@"
