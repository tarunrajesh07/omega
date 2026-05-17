"""Scenario overlays for deterministic hackathon demos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

from config import Settings
from models import EventType, VisionEvent


async def apply_scenario(settings: Settings, events: AsyncIterator[VisionEvent]) -> AsyncIterator[VisionEvent]:
    scenario = settings.scenario.strip().lower()
    if scenario in {"", "live", "none"}:
        async for event in events:
            yield event
        return

    if scenario == "arrival_landmark":
        async for event in _arrival_landmark(settings, events):
            yield event
        return

    raise ValueError(f"Unknown SCENARIO={settings.scenario!r}")


async def _arrival_landmark(settings: Settings, events: AsyncIterator[VisionEvent]) -> AsyncIterator[VisionEvent]:
    seen = 0
    landmark = settings.landmark_label or "the main entrance landmark"
    destination = settings.destination_label
    async for event in events:
        seen += 1
        if seen <= settings.scenario_warmup_frames or not _scenario_arrived(settings.scenario_state_file):
            yield VisionEvent(
                event_type=EventType.EN_ROUTE,
                reason=f"Driving toward {destination}; landmark target: {landmark}.",
                confidence=0.9,
            )
            continue

        yield VisionEvent(
            event_type=EventType.ARRIVED,
            reason=f"Arrived at {destination}, next to {landmark}.",
            confidence=0.98,
            eta_minutes=0,
            raw={"scenario": "arrival_landmark", "source_event": event.raw},
        )


def _scenario_arrived(path: str) -> bool:
    state_path = Path(path)
    if not state_path.exists():
        return False
    try:
        payload = json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return False
    return payload.get("status") == "arrived"
