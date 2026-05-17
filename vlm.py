"""Vision-language analysis for camera frames."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import AsyncIterator

from config import Settings
from models import EventType, Frame, SceneDescription, VisionEvent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are the vision system for an autonomous vehicle. Analyze the latest front-camera frame.
Return only JSON with these fields:
{
  "event": "en_route" | "arrived" | "blocked" | "hazard" | "rerouting",
  "reason": "one short plain-English reason",
  "confidence": 0.0-1.0,
  "obstacle": "short obstacle description or null",
  "eta_minutes": integer or null
}
Trigger blocked only for a physical obstruction in the lane, arrived only when the destination is visible/reached,
hazard only for unsafe road conditions, and rerouting only when the current route is unusable.
""".strip()

SCENE_PROMPT = """
You are describing a pickup location to a passenger using the autonomous vehicle front-camera frame.
Focus on what the passenger can use to find the vehicle right now: visible buildings, storefronts, curb position, road layout, signs, colors, nearby objects, and whether the car is stopped at a pickup spot.
Do not describe generic driving state unless it helps the passenger locate the car.
Do not invent a landmark that is not visible. If a requested landmark is not visible, say what is visible instead.
Return only JSON with these fields:
{
  "summary": "one natural passenger-facing sentence describing where the car is",
  "pickup_cue": "short practical cue for finding the car or null",
  "visible_landmark": "most recognizable visible landmark/object/building or null",
  "confidence": 0.0-1.0
}
""".strip()


class GeminiLiveVision:
    """Analyzes frames with Gemini when configured, otherwise uses a scripted demo classifier."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    async def analyze_stream(self, frames: AsyncIterator[Frame]) -> AsyncIterator[VisionEvent]:
        async for frame in frames:
            yield await self.analyze_frame(frame)

    async def analyze_frame(self, frame: Frame) -> VisionEvent:
        if not self.settings.google_api_key or frame.source == "demo":
            return self._scripted_event(frame.sequence)

        try:
            return await self._analyze_with_gemini(frame)
        except Exception as exc:
            logger.warning("Gemini analysis failed (%s); using scripted fallback", exc)
            return self._scripted_event(frame.sequence)

    async def describe_pickup_scene(self, frame: Frame) -> SceneDescription:
        if not self.settings.google_api_key or frame.source == "demo":
            return SceneDescription(
                summary="The vehicle is stopped near the destination entrance.",
                pickup_cue="Look for the vehicle at the curb near the entrance.",
                visible_landmark=None,
                confidence=0.6,
                raw={"source": "scripted"},
            )

        try:
            return await self._describe_pickup_scene_with_gemini(frame)
        except Exception as exc:
            logger.warning("Gemini scene description failed (%s); using scripted fallback", exc)
            return SceneDescription(
                summary="The vehicle is stopped near the destination entrance.",
                pickup_cue="Look for the vehicle at the curb near the entrance.",
                visible_landmark=None,
                confidence=0.6,
                raw={"source": "scripted"},
            )

    async def _describe_pickup_scene_with_gemini(self, frame: Frame) -> SceneDescription:
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(api_key=self.settings.google_api_key)

        image_part = types.Part.from_bytes(data=frame.jpeg_bytes, mime_type="image/jpeg")
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self.settings.llm_reply_model,
            contents=[SCENE_PROMPT, image_part],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        payload = _extract_json(response.text or "{}")
        payload.setdefault("source", "gemini")
        return SceneDescription.from_payload(payload)

    async def _analyze_with_gemini(self, frame: Frame) -> VisionEvent:
        """Uses the Google GenAI SDK. Falls back cleanly if the SDK/API is unavailable."""
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(api_key=self.settings.google_api_key)

        image_part = types.Part.from_bytes(data=frame.jpeg_bytes, mime_type="image/jpeg")
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self.settings.llm_reply_model,
            contents=[SYSTEM_PROMPT, image_part],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        payload = _extract_json(response.text or "{}")
        payload.setdefault("source", "gemini")
        return VisionEvent.from_payload(payload)

    def _scripted_event(self, sequence: int) -> VisionEvent:
        if 8 <= sequence < 22:
            return VisionEvent(
                event_type=EventType.BLOCKED,
                reason="A parked vehicle is blocking the lane ahead.",
                confidence=0.92,
                obstacle="parked vehicle",
                eta_minutes=4,
                raw={"source": "scripted"},
            )
        if 28 <= sequence < 34:
            return VisionEvent(
                event_type=EventType.REROUTING,
                reason="The vehicle is taking a short alternate approach to the destination.",
                confidence=0.76,
                eta_minutes=2,
                raw={"source": "scripted"},
            )
        if sequence >= 34:
            return VisionEvent(
                event_type=EventType.ARRIVED,
                reason="The destination entrance is visible and the vehicle has stopped outside.",
                confidence=0.96,
                eta_minutes=0,
                raw={"source": "scripted"},
            )
        return VisionEvent(
            event_type=EventType.EN_ROUTE,
            reason="The lane ahead is clear and the vehicle is progressing normally.",
            confidence=0.88,
            raw={"source": "scripted"},
        )


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def frame_to_base64(frame: Frame) -> str:
    return base64.b64encode(frame.jpeg_bytes).decode("ascii")

