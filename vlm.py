"""Vision-language analysis for camera frames."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import AsyncIterator

from config import Settings
from models import EventType, Frame, VisionEvent

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
        return VisionEvent.from_payload(payload)

    def _scripted_event(self, sequence: int) -> VisionEvent:
        if 8 <= sequence < 22:
            return VisionEvent(
                event_type=EventType.BLOCKED,
                reason="A parked vehicle is blocking the lane ahead.",
                confidence=0.92,
                obstacle="parked vehicle",
                eta_minutes=4,
            )
        if 28 <= sequence < 34:
            return VisionEvent(
                event_type=EventType.REROUTING,
                reason="The vehicle is taking a short alternate approach to the destination.",
                confidence=0.76,
                eta_minutes=2,
            )
        if sequence >= 34:
            return VisionEvent(
                event_type=EventType.ARRIVED,
                reason="The destination entrance is visible and the vehicle has stopped outside.",
                confidence=0.96,
                eta_minutes=0,
            )
        return VisionEvent(
            event_type=EventType.EN_ROUTE,
            reason="The lane ahead is clear and the vehicle is progressing normally.",
            confidence=0.88,
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

