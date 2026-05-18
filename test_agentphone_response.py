"""AgentPhone response-capture test.

Starts a local webhook, places one outbound call, asks the callee to say a target phrase,
and reports whether that phrase appeared in any AgentPhone webhook event.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import time
from dataclasses import replace
from typing import Any

from flask import Flask, Response, jsonify, request

from caller import AgentPhoneCaller
from config import Settings, settings
from models import CallRequest, EventType

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test whether AgentPhone sends user speech/transcript events to a webhook")
    parser.add_argument("--to", dest="to_number", default=settings.passenger_phone_number, help="Phone number to call")
    parser.add_argument("--expected", default="banana taxi", help="Phrase the callee should say during the call")
    parser.add_argument("--port", type=int, default=3010, help="Local webhook port for this test")
    parser.add_argument("--wait-seconds", type=float, default=120.0, help="How long to wait for webhook events")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    missing = settings.missing_for_live_calls()
    if missing:
        raise RuntimeError(f"Missing required AgentPhone settings: {', '.join(missing)}")
    if not args.to_number:
        raise RuntimeError("Missing --to or PASSENGER_PHONE_NUMBER")

    collector = EventCollector(expected=args.expected)
    app = create_test_app(collector)
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False),
        daemon=True,
        name="agentphone-response-test-webhook",
    )
    thread.start()
    await asyncio.sleep(0.5)

    webhook_url_hint = f"http://<your-public-tunnel>/agentphone-test"
    logger.info("Local test webhook listening on http://localhost:%s/agentphone-test", args.port)
    logger.info("Configure/tunnel AgentPhone webhooks to POST to %s", webhook_url_hint)

    script = (
        f"This is a response capture test. Please say exactly: {args.expected}. "
        "After you say it, you can hang up."
    )
    system_prompt = (
        "You are running a short AgentPhone webhook test. "
        f"Ask the callee to say exactly: {args.expected}. "
        "Do not discuss rides, routing, or anything else. If they say the phrase, acknowledge it and end politely."
    )
    request_model = CallRequest(
        event_type=EventType.UNKNOWN,
        script=script,
        context=f"AgentPhone response test; expected phrase: {args.expected}",
        system_prompt=system_prompt,
        passenger_name=settings.passenger_name,
        to_number=args.to_number,
    )
    active_settings = replace(settings, webhook_port=args.port)
    result = await AgentPhoneCaller(active_settings).call(request_model)
    logger.info("Call request result attempted=%s call_id=%s message=%s", result.attempted, result.call_id, result.message)

    deadline = time.monotonic() + args.wait_seconds
    while time.monotonic() < deadline:
        if collector.call_ended and collector.seen_expected:
            break
        await asyncio.sleep(0.5)

    print("\nAgentPhone response test result")
    print(f"expected_phrase={args.expected!r}")
    print(f"call_id={result.call_id!r}")
    print(f"events_received={len(collector.events)}")
    print(f"call_ended={collector.call_ended}")
    print(f"seen_expected={collector.seen_expected}")
    if collector.transcripts:
        print("transcripts:")
        for transcript in collector.transcripts:
            print(f"- {transcript}")
    else:
        print("transcripts: <none>")

    if not collector.events:
        print("diagnosis=no webhook events reached this process; check public tunnel/webhook URL and AgentPhone agent voice mode")
    elif not collector.transcripts:
        print("diagnosis=webhook events arrived, but no transcript/message text was found in their payloads")
    elif not collector.seen_expected:
        print("diagnosis=transcripts arrived, but the expected phrase was not detected")
    else:
        print("diagnosis=success; AgentPhone sent the expected user response to the webhook")


def create_test_app(collector: "EventCollector") -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health() -> Response:
        return jsonify({"ok": True, "events": len(collector.events), "seen_expected": collector.seen_expected})

    @app.post("/agentphone-test")
    def agentphone_test() -> Response:
        payload: dict[str, Any] = request.get_json(silent=True) or {}
        collector.record(payload)
        event_type = payload.get("type") or payload.get("event")
        logger.info("AgentPhone test webhook event=%s extracted_text=%r", event_type, collector.last_text)
        if event_type == "agent.message":
            return jsonify({"text": "Thank you. I recorded your response."})
        return jsonify({"ok": True})

    return app


class EventCollector:
    def __init__(self, expected: str) -> None:
        self.expected = expected.lower()
        self.events: list[dict[str, Any]] = []
        self.transcripts: list[str] = []
        self.call_ended = False
        self.seen_expected = False
        self.last_text = ""

    def record(self, payload: dict[str, Any]) -> None:
        self.events.append(payload)
        event_type = str(payload.get("type") or payload.get("event") or "")
        if "call_ended" in event_type or event_type.endswith(".ended"):
            self.call_ended = True

        texts = _extract_texts(payload)
        self.last_text = " | ".join(texts)
        for text in texts:
            normalized = " ".join(text.lower().split())
            if normalized and normalized not in self.transcripts:
                self.transcripts.append(text)
            if self.expected in normalized:
                self.seen_expected = True

        logger.debug("AgentPhone raw event: %s", json.dumps(payload, sort_keys=True))


def _extract_texts(value: Any) -> list[str]:
    texts: list[str] = []
    interesting_keys = {"transcript", "text", "message", "content", "utterance", "speech", "input"}

    def walk(node: Any, key: str = "") -> None:
        if isinstance(node, dict):
            for child_key, child_value in node.items():
                walk(child_value, str(child_key))
            return
        if isinstance(node, list):
            for item in node:
                walk(item, key)
            return
        if isinstance(node, str) and key in interesting_keys and node.strip():
            texts.append(node.strip())

    walk(value)
    return texts


if __name__ == "__main__":
    asyncio.run(main())
