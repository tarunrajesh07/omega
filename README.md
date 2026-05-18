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
AGENTPHONE_VOICE=
AGENTPHONE_FROM_NUMBER_ID=
PASSENGER_PHONE_NUMBER=
CARLA_HOST=localhost
CARLA_PORT=2000
WEBHOOK_PORT=3000
```

You can put these values in a local `.env` file at the project root. `config.py` loads it automatically for Python entrypoints, and `run_live.sh` sources it before starting CARLA/Omega. Existing exported shell variables take precedence over `.env` values.

`AGENTPHONE_AGENT_ID` is required for outbound calls. AgentPhone's `POST /v1/calls` API requires `agentId` and `toNumber`; Omega sends the arrival script as `initialGreeting` and includes a detailed `systemPrompt` for the built-in LLM conversation. Set the AgentPhone agent's voice mode to `hosted` for natural back-and-forth using this prompt. Use `webhook` mode only if you want AgentPhone to call Omega's `/webhook/agentphone` endpoint for every user turn.

`AGENTPHONE_VOICE` and `AGENTPHONE_FROM_NUMBER_ID` are optional per-call overrides. Use them if you want to pick a specific voice or outbound caller number from AgentPhone.

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
SPECTATOR_UPDATE_HZ=45 SPECTATOR_SMOOTHING=0.10 ./run_live.sh
```

`SPECTATOR_SMOOTHING` controls how quickly the chase camera catches up to the car. Lower values are smoother but lag farther behind; higher values track tighter but can look jumpier.

The streamed frontend camera defaults to the ego/front camera. To stream a third-person chase view instead, run with:

```bash
CAMERA_VIEW=chase ./run_live.sh
```

`CAMERA_VIEW=chase` uses a CARLA RGB sensor placed at the same chase transform as the spectator camera. CARLA does not expose the actual simulator viewport pixels through its Python API, so this is the closest API-native view to what you see in the simulator window.

Increase stream resolution and JPEG quality with:

```bash
CAMERA_WIDTH=1920 CAMERA_HEIGHT=1080 CAMERA_JPEG_QUALITY=95 CAMERA_VIEW=chase ./run_live.sh
```

Higher values look much better in the frontend but cost more simulator/GPU/CPU/network bandwidth.

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

Scenario mode still samples Gemini periodically and forces one Gemini check when the destination is reached. Tune the sampling cadence with:

```bash
SCENARIO_VLM_INTERVAL_FRAMES=25 SCENARIO=arrival_landmark ./run_live.sh
```

Adjust how close the vehicle must get before it stops and calls:

```bash
SCENARIO_ARRIVAL_DISTANCE=6 SCENARIO=arrival_landmark ./run_live.sh
```


Tune the warmup before the call with:

```bash
SCENARIO_WARMUP_FRAMES=12 SCENARIO=arrival_landmark ./run_live.sh
```


## Demo One

Demo One is the pickup arrival landmark flow. It runs the deterministic `arrival_landmark` scenario with spawn point `0`, target point `20`, destination label `the pickup curb`, landmark label `the glass office tower`, and Gemini `gemini-2.5-flash` analysis on arrival.

```bash
./demo_one
```

It is equivalent to:

```bash
SCENARIO=arrival_landmark \
SCENARIO_SPAWN_INDEX=0 \
SCENARIO_TARGET_INDEX=20 \
SCENARIO_ARRIVAL_DISTANCE=8 \
SCENARIO_WARMUP_FRAMES=8 \
SCENARIO_VLM_INTERVAL_FRAMES=10 \
DESTINATION_LABEL="the pickup curb" \
LANDMARK_LABEL="the glass office tower" \
DEMO_MODE=false \
GEMINI_MODEL=gemini-2.5-flash \
./run_live.sh
```

You can override any setting inline, for example:

```bash
SCENARIO_TARGET_INDEX=24 LANDMARK_LABEL="the hotel entrance" ./demo_one
```


## Demo Two

Demo Two is the reroute-request flow. The car starts already stopped at the pickup location, calls the passenger immediately, waits for the passenger to say `reroute`, then drives to a fixed second destination.

```bash
./demo_two
```

Defaults:

```bash
SCENARIO=reroute_request
SCENARIO_SPAWN_INDEX=0
SCENARIO_REROUTE_TARGET_INDEX=35
DESTINATION_LABEL="the pickup location"
REROUTE_DESTINATION_LABEL="the alternate pickup point"
DEMO_REROUTE_TIMEOUT_SECONDS=15
```

If no passenger transcript/call-ended webhook arrives, Demo Two automatically reroutes after `DEMO_REROUTE_TIMEOUT_SECONDS`. You can tune it inline:

```bash
DEMO_REROUTE_TIMEOUT_SECONDS=8 ./demo_two
```

If AgentPhone is down or you want to test the second driving leg manually, run this in another terminal after the call should have happened:

```bash
python - <<'PY'
import json, time
from pathlib import Path
path = Path('.omega_scenario_state.json')
payload = json.loads(path.read_text())
payload.update({'status': 'reroute_requested', 'command': 'reroute', 'updated_at': time.time()})
path.write_text(json.dumps(payload))
PY
```

You can override route points inline:

```bash
SCENARIO_SPAWN_INDEX=24 SCENARIO_REROUTE_TARGET_INDEX=40 ./demo_two
```


## AgentPhone Response Test

Use this to verify whether AgentPhone sends user speech/transcript events back to Omega. It does not use CARLA or Gemini.

Start a public tunnel to the test webhook port:

```bash
ngrok http 3010
```

Configure your AgentPhone agent/webhook URL to the tunnel URL plus this path:

```text
https://YOUR-NGROK-DOMAIN/agentphone-test
```

Then run the test in another terminal:

```bash
python test_agentphone_response.py \
  --to "+15551234567" \
  --expected "banana taxi"
```

When the call arrives, say the exact expected phrase. The script prints whether webhook events arrived, whether any transcript/message text was present, and whether the expected phrase was detected.

If it reports `events_received=0`, AgentPhone is not reaching the webhook URL. If events arrive but `transcripts: <none>`, AgentPhone is posting lifecycle events but not user speech text for this agent mode/configuration.

## One-Shot Arrival Call Test

If the car is already at the pickup location and you only want to test the arrival call flow, run:

```bash
python test_arrival_landmark_call.py \
  --destination "the pickup curb" \
  --landmark "the glass office tower" \
  --to "+15551234567"
```

This captures one CARLA camera frame, sends it to Gemini immediately, then calls the passenger through AgentPhone with an arrival script that includes the landmark and Gemini visual context. It does not drive the car or use the scenario state machine.

Use a generated frame instead of CARLA for a dry smoke test:

```bash
python test_arrival_landmark_call.py --use-demo-frame --destination "the pickup curb" --landmark "the glass office tower"
```
