# Omega

Autonomous vehicle agent for the YC Call My Agent Hackathon (05/17/2026).

Omega watches an ego vehicle camera feed, classifies driving events with a VLM, and proactively calls the passenger through AgentPhone for arrival, blockages, hazards, and reroutes.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

By default the app runs in `DEMO_MODE=true`, which generates synthetic camera frames and scripted VLM events. This lets the full agent loop, webhook, dashboard logging, debounce logic, and call dry-run behavior work without CARLA, Gemini, or AgentPhone credentials.

## Live Mode

Set the environment variables below, start CARLA with an ego vehicle in the world, expose the webhook with a tunnel such as `ngrok http 3000`, then run:

```bash
python main.py --live
```

Or let the project spawn a CARLA ego vehicle first:

```bash
./run_live.sh
```

`run_live.sh` sets `DEMO_MODE=false`, defaults `CARLA_ROOT` to `/home/vkommera/Documents/Hackathons/CARLA_Latest`, adds `CARLA_ROOT/PythonAPI/carla` to `PYTHONPATH`, runs `spawn_carla_vehicle.py --autopilot --keep-alive`, then starts `main.py --live`. The spawned vehicle uses `role_name=hero`, which is what `capture.py` prefers when attaching the RGB camera. Stop the script with `Ctrl+C`; the spawner will destroy the vehicle actor.

You can also spawn only the vehicle:

```bash
python spawn_carla_vehicle.py --host localhost --port 2000 --autopilot --keep-alive
```

Useful live-run toggles:

```bash
SPAWN_VEHICLE=false ./run_live.sh       # use an existing CARLA vehicle
ENABLE_AUTOPILOT=false ./run_live.sh    # spawn the vehicle but leave it parked/manual
CARLA_HOST=127.0.0.1 CARLA_PORT=2000 ./run_live.sh
```

Required environment variables for live integrations:

```bash
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
AGENTPHONE_API_KEY=
AGENTPHONE_AGENT_ID=
AGENTPHONE_WEBHOOK_SECRET=
PASSENGER_PHONE_NUMBER=
CARLA_HOST=localhost
CARLA_PORT=2000
WEBHOOK_PORT=3000
```

You can put these values in a local `.env` file at the project root. `config.py` loads it automatically for Python entrypoints, and `run_live.sh` sources it before starting CARLA/Omega. Existing exported shell variables take precedence over `.env` values.

## Modules

- `capture.py`: CARLA RGB camera capture with deterministic demo-frame fallback.
- `vlm.py`: Gemini image analysis adapter with structured event parsing and scripted fallback.
- `agent.py`: ride state machine, event debouncing, call script generation, and passenger decisions.
- `caller.py`: AgentPhone `/v1/calls` integration with dry-run logging when credentials are absent.
- `webhook.py`: Flask endpoint for `agent.message` and `agent.call_ended` events.
- `main.py`: asyncio orchestrator and terminal dashboard logging.
- `spawn_carla_vehicle.py`: helper that spawns a CARLA vehicle with `role_name=hero`.
- `run_live.sh`: live-mode wrapper that can spawn the CARLA vehicle and start Omega.

## Webhook

AgentPhone should post voice events to:

```text
POST /webhook/agentphone
```

The webhook returns `{"text": "..."}` for AgentPhone TTS. If `AGENTPHONE_WEBHOOK_SECRET` is set, requests must include `X-AgentPhone-Signature` as either the raw HMAC-SHA256 hex digest or `sha256=<digest>` computed over the request body.

## Seeing The Car And Camera

In live mode, `capture.py` follows the CARLA ego vehicle with the simulator spectator camera by default. Disable or tune it with:

```bash
FOLLOW_SPECTATOR=false ./run_live.sh
SPECTATOR_DISTANCE=12 SPECTATOR_HEIGHT=6 ./run_live.sh
```

The Flask server also exposes the camera frames that Omega is analyzing:

```text
http://localhost:3000/camera.jpg   # latest frame
http://localhost:3000/camera.mjpg  # live MJPEG stream
```

If `GOOGLE_API_KEY` is set and the frame source is CARLA, Omega calls Gemini for frame analysis. Without `GOOGLE_API_KEY`, or in demo mode, it uses the scripted fallback events.

## Basic Scenarios

The default live run uses CARLA Traffic Manager autopilot from a spawn point. That is useful for smoke tests, but it is not a planned pickup route yet.

For a deterministic arrival demo, list CARLA spawn points, pick one near the landmark you want to show, then run `arrival_landmark`:

```bash
python spawn_carla_vehicle.py --host localhost --port 2000 --list-spawns

SCENARIO=arrival_landmark \
SCENARIO_SPAWN_INDEX=0 \
SCENARIO_TARGET_INDEX=1 \
DESTINATION_LABEL="the pickup curb" \
LANDMARK_LABEL="the glass office tower" \
./run_live.sh
```

In this scenario, `run_live.sh` spawns the ego vehicle at `SCENARIO_SPAWN_INDEX`, drives it to `SCENARIO_TARGET_INDEX` using CARLA's `BasicAgent`, stops the car, follows it with the spectator camera, then triggers an arrival call like: `Your ride has arrived. I'm outside the pickup curb, near the glass office tower.`

Adjust how close the vehicle must get before it stops and calls:

```bash
SCENARIO_ARRIVAL_DISTANCE=6 SCENARIO=arrival_landmark ./run_live.sh
```


Tune the warmup before the call with:

```bash
SCENARIO_WARMUP_FRAMES=12 SCENARIO=arrival_landmark ./run_live.sh
```
