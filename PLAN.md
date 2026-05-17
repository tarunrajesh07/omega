# Omega — Autonomous Vehicle Agent with Live Vision & Voice

**Hackathon:** YC Call My Agent Hackathon (05/17/2026)

---

## Concept

A self-driving car agent that watches its own surroundings via a VLM (Gemini Live API) and proactively phones the passenger when it needs to communicate — arrival, detours, blockages, or help resolving an obstacle.

The core insight: the car doesn't wait for the passenger to ask. It sees, decides, and calls.

---

## Architecture

```
CARLA Simulator
     │  (RGB camera frames via Python client)
     ▼
Frame Capture Service  ──────────────────────────────┐
     │  (captures frames at ~5-10 fps)               │
     ▼                                               │
Gemini Live API (VLM)                                │
     │  (streaming multimodal session)               │
     │  analyzes: road state, blockages,             │
     │  destination proximity, hazards               │
     ▼                                               │
Agent Decision Engine                                │
     │  (event classifier + call trigger logic)      │
     │                                               │
     ├──► "arrived" event                            │
     ├──► "blocked" event                            │
     ├──► "rerouting" event                          │
     └──► "hazard" event                             │
          │                                          │
          ▼                                          │
  AgentPhone (POST /v1/calls)                        │
          │  outbound call to passenger              │
          ▼                                          │
  Passenger speaks → AgentPhone transcribes          │
          │  webhook: agent.message {transcript}     │
          ▼                                          │
  Webhook Server (Flask) ─── LLM reply ──► {"text"} │
          │  AgentPhone TTS's response back          │
          ▼                                          │
     Passenger Phone ◄───────────────────────────────┘
                           (bidirectional voice)
```

---

## Stack

| Layer | Technology |
|---|---|
| Simulator | CARLA 0.9.x (Python client) |
| VLM | Google Gemini 2.0 Flash Live API |
| Orchestration | Python asyncio agent loop |
| Phone calls | AgentPhone (`pip install agentphone`) |
| TTS + STT | Handled automatically by AgentPhone |
| Webhook server | Flask (receives `agent.message` voice events) |
| Frame transport | In-process PIL → base64 → Gemini stream |
| State machine | Simple Python FSM (idle → en_route → blocked → arrived) |

---

## Components

### 1. CARLA Frame Capture (`capture.py`)
- Connect to CARLA via `carla` Python library
- Attach an RGB camera sensor to the ego vehicle
- Capture frames at 5–10 fps (throttled to stay within Gemini rate limits)
- Expose frames via an async queue consumed by the VLM session

### 2. Gemini Live Streaming Session (`vlm.py`)
- Open a persistent Gemini Live API session (WebSocket-based)
- Send frames + a system prompt telling the model its role:
  - "You are the vision system for an autonomous vehicle. Analyze each frame and report one of: [en_route, arrived, blocked, hazard, rerouting]. Include a one-sentence plain-English reason."
- Parse structured JSON responses from the model
- Emit events to the agent decision engine

### 3. Agent Decision Engine (`agent.py`)
- Maintains a state machine: `idle → en_route → [blocked | arrived | hazard]`
- Debounces events (e.g., require 3 consecutive "blocked" frames before triggering a call)
- Decides call type and generates a natural-language call script based on context
- Triggers the phone call service

### 4. Phone Call Agent (`caller.py`)
- Creates an AgentPhone agent at startup with a system prompt scoped to the current ride:
  - "You are the voice assistant for an autonomous vehicle. The passenger is [name]. You are calling to inform them: [event context]. Answer their questions briefly and clearly."
- Triggers outbound calls via `POST /v1/calls` with `agentId` + `toNumber`
- AgentPhone handles all TTS (speaking) and STT (transcribing) automatically

### 5. Webhook Server (`webhook.py`)
- Flask server receiving `agent.message` events from AgentPhone
- On each voice turn, the passenger's transcript arrives; the server generates a reply via the VLM/LLM and returns `{"text": "..."}` — AgentPhone TTS's it back
- On `agent.call_ended`, logs the outcome and feeds the passenger's decision (wait/reroute/cancel) back to the agent state machine

### 6. Orchestrator (`main.py`)
- Ties all components together via asyncio
- Manages lifecycle: start sim, open VLM session, run agent loop, handle shutdown

---

## Trigger Events & Call Scripts

| Event | Trigger Condition | Call Script |
|---|---|---|
| **Arrived** | VLM detects destination reached | "Your ride has arrived. I'm outside [location]." |
| **Blocked** | Obstacle detected for 3+ seconds | "I'm blocked by [obstacle]. Estimated delay: [N] min. Press 1 to wait, 2 to cancel." |
| **Hazard** | Unsafe road condition | "I've detected a road hazard and stopped for safety. [description]. I'll resume shortly." |
| **Rerouting** | Route deviation required | "Taking an alternate route due to [reason]. New ETA: [N] min." |

---

## Implementation Order

1. **[P0] CARLA setup** — get simulator running, attach camera, verify frame capture
2. **[P0] Gemini Live session** — open stream, send test frames, parse structured events
3. **[P0] AgentPhone agent** — create agent via API, trigger a test outbound call
4. **[P0] Webhook server** — Flask endpoint receiving `agent.message`, returning `{"text": ...}`
5. **[P1] Agent state machine** — wire VLM events to AgentPhone call triggers
6. **[P1] Dynamic system prompts** — build per-event prompts from VLM context strings
7. **[P1] Passenger decision loop** — webhook feeds "wait/cancel/reroute" back to state machine
8. **[P2] Demo scenario** — pre-scripted CARLA route with blockage + arrival events
9. **[P2] Dashboard** — simple terminal UI showing current VLM state + call log

---

## Demo Flow (for judging)

1. CARLA car starts driving toward a destination
2. Gemini Live watches the camera feed in real time
3. A parked vehicle blocks the road → agent calls passenger: "I'm blocked, want to wait?"
4. Passenger presses 1 → car waits, obstacle clears, car resumes
5. Car arrives → agent calls passenger: "I'm here, come outside"
6. Judges see: live sim window + terminal showing VLM events + actual phone ringing

---

## Key Files

```
omega/
├── main.py          # orchestrator
├── capture.py       # CARLA frame capture
├── vlm.py           # Gemini Live session
├── agent.py         # state machine + call trigger logic
├── caller.py        # AgentPhone outbound call trigger
├── webhook.py       # Flask server for AgentPhone voice events
├── config.py        # API keys, phone numbers, sim settings
├── requirements.txt
└── PLAN.md          # this file
```

---

## Environment Variables Needed

```
GOOGLE_API_KEY=
AGENTPHONE_API_KEY=              # ap_...
AGENTPHONE_AGENT_ID=             # created once at startup
AGENTPHONE_WEBHOOK_SECRET=       # for signature verification
PASSENGER_PHONE_NUMBER=
CARLA_HOST=localhost
CARLA_PORT=2000
WEBHOOK_PORT=3000                # Flask port (expose via ngrok for AgentPhone)
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Gemini Live rate limits on frames | Throttle to 5 fps, send keyframes only on scene change |
| CARLA not available | Fallback: replay a recorded frame sequence from disk |
| AgentPhone webhook not reachable locally | Run `ngrok http 3000` to expose Flask server during demo |
| VLM hallucinations on triggers | Require N consecutive matching frames before calling |
| AgentPhone agent responds off-script | Tightly scope system prompt per event type; keep it brief |
