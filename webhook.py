"""Flask webhook server for AgentPhone voice events."""

from __future__ import annotations

import hmac
import hashlib
import logging
import time
from typing import Any

from flask import Flask, Response, jsonify, request

from agent import RideAgent
from config import Settings, settings as default_settings
from frame_store import LatestFrameStore
from models import PassengerDecision

logger = logging.getLogger(__name__)


def create_app(
    agent: RideAgent | None = None,
    settings: Settings = default_settings,
    frame_store: LatestFrameStore | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["ride_agent"] = agent
    app.config["settings"] = settings
    app.config["frame_store"] = frame_store

    @app.get("/health")
    def health() -> Response:
        ride_agent: RideAgent | None = app.config.get("ride_agent")
        return jsonify({"ok": True, "state": ride_agent.state.value if ride_agent else "standalone"})

    @app.get("/api/dashboard")
    def dashboard() -> Response:
        ride_agent: RideAgent | None = app.config.get("ride_agent")
        store: LatestFrameStore | None = app.config.get("frame_store")
        frame = store.latest() if store else None
        telemetry = store.latest_telemetry() if store else None
        map_payload = store.latest_map() if store else None
        current_settings: Settings = app.config.get("settings") or settings
        event = ride_agent.last_event if ride_agent else None
        return jsonify(
            {
                "rideId": current_settings.scenario_run_id or "omega-live",
                "passengerName": current_settings.passenger_name,
                "passengerPhone": current_settings.passenger_phone_number or "not configured",
                "pickup": current_settings.destination_label,
                "destination": current_settings.reroute_destination_label,
                "state": ride_agent.state.value if ride_agent else "idle",
                "callState": _call_state(ride_agent),
                "callDuration": _call_duration(ride_agent),
                "callLog": ride_agent.call_log if ride_agent else [],
                "transcript": ride_agent.transcript_log if ride_agent else [],
                "eventLog": ride_agent.event_log if ride_agent else [],
                "lastEvent": _event_payload(event),
                "frame": _frame_payload(frame),
                "vehicle": _telemetry_payload(telemetry),
                "map": map_payload,
                "camera": {
                    "snapshotUrl": "/camera.jpg",
                    "streamUrl": "/camera.mjpg",
                    "available": frame is not None,
                },
                "integrations": {
                    "carla": frame is not None and frame.source == "carla",
                    "gemini": bool(current_settings.google_api_key),
                    "agentphone": bool(current_settings.agentphone_api_key),
                },
            },
        )

    @app.post("/api/transcript")
    def submit_transcript() -> Response:
        ride_agent: RideAgent | None = app.config.get("ride_agent")
        if ride_agent is None:
            return jsonify({"error": "ride agent unavailable"}), 404
        payload: dict[str, Any] = request.get_json(silent=True) or {}
        transcript = str(payload.get("text") or payload.get("transcript") or "").strip()
        if not transcript:
            return jsonify({"error": "text is required"}), 400
        decision = _classify_decision(transcript)
        if decision == "unknown":
            ride_agent.record_transcript("passenger", transcript)
            ride_agent.record_event("call", "Passenger transcript received")
        else:
            ride_agent.apply_passenger_decision(
                PassengerDecision(action=decision, transcript=transcript, call_id=payload.get("callId")),
            )
        return jsonify({"ok": True, "decision": decision, "reply": _reply_for_decision(decision, transcript)})

    @app.post("/demo/reroute")
    def demo_reroute() -> Response:
        ride_agent: RideAgent | None = app.config.get("ride_agent")
        if ride_agent is None:
            return jsonify({"error": "ride agent unavailable"}), 404
        ride_agent.apply_passenger_decision(
            PassengerDecision(action="reroute", transcript="manual demo reroute", call_id=None),
        )
        return jsonify({"ok": True, "state": ride_agent.state.value})

    @app.get("/camera.jpg")
    def camera_jpeg() -> Response:
        store: LatestFrameStore | None = app.config.get("frame_store")
        frame = store.latest() if store else None
        if frame is None:
            return jsonify({"error": "no frame captured yet"}), 404
        return Response(frame.jpeg_bytes, mimetype="image/jpeg")

    @app.get("/camera.mjpg")
    def camera_mjpeg() -> Response:
        store: LatestFrameStore | None = app.config.get("frame_store")
        if store is None:
            return jsonify({"error": "camera stream unavailable"}), 404

        def generate() -> Any:
            last_sequence = -1
            while True:
                frame = store.latest()
                if frame is not None and frame.sequence != last_sequence:
                    last_sequence = frame.sequence
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + frame.jpeg_bytes
                        + b"\r\n"
                    )
                time.sleep(0.05)

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.post("/webhook/agentphone")
    def agentphone_webhook() -> Response:
        if not _valid_signature(request.get_data(), request.headers, settings):
            return jsonify({"error": "invalid signature"}), 401

        payload: dict[str, Any] = request.get_json(silent=True) or {}
        event_type = payload.get("type") or payload.get("event")
        logger.info("AgentPhone webhook type=%s", event_type)

        if event_type == "agent.message":
            transcript = _extract_transcript(payload)
            decision = _classify_decision(transcript)
            ride_agent: RideAgent | None = app.config.get("ride_agent")
            if ride_agent and decision != "unknown":
                ride_agent.apply_passenger_decision(
                    PassengerDecision(action=decision, transcript=transcript, call_id=payload.get("callId")),
                )
            elif ride_agent and transcript:
                ride_agent.record_transcript("passenger", transcript)
                ride_agent.record_event("call", "AgentPhone transcript received")
            return jsonify({"text": _reply_for_decision(decision, transcript)})

        if event_type == "agent.call_ended":
            logger.info("Call ended payload=%s", payload)
            ride_agent: RideAgent | None = app.config.get("ride_agent")
            if ride_agent:
                ride_agent.mark_call_ended(payload.get("callId") or payload.get("id"))
            return jsonify({"ok": True})

        return jsonify({"text": "I received that update."})

    return app


