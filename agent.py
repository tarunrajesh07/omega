"""Autonomous vehicle event state machine and call trigger logic."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncIterator, Deque

from caller import AgentPhoneCaller, build_system_prompt
from config import Settings
from models import CallRequest, EventType, PassengerDecision, RideState, VisionEvent

logger = logging.getLogger(__name__)


CALLABLE_EVENTS = {EventType.ARRIVED, EventType.BLOCKED, EventType.HAZARD, EventType.REROUTING}


@dataclass
class RideAgent:
    settings: Settings
    caller: AgentPhoneCaller
    state: RideState = RideState.IDLE
    last_event: VisionEvent | None = None
    call_log: list[str] = field(default_factory=list)
    _recent_events: Deque[EventType] = field(default_factory=lambda: deque(maxlen=6))
    _last_call_by_event: dict[EventType, float] = field(default_factory=dict)
    _called_events: set[EventType] = field(default_factory=set)
    _active_call_id: str | None = None
    _active_call_started_at: float | None = None
    _last_passenger_decision: str | None = None
    _demo_reroute_timeout_task: asyncio.Task[None] | None = None

    async def run(self, events: AsyncIterator[VisionEvent]) -> None:
        self.state = RideState.EN_ROUTE
        async for event in events:
            await self.handle_event(event)

    async def handle_event(self, event: VisionEvent) -> None:
        self.last_event = event
        self._recent_events.append(event.event_type)
        logger.info("VLM event=%s confidence=%.2f reason=%s", event.event_type, event.confidence, event.reason)

        if event.event_type == EventType.EN_ROUTE:
            if self.state not in {RideState.ARRIVED, RideState.CANCELLED}:
                self.state = RideState.EN_ROUTE
            return

        if event.event_type not in CALLABLE_EVENTS:
            return

        if not self._is_debounced(event.event_type):
            return

        self._transition(event.event_type)
        if self._already_called(event.event_type):
            logger.info("Skipping %s call because it was already attempted this run", event.event_type.value)
            return
        if self._call_in_progress():
            logger.info("Skipping %s call because call %s is still active", event.event_type.value, self._active_call_id or "<unknown>")
            return
        if not self._cooldown_elapsed(event.event_type):
            return

        request = self._build_call_request(event)
        result = await self.caller.call(request)
        now = time.monotonic()
        self._last_call_by_event[event.event_type] = now
        if result.attempted:
            self._called_events.add(event.event_type)
        if result.attempted:
            self._active_call_id = result.call_id or f"{event.event_type.value}-{int(now)}"
            self._active_call_started_at = now
            self._schedule_demo_reroute_timeout(event)
        self.call_log.append(f"{event.event_type.value}: {request.script} ({result.message})")

    def mark_call_ended(self, call_id: str | None = None) -> None:
        if call_id and self._active_call_id and call_id != self._active_call_id:
            logger.info("Ignoring call-ended event for %s; active call is %s", call_id, self._active_call_id)
            return
        logger.info("Call ended: %s", call_id or self._active_call_id or "<unknown>")
        self._active_call_id = None
        self._active_call_started_at = None
        if self.settings.scenario.strip().lower() == "reroute_request" and self._last_passenger_decision is None:
            logger.info("Demo 2 call ended without a transcript decision; defaulting to reroute")
            self._last_passenger_decision = "reroute"
            self.state = RideState.REROUTING
            self._request_scenario_reroute()

    def apply_passenger_decision(self, decision: PassengerDecision) -> None:
        normalized = decision.action.lower().strip()
        self._last_passenger_decision = normalized
        logger.info("Passenger decision=%s transcript=%s", normalized, decision.transcript)
        if normalized == "cancel":
            self.state = RideState.CANCELLED
        elif normalized == "reroute":
            self.state = RideState.REROUTING
            self._request_scenario_reroute()
        elif normalized == "wait":
            self.state = RideState.BLOCKED
        elif normalized == "resume":
            self.state = RideState.EN_ROUTE

    def _schedule_demo_reroute_timeout(self, event: VisionEvent) -> None:
        if self.settings.scenario.strip().lower() != "reroute_request":
            return
        if event.raw.get("scenario") != "reroute_request":
            return
        if self._demo_reroute_timeout_task and not self._demo_reroute_timeout_task.done():
            return
        timeout = max(self.settings.demo_reroute_timeout_seconds, 0.0)
        logger.info("Demo 2 reroute fallback scheduled in %.1f seconds", timeout)
        self._demo_reroute_timeout_task = asyncio.create_task(self._demo_reroute_after_timeout(timeout))

    async def _demo_reroute_after_timeout(self, timeout: float) -> None:
        await asyncio.sleep(timeout)
        if self.settings.scenario.strip().lower() != "reroute_request":
            return
        if self._last_passenger_decision is not None:
            logger.info("Demo 2 reroute timeout skipped; passenger decision=%s", self._last_passenger_decision)
            return
        logger.info("Demo 2 reroute timeout elapsed; defaulting to reroute")
        self._last_passenger_decision = "reroute"
        self.state = RideState.REROUTING
        self._request_scenario_reroute()

    def _request_scenario_reroute(self) -> None:
        if self.settings.scenario.strip().lower() != "reroute_request":
            return
        path = Path(self.settings.scenario_state_file)
        payload = {}
        if path.exists():
            try:
                payload = json.loads(path.read_text())
            except json.JSONDecodeError:
                payload = {}
        payload.update(
            {
                "status": "reroute_requested",
                "command": "reroute",
                "run_id": self.settings.scenario_run_id,
                "updated_at": time.time(),
            },
        )
        path.write_text(json.dumps(payload))
        logger.info("Scenario reroute command written to %s", path)

    def _is_debounced(self, event_type: EventType) -> bool:
        threshold = {
            EventType.BLOCKED: self.settings.blocked_threshold,
            EventType.ARRIVED: self.settings.arrived_threshold,
            EventType.HAZARD: self.settings.hazard_threshold,
            EventType.REROUTING: self.settings.rerouting_threshold,
        }.get(event_type, 1)
        recent = list(self._recent_events)[-threshold:]
        return len(recent) == threshold and all(item == event_type for item in recent)

    def _already_called(self, event_type: EventType) -> bool:
        return event_type in self._called_events

    def _call_in_progress(self) -> bool:
        if self._active_call_started_at is None:
            return False
        elapsed = time.monotonic() - self._active_call_started_at
        if elapsed >= self.settings.active_call_timeout_seconds:
            logger.warning("Clearing stale active call %s after %.1f seconds", self._active_call_id or "<unknown>", elapsed)
            self._active_call_id = None
            self._active_call_started_at = None
            return False
        return True

    def _cooldown_elapsed(self, event_type: EventType) -> bool:
        last_call = self._last_call_by_event.get(event_type)
        if last_call is None:
            return True
        return (time.monotonic() - last_call) >= self.settings.call_cooldown_seconds

    def _transition(self, event_type: EventType) -> None:
        if event_type == EventType.BLOCKED:
            self.state = RideState.BLOCKED
        elif event_type == EventType.HAZARD:
            self.state = RideState.HAZARD
        elif event_type == EventType.REROUTING:
            self.state = RideState.REROUTING
        elif event_type == EventType.ARRIVED:
            self.state = RideState.ARRIVED

    def _build_call_request(self, event: VisionEvent) -> CallRequest:
        context = self._context(event)
        script = self._script(event)
        request = CallRequest(
            event_type=event.event_type,
            script=script,
            context=context,
            system_prompt="",
            passenger_name=self.settings.passenger_name,
            to_number=self.settings.passenger_phone_number,
        )
        return CallRequest(
            event_type=request.event_type,
            script=request.script,
            context=request.context,
            system_prompt=build_system_prompt(request),
            passenger_name=request.passenger_name,
            to_number=request.to_number,
        )

    def _context(self, event: VisionEvent) -> str:
        pieces = [event.reason]
        if event.obstacle:
            pieces.append(f"Obstacle: {event.obstacle}.")
        if event.eta_minutes is not None:
            pieces.append(f"ETA impact: {event.eta_minutes} minutes.")
        return " ".join(pieces)

    def _script(self, event: VisionEvent) -> str:
        eta = event.eta_minutes if event.eta_minutes is not None else 3
        if event.event_type == EventType.ARRIVED:
            return f"Your ride has arrived. {event.reason}"
        if event.event_type == EventType.BLOCKED:
            if event.raw.get("scenario") == "reroute_request":
                return f"I've arrived at {self.settings.destination_label}. I'm waiting here now."
            obstacle = event.obstacle or "an obstacle"
            return f"I'm blocked by {obstacle}. Estimated delay: {eta} minutes. Say wait, reroute, or cancel."
        if event.event_type == EventType.HAZARD:
            return f"I've detected a road hazard and stopped for safety. {event.reason} I'll resume shortly."
        if event.event_type == EventType.REROUTING:
            return f"Taking an alternate route due to {event.reason}. New ETA: {eta} minutes."
        return event.reason


async def drain_events(agent: RideAgent, events: AsyncIterator[VisionEvent]) -> None:
    await agent.run(events)
