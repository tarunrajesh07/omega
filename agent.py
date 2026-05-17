"""Autonomous vehicle event state machine and call trigger logic."""

from __future__ import annotations

import asyncio
import logging
import time
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
        if not self._cooldown_elapsed(event.event_type):
            return

        request = self._build_call_request(event)
        result = await self.caller.call(request)
        self._last_call_by_event[event.event_type] = time.monotonic()
        self.call_log.append(f"{event.event_type.value}: {request.script} ({result.message})")

    def apply_passenger_decision(self, decision: PassengerDecision) -> None:
        normalized = decision.action.lower().strip()
        logger.info("Passenger decision=%s transcript=%s", normalized, decision.transcript)
        if normalized == "cancel":
            self.state = RideState.CANCELLED
        elif normalized == "reroute":
            self.state = RideState.REROUTING
        elif normalized == "wait":
            self.state = RideState.BLOCKED
        elif normalized == "resume":
            self.state = RideState.EN_ROUTE

    def _is_debounced(self, event_type: EventType) -> bool:
        threshold = {
            EventType.BLOCKED: self.settings.blocked_threshold,
            EventType.ARRIVED: self.settings.arrived_threshold,
            EventType.HAZARD: self.settings.hazard_threshold,
            EventType.REROUTING: self.settings.rerouting_threshold,
        }.get(event_type, 1)
        recent = list(self._recent_events)[-threshold:]
        return len(recent) == threshold and all(item == event_type for item in recent)

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
            landmark = f", near {self.settings.landmark_label}" if self.settings.landmark_label else ""
            return f"Your ride has arrived. I'm outside {self.settings.destination_label}{landmark}."
        if event.event_type == EventType.BLOCKED:
            obstacle = event.obstacle or "an obstacle"
            return f"I'm blocked by {obstacle}. Estimated delay: {eta} minutes. Say wait, reroute, or cancel."
        if event.event_type == EventType.HAZARD:
            return f"I've detected a road hazard and stopped for safety. {event.reason} I'll resume shortly."
        if event.event_type == EventType.REROUTING:
            return f"Taking an alternate route due to {event.reason}. New ETA: {eta} minutes."
        return event.reason


async def drain_events(agent: RideAgent, events: AsyncIterator[VisionEvent]) -> None:
    await agent.run(events)
