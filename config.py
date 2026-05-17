"""Runtime configuration for the Omega autonomous vehicle agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def load_dotenv(path: str | os.PathLike[str] = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file without overriding exports."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "t", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-live-001")

    agentphone_api_key: str | None = os.getenv("AGENTPHONE_API_KEY")
    agentphone_agent_id: str | None = os.getenv("AGENTPHONE_AGENT_ID")
    agentphone_webhook_secret: str | None = os.getenv("AGENTPHONE_WEBHOOK_SECRET")
    agentphone_base_url: str = os.getenv("AGENTPHONE_BASE_URL", "https://api.agentphone.com")
    passenger_phone_number: str | None = os.getenv("PASSENGER_PHONE_NUMBER")
    passenger_name: str = os.getenv("PASSENGER_NAME", "passenger")

    carla_host: str = os.getenv("CARLA_HOST", "localhost")
    carla_port: int = _get_int("CARLA_PORT", 2000)
    carla_timeout_seconds: float = _get_float("CARLA_TIMEOUT_SECONDS", 5.0)
    camera_width: int = _get_int("CAMERA_WIDTH", 800)
    camera_height: int = _get_int("CAMERA_HEIGHT", 600)
    camera_fov: float = _get_float("CAMERA_FOV", 90.0)
    frame_rate: float = _get_float("FRAME_RATE", 5.0)
    follow_spectator: bool = _get_bool("FOLLOW_SPECTATOR", True)
    spectator_distance: float = _get_float("SPECTATOR_DISTANCE", 8.0)
    spectator_height: float = _get_float("SPECTATOR_HEIGHT", 4.0)

    webhook_host: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    webhook_port: int = _get_int("WEBHOOK_PORT", 3000)

    destination_label: str = os.getenv("DESTINATION_LABEL", "the pickup point")
    landmark_label: str | None = os.getenv("LANDMARK_LABEL")
    scenario: str = os.getenv("SCENARIO", "live")
    scenario_warmup_frames: int = _get_int("SCENARIO_WARMUP_FRAMES", 8)
    scenario_state_file: str = os.getenv("SCENARIO_STATE_FILE", ".omega_scenario_state.json")
    demo_mode: bool = _get_bool("DEMO_MODE", True)
    demo_frame_count: int = _get_int("DEMO_FRAME_COUNT", 40)

    blocked_threshold: int = _get_int("BLOCKED_THRESHOLD", 3)
    arrived_threshold: int = _get_int("ARRIVED_THRESHOLD", 2)
    hazard_threshold: int = _get_int("HAZARD_THRESHOLD", 2)
    rerouting_threshold: int = _get_int("REROUTING_THRESHOLD", 2)
    call_cooldown_seconds: float = _get_float("CALL_COOLDOWN_SECONDS", 20.0)

    llm_reply_model: str = os.getenv("LLM_REPLY_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    def missing_for_live_calls(self) -> list[str]:
        required = {
            "AGENTPHONE_API_KEY": self.agentphone_api_key,
            "AGENTPHONE_AGENT_ID": self.agentphone_agent_id,
            "PASSENGER_PHONE_NUMBER": self.passenger_phone_number,
        }
        return [name for name, value in required.items() if not value]

    def missing_for_gemini(self) -> list[str]:
        return [] if self.google_api_key else ["GOOGLE_API_KEY"]

    def mode_notes(self) -> Iterable[str]:
        if self.demo_mode:
            yield "DEMO_MODE is enabled; scripted frames/events are available."
        if self.missing_for_gemini():
            yield "GOOGLE_API_KEY is missing; VLM will use scripted demo analysis."
        if self.missing_for_live_calls():
            yield "AgentPhone credentials are incomplete; outbound calls will be logged only."


settings = Settings()
