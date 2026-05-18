#!/usr/bin/env bash
set -euo pipefail

# Demo One: arrival landmark pickup.
# Spawns the ego vehicle, drives to the pickup curb, runs Gemini on arrival,
# then triggers the passenger arrival call through the normal live runner.

export SCENARIO="${SCENARIO:-arrival_landmark}"
export SCENARIO_SPAWN_INDEX="${SCENARIO_SPAWN_INDEX:-15}"
export SCENARIO_TARGET_INDEX="${SCENARIO_TARGET_INDEX:-20}"
export SCENARIO_ARRIVAL_DISTANCE="${SCENARIO_ARRIVAL_DISTANCE:-8}"
export SCENARIO_CURB_OFFSET_FEET="${SCENARIO_CURB_OFFSET_FEET:-4}"
export SCENARIO_WARMUP_FRAMES="${SCENARIO_WARMUP_FRAMES:-8}"
export SCENARIO_VLM_INTERVAL_FRAMES="${SCENARIO_VLM_INTERVAL_FRAMES:-10}"
export DESTINATION_LABEL="${DESTINATION_LABEL:-normal road}"
export LANDMARK_LABEL="${LANDMARK_LABEL:-the musuem}"
export DEMO_MODE="${DEMO_MODE:-false}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
export CAMERA_VIEW="${CAMERA_VIEW:-chase}"
export CAMERA_WIDTH="${CAMERA_WIDTH:-1920}"
export CAMERA_HEIGHT="${CAMERA_HEIGHT:-1080}"
export CAMERA_JPEG_QUALITY="${CAMERA_JPEG_QUALITY:-95}"
export SPECTATOR_UPDATE_HZ="${SPECTATOR_UPDATE_HZ:-30}"
export SPECTATOR_SMOOTHING="${SPECTATOR_SMOOTHING:-0.12}"
export SPECTATOR_DISTANCE="${SPECTATOR_DISTANCE:-10}"
export SPECTATOR_HEIGHT="${SPECTATOR_HEIGHT:-5}"
export SPECTATOR_PITCH="${SPECTATOR_PITCH:--16}"

exec ./run_live.sh "$@"
