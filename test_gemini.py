"""Gemini-only smoke test for text and optional CARLA/demo image analysis."""

from __future__ import annotations

import argparse
import asyncio
import logging

from google import genai

from capture import FrameCaptureService
from config import Settings, settings
from frame_store import LatestFrameStore
from vlm import GeminiLiveVision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gemini text and vision diagnostics only")
    parser.add_argument("--text-only", action="store_true", help="Only run a simple text generateContent request")
    parser.add_argument("--use-demo-frame", action="store_true", help="Use a generated frame instead of CARLA for the vision check")
    parser.add_argument("--model", default=settings.llm_reply_model)
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing")

    print(_key_summary(settings.google_api_key))
    _run_text_check(settings.google_api_key, args.model)

    if args.text_only:
        return

    active_settings = Settings(demo_mode=args.use_demo_frame, llm_reply_model=args.model)
    frame = await _capture_one_frame(active_settings)
    event = await GeminiLiveVision(active_settings).analyze_frame(frame)
    print(f"vision_source={event.raw.get('source')} event={event.event_type.value} confidence={event.confidence:.2f}")
    print(f"vision_reason={event.reason}")
    if event.raw.get("source") != "gemini":
        raise RuntimeError("Vision test did not use Gemini; it used fallback/scripted analysis")


def _key_summary(key: str) -> str:
    return (
        f"key_loaded=True length={len(key)} starts_with_AIza={key.startswith('AIza')} "
        f"contains_hash={'#' in key} contains_space={any(ch.isspace() for ch in key)} "
        f"masked={key[:6]}...{key[-4:]}"
    )


def _run_text_check(api_key: str, model: str) -> None:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents="Reply with only: ok")
    text = (response.text or "").strip()
    print(f"text_model={model} response={text!r}")
    if text.lower() != "ok":
        raise RuntimeError(f"Unexpected Gemini text response: {text!r}")


async def _capture_one_frame(settings: Settings):
    store = LatestFrameStore()
    capture = FrameCaptureService(settings, frame_store=store)
    try:
        async for frame in capture.frames():
            print(f"frame_source={frame.source} sequence={frame.sequence} bytes={frame.size_bytes}")
            return frame
    finally:
        capture.close()
    raise RuntimeError("No frame captured")


if __name__ == "__main__":
    asyncio.run(main())
