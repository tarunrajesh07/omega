"""Scenario overlays for deterministic hackathon demos."""

from __future__ import annotations

import json
from pathlib import Path
import logging
from typing import AsyncIterator, Protocol

from config import Settings
from models import EventType, Frame, VisionEvent

logger = logging.getLogger(__name__)


class VisionAnalyzer(Protocol):
    async def analyze_frame(self, frame: Frame) -> VisionEvent:
        ...


def scenario_enabled(settings: Settings) -> bool:
    return settings.scenario.strip().lower() not in {"", "live", "none"}


async def scenario_events(
    settings: Settings,
    frames: AsyncIterator[Frame],
    vision: VisionAnalyzer | None = None,
) -> AsyncIterator[VisionEvent]:
    scenario = settings.scenario.strip().lower()
    if scenario == "arrival_landmark":
        async for event in _arrival_landmark_from_frames(settings, frames, vision):
            yield event
        return

    raise ValueError(f"Unknown SCENARIO={settings.scenario!r}")


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
        if seen <= settings.scenario_warmup_frames or not _scenario_arrived(settings.scenario_state_file, settings.scenario_run_id):
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


def _scenario_arrived(path: str, run_id: str = "") -> bool:
    state_path = Path(path)
    if not state_path.exists():
        return False
    try:
        payload = json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return False
    if run_id and payload.get("run_id") != run_id:
        return False
    return payload.get("status") == "arrived"


async def _arrival_landmark_from_frames(
    settings: Settings,
    frames: AsyncIterator[Frame],
    vision: VisionAnalyzer | None,
) -> AsyncIterator[VisionEvent]:
    seen = 0
    did_arrival_vlm_check = False
    latest_vlm_event: VisionEvent | None = None
    landmark = settings.landmark_label or "the main entrance landmark"
    destination = settings.destination_label
    interval = max(settings.scenario_vlm_interval_frames, 1)
    async for frame in frames:
        seen += 1
        arrived = _scenario_arrived(settings.scenario_state_file, settings.scenario_run_id)
        should_sample_vlm = vision is not None and (seen % interval == 0 or (arrived and not did_arrival_vlm_check))
        if should_sample_vlm:
            latest_vlm_event = await _safe_analyze(vision, frame)
            if arrived:
                did_arrival_vlm_check = True

        if seen <= settings.scenario_warmup_frames or not arrived:
            vlm_suffix = f" VLM says: {latest_vlm_event.reason}" if latest_vlm_event else ""
            yield VisionEvent(
                event_type=EventType.EN_ROUTE,
                reason=f"Driving toward {destination}; landmark target: {landmark}.{vlm_suffix}",
                confidence=0.9,
            )
            continue

        visual_context = f" Visual context: {latest_vlm_event.reason}" if latest_vlm_event else ""
        yield VisionEvent(
            event_type=EventType.ARRIVED,
            reason=f"Arrived at {destination}, next to {landmark}.{visual_context}",
            confidence=0.98,
            eta_minutes=0,
            raw={"scenario": "arrival_landmark", "vlm_event": latest_vlm_event.raw if latest_vlm_event else None},
        )


async def _safe_analyze(vision: VisionAnalyzer, frame: Frame) -> VisionEvent | None:
    try:
        event = await vision.analyze_frame(frame)
    except Exception as exc:
        logger.warning("Scenario VLM sample failed: %s", exc)
        return None
    logger.info("Scenario VLM sample event=%s reason=%s", event.event_type.value, event.reason)
    return event
