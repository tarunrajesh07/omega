"""Scenario overlays for deterministic hackathon demos."""

from __future__ import annotations

import json
from pathlib import Path
import logging
from typing import AsyncIterator, Protocol

from config import Settings
from models import EventType, Frame, SceneDescription, VisionEvent

logger = logging.getLogger(__name__)


class VisionAnalyzer(Protocol):
    async def analyze_frame(self, frame: Frame) -> VisionEvent:
        ...

    async def describe_pickup_scene(self, frame: Frame) -> SceneDescription:
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

    if scenario == "reroute_request":
        async for event in _reroute_request_from_frames(settings, frames, vision):
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
    payload = _scenario_state(path, run_id)
    return bool(payload and payload.get("status") == "arrived")


def _scenario_state(path: str, run_id: str = "") -> dict | None:
    state_path = Path(path)
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return None
    if run_id and payload.get("run_id") != run_id:
        return None
    return payload


async def _reroute_request_from_frames(
    settings: Settings,
    frames: AsyncIterator[Frame],
    vision: VisionAnalyzer | None,
) -> AsyncIterator[VisionEvent]:
    seen = 0
    call_event_count = 0
    did_reroute_notice = False
    did_final_arrival = False
    latest_scene: SceneDescription | None = None
    did_initial_scene_check = False
    async for frame in frames:
        seen += 1
        state = _scenario_state(settings.scenario_state_file, settings.scenario_run_id)
        status = state.get("status") if state else None

        if status == "arrived" and call_event_count < settings.blocked_threshold and seen > settings.scenario_warmup_frames:
            if vision is not None and not did_initial_scene_check:
                latest_scene = await _safe_describe_pickup_scene(vision, frame)
                did_initial_scene_check = True

            if latest_scene is None or (latest_scene.raw.get("source") != "gemini" and not settings.allow_scripted_vlm_calls):
                reason = "Arrived at pickup location, but waiting for a real Gemini pickup-scene description before calling."
                if latest_scene:
                    reason += f" Latest fallback scene: {latest_scene.summary}"
                yield VisionEvent(
                    event_type=EventType.EN_ROUTE,
                    reason=reason,
                    confidence=0.7,
                    raw={"scenario": "reroute_request", "waiting_for_scene_description": True, "status": status},
                )
                continue

            call_event_count += 1
            scene_text = _scene_call_text(latest_scene)
            yield VisionEvent(
                event_type=EventType.BLOCKED,
                reason=(
                    f"Stopped at {settings.destination_label}. {scene_text}"
                ),
                confidence=0.99,
                obstacle="waiting for passenger reroute request",
                eta_minutes=2,
                raw={
                    "scenario": "reroute_request",
                    "stop_status": status,
                    "call_event_count": call_event_count,
                    "scene": latest_scene.raw,
                    "used_real_vlm": latest_scene.raw.get("source") == "gemini",
                },
            )
            continue

        if status == "rerouting" and not did_reroute_notice:
            did_reroute_notice = True
            yield VisionEvent(
                event_type=EventType.EN_ROUTE,
                reason=f"Passenger requested reroute. Driving toward {settings.reroute_destination_label}.",
                confidence=0.95,
                raw={"scenario": "reroute_request", "status": status},
            )
            continue

        if status == "reroute_arrived" and not did_final_arrival:
            did_final_arrival = True
            yield VisionEvent(
                event_type=EventType.ARRIVED,
                reason=f"Arrived at the rerouted destination: {settings.reroute_destination_label}.",
                confidence=0.98,
                eta_minutes=0,
                raw={"scenario": "reroute_request", "status": status},
            )
            continue

        yield VisionEvent(
            event_type=EventType.EN_ROUTE,
            reason=f"Demo 2 route status={status or 'waiting'} toward {settings.destination_label}.",
            confidence=0.9,
            raw={"scenario": "reroute_request", "status": status},
        )



async def _arrival_landmark_from_frames(
    settings: Settings,
    frames: AsyncIterator[Frame],
    vision: VisionAnalyzer | None,
) -> AsyncIterator[VisionEvent]:
    seen = 0
    did_arrival_vlm_check = False
    latest_vlm_event: VisionEvent | None = None
    latest_scene: SceneDescription | None = None
    landmark = settings.landmark_label or "the main entrance landmark"
    destination = settings.destination_label
    interval = max(settings.scenario_vlm_interval_frames, 1)
    async for frame in frames:
        seen += 1
        arrived = _scenario_arrived(settings.scenario_state_file, settings.scenario_run_id)
        should_sample_vlm = vision is not None and not arrived and seen % interval == 0
        if should_sample_vlm:
            latest_vlm_event = await _safe_analyze(vision, frame)

        if arrived and vision is not None and not did_arrival_vlm_check:
            latest_scene = await _safe_describe_pickup_scene(vision, frame)
            did_arrival_vlm_check = True

        if seen <= settings.scenario_warmup_frames or not arrived:
            vlm_suffix = f" VLM says: {latest_vlm_event.reason}" if latest_vlm_event else ""
            yield VisionEvent(
                event_type=EventType.EN_ROUTE,
                reason=f"Driving toward {destination}; landmark target: {landmark}.{vlm_suffix}",
                confidence=0.9,
            )
            continue

        if latest_scene is None or (latest_scene.raw.get("source") != "gemini" and not settings.allow_scripted_vlm_calls):
            reason = "Arrived at destination, but waiting for a real Gemini pickup-scene description before calling."
            if latest_scene:
                reason += f" Latest fallback scene: {latest_scene.summary}"
            yield VisionEvent(
                event_type=EventType.EN_ROUTE,
                reason=reason,
                confidence=0.7,
                raw={"scenario": "arrival_landmark", "waiting_for_scene_description": True},
            )
            continue

        scene_text = _scene_call_text(latest_scene)
        yield VisionEvent(
            event_type=EventType.ARRIVED,
            reason=f"Arrived at {destination}. {scene_text}",
            confidence=latest_scene.confidence or 0.98,
            eta_minutes=0,
            raw={
                "scenario": "arrival_landmark",
                "scene": latest_scene.raw,
                "configured_landmark": landmark,
                "used_real_vlm": latest_scene.raw.get("source") == "gemini",
            },
        )


def _scene_call_text(scene: SceneDescription) -> str:
    pieces = [scene.summary.rstrip(".")]
    if scene.visible_landmark:
        pieces.append(f"Visible landmark: {scene.visible_landmark.rstrip('.')}")
    if scene.pickup_cue:
        pieces.append(f"Pickup cue: {scene.pickup_cue.rstrip('.')}")
    return ". ".join(piece for piece in pieces if piece) + "."


async def _safe_analyze(vision: VisionAnalyzer, frame: Frame) -> VisionEvent | None:
    try:
        event = await vision.analyze_frame(frame)
    except Exception as exc:
        logger.warning("Scenario VLM sample failed: %s", exc)
        return None
    logger.info("Scenario VLM sample event=%s reason=%s", event.event_type.value, event.reason)
    return event


async def _safe_describe_pickup_scene(vision: VisionAnalyzer, frame: Frame) -> SceneDescription | None:
    try:
        scene = await vision.describe_pickup_scene(frame)
    except Exception as exc:
        logger.warning("Scenario pickup-scene description failed: %s", exc)
        return None
    logger.info(
        "Scenario pickup scene source=%s summary=%s pickup_cue=%s landmark=%s",
        scene.raw.get("source"),
        scene.summary,
        scene.pickup_cue,
        scene.visible_landmark,
    )
    return scene
