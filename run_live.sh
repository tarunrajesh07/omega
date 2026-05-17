#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
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

if [[ "$SPAWN_VEHICLE" == "true" ]]; then
  args=(--host "$CARLA_HOST" --port "$CARLA_PORT")
  if [[ "$SCENARIO" == "arrival_landmark" ]]; then
    rm -f "${SCENARIO_STATE_FILE:-.omega_scenario_state.json}"
    args+=(
      --spawn-index "${SCENARIO_SPAWN_INDEX:-0}"
      --target-index "${SCENARIO_TARGET_INDEX:-1}"
      --arrival-distance "${SCENARIO_ARRIVAL_DISTANCE:-8}"
      --scenario-state-file "${SCENARIO_STATE_FILE:-.omega_scenario_state.json}"
    )
  elif [[ "$ENABLE_AUTOPILOT" == "true" ]]; then
    args+=(--autopilot)
  fi
  if [[ "$KEEP_SPAWNER_ALIVE" == "true" ]]; then
    args+=(--keep-alive)
  fi

  python spawn_carla_vehicle.py "${args[@]}" &
  SPAWNER_PID=$!
  trap 'kill "$SPAWNER_PID" 2>/dev/null || true' EXIT
  sleep 2
fi

python main.py --live "$@"