def _call_state(agent: RideAgent | None) -> str:
    if agent is None:
        return "none"
    if agent._active_call_started_at is not None:
        return "in_call"
    return "ended" if agent.call_log else "none"


def _call_duration(agent: RideAgent | None) -> int:
    if agent is None or agent._active_call_started_at is None:
        return 0
    return max(0, int(time.monotonic() - agent._active_call_started_at))


def _event_payload(event: Any) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "id": f"vlm-{int(event.timestamp.timestamp() * 1000)}",
        "timestamp": event.timestamp.isoformat(),
        "type": event.event_type.value,
        "reason": event.reason,
        "confidence": event.confidence,
        "frameId": event.raw.get("frame") or event.raw.get("frame_id") or 0,
    }


def _frame_payload(frame: Any) -> dict[str, Any] | None:
    if frame is None:
        return None
    return {
        "sequence": frame.sequence,
        "timestamp": frame.timestamp.isoformat(),
        "source": frame.source,
        "sizeBytes": frame.size_bytes,
    }


def _telemetry_payload(telemetry: Any) -> dict[str, Any] | None:
    if telemetry is None:
        return None
    return {
        "x": telemetry.x,
        "y": telemetry.y,
        "z": telemetry.z,
        "yaw": telemetry.yaw,
        "speedMps": telemetry.speed_mps,
        "timestamp": telemetry.timestamp.isoformat(),
    }


def _valid_signature(body: bytes, headers: Any, settings: Settings) -> bool:
    secret = settings.agentphone_webhook_secret
    if not secret:
        return True
    signature = headers.get("X-AgentPhone-Signature") or headers.get("x-agentphone-signature")
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(signature, expected) or hmac.compare_digest(signature, digest)


def _extract_transcript(payload: dict[str, Any]) -> str:
    message = payload.get("message")
    if isinstance(message, dict):
        return str(message.get("transcript") or message.get("text") or "")
    return str(payload.get("transcript") or payload.get("text") or "")


def _classify_decision(transcript: str) -> str:
    text = transcript.lower()
    if any(token in text for token in ("cancel", "stop", "end ride")):
        return "cancel"
    if any(token in text for token in ("reroute", "alternate", "different route")):
        return "reroute"
    if any(token in text for token in ("wait", "hold", "stay")):
        return "wait"
    if any(token in text for token in ("resume", "continue", "go ahead")):
        return "resume"
    return "unknown"


def _reply_for_decision(decision: str, transcript: str) -> str:
    if decision == "wait":
        return "Understood. I will wait here and update you when the route clears."
    if decision == "reroute":
        return "Got it. I can reroute there. That will add about two minutes to your ETA."
    if decision == "cancel":
        return "Understood. I will cancel the ride and stop further routing."
    if decision == "resume":
        return "Understood. I will continue when it is safe to proceed."
    if transcript:
        return "I heard you. I'm waiting here at the pickup location."
    return "I'm waiting here at the pickup location."


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=default_settings.webhook_host, port=default_settings.webhook_port)
