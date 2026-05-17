"""Omega orchestrator: capture frames, analyze them, and trigger passenger calls."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import threading
from contextlib import suppress

from agent import RideAgent
from caller import AgentPhoneCaller
from capture import FrameCaptureService
from config import Settings, settings
from frame_store import LatestFrameStore
from scenarios import apply_scenario, scenario_enabled, scenario_events
from vlm import GeminiLiveVision
from webhook import create_app

logger = logging.getLogger(__name__)


async def run_agent(settings: Settings) -> None:
    for note in settings.mode_notes():
        logger.info(note)

    frame_store = LatestFrameStore()
    capture = FrameCaptureService(settings, frame_store=frame_store)
    vision = GeminiLiveVision(settings)
    caller = AgentPhoneCaller(settings)
    ride_agent = RideAgent(settings=settings, caller=caller)

    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    webhook_thread = _start_webhook_thread(ride_agent, settings, frame_store)
    dashboard_task = asyncio.create_task(_dashboard(ride_agent, stop_event))

    try:
        frames = capture.frames()
        if scenario_enabled(settings):
            logger.info(
                "Scenario %s enabled; run_id=%s; sampling Gemini every %s frames and on arrival",
                settings.scenario,
                settings.scenario_run_id or "<none>",
                settings.scenario_vlm_interval_frames,
            )
            events = scenario_events(settings, frames, vision)
        else:
            events = apply_scenario(settings, vision.analyze_stream(frames))
        agent_task = asyncio.create_task(ride_agent.run(events))
        stop_task = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait({agent_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except asyncio.CancelledError:
        raise
    finally:
        stop_event.set()
        dashboard_task.cancel()
        with suppress(asyncio.CancelledError):
            await dashboard_task
        capture.close()
        if webhook_thread.is_alive():
            logger.info("Webhook thread will exit with process shutdown")


def _start_webhook_thread(agent: RideAgent, settings: Settings, frame_store: LatestFrameStore) -> threading.Thread:
    app = create_app(agent=agent, settings=settings, frame_store=frame_store)
    def run_webhook() -> None:
        try:
            app.run(
                host=settings.webhook_host,
                port=settings.webhook_port,
                debug=False,
                use_reloader=False,
            )
        except OSError as exc:
            logger.warning("Webhook server did not start: %s", exc)

    thread = threading.Thread(
        target=run_webhook,
        daemon=True,
        name="agentphone-webhook",
    )
    thread.start()
    logger.info("Webhook listening on %s:%s", settings.webhook_host, settings.webhook_port)
    return thread


async def _dashboard(agent: RideAgent, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        event = agent.last_event
        event_label = event.event_type.value if event else "none"
        reason = event.reason if event else "waiting for first frame"
        calls = len(agent.call_log)
        logger.info("dashboard state=%s event=%s calls=%s reason=%s", agent.state.value, event_label, calls, reason)
        await asyncio.sleep(3)


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Omega autonomous vehicle agent")
    parser.add_argument("--live", action="store_true", help="Disable demo mode and attempt CARLA/Gemini integrations")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    active_settings = settings
    if args.live:
        active_settings = Settings(demo_mode=False)
    asyncio.run(run_agent(active_settings))


if __name__ == "__main__":
    main()
