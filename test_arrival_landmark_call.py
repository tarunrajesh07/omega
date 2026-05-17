"""One-shot arrival landmark test: Gemini frame analysis, then AgentPhone call."""

from __future__ import annotations

import argparse
import asyncio
import logging

from caller import AgentPhoneCaller, build_system_prompt
from capture import FrameCaptureService
from config import Settings, settings
from frame_store import LatestFrameStore
from models import CallRequest, EventType, Frame
from vlm import GeminiLiveVision


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one arrival-landmark Gemini + AgentPhone call test")
    parser.add_argument("--to", dest="to_number", help="Override PASSENGER_PHONE_NUMBER")
    parser.add_argument("--destination", default=settings.destination_label)
    parser.add_argument("--landmark", default=settings.landmark_label or "the nearby landmark")
    parser.add_argument("--passenger-name", default=settings.passenger_name)
    parser.add_argument("--use-demo-frame", action="store_true", help="Use generated demo frame instead of CARLA")
    parser.add_argument("--require-gemini", action="store_true", help="Fail if GOOGLE_API_KEY is missing or Gemini falls back")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    active_settings = Settings(
        demo_mode=args.use_demo_frame,
        destination_label=args.destination,
        landmark_label=args.landmark,
        passenger_name=args.passenger_name,
        passenger_phone_number=args.to_number or settings.passenger_phone_number,
    )

    if args.require_gemini and active_settings.missing_for_gemini():
        raise RuntimeError("--require-gemini was set, but GOOGLE_API_KEY is missing")

    frame = await _capture_one_frame(active_settings)
    vision = GeminiLiveVision(active_settings)
    vision_event = await vision.analyze_frame(frame)
    if args.require_gemini and vision_event.raw.get("source") == "scripted":
        raise RuntimeError(f"--require-gemini was set, but Gemini used scripted fallback: {vision_event.reason}")
    logger.info("Gemini event=%s confidence=%.2f reason=%s", vision_event.event_type.value, vision_event.confidence, vision_event.reason)

    visual_context = vision_event.reason
    script = (
        f"Your ride has arrived. I'm outside {active_settings.destination_label}, "
        f"near {active_settings.landmark_label}. I can see: {visual_context}"
    )
    context = (
        f"Arrival landmark test. Destination: {active_settings.destination_label}. "
        f"Landmark: {active_settings.landmark_label}. Gemini visual context: {visual_context}"
    )
    request = CallRequest(
        event_type=EventType.ARRIVED,
        script=script,
        context=context,
        system_prompt="",
        passenger_name=active_settings.passenger_name,
        to_number=active_settings.passenger_phone_number,
    )
    request = CallRequest(
        event_type=request.event_type,
        script=request.script,
        context=request.context,
        system_prompt=build_system_prompt(request),
        passenger_name=request.passenger_name,
        to_number=request.to_number,
    )

    logger.info("Calling %s with greeting: %s", request.to_number or "<missing number>", request.script)
    logger.info("AgentPhone system prompt: %s", request.system_prompt)
    result = await AgentPhoneCaller(active_settings).call(request)
    logger.info("Call result attempted=%s call_id=%s message=%s", result.attempted, result.call_id, result.message)


async def _capture_one_frame(settings: Settings) -> Frame:
    store = LatestFrameStore()
    capture = FrameCaptureService(settings, frame_store=store)
    try:
        async for frame in capture.frames():
            logger.info("Captured frame source=%s sequence=%s bytes=%s", frame.source, frame.sequence, frame.size_bytes)
            return frame
    finally:
        capture.close()
    raise RuntimeError("No frame captured")


if __name__ == "__main__":
    asyncio.run(main())

