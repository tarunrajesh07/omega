"""Shared data models for Omega."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    BLOCKED = "blocked"
    HAZARD = "hazard"
    REROUTING = "rerouting"
    UNKNOWN = "unknown"


class RideState(str, Enum):
    IDLE = "idle"
    EN_ROUTE = "en_route"
    BLOCKED = "blocked"
    HAZARD = "hazard"
    REROUTING = "rerouting"
    ARRIVED = "arrived"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Frame:
    jpeg_bytes: bytes
    sequence: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "unknown"

    @property
    def size_bytes(self) -> int:
        return len(self.jpeg_bytes)


@dataclass(frozen=True)
class VehicleTelemetry:
    x: float
    y: float
    z: float
    yaw: float
    speed_mps: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class VisionEvent:
    event_type: EventType
    reason: str
    confidence: float = 0.0
    obstacle: str | None = None
    eta_minutes: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VisionEvent":
        status = str(payload.get("event") or payload.get("state") or payload.get("status") or "unknown")
        try:
            event_type = EventType(status)
        except ValueError:
            event_type = EventType.UNKNOWN

        confidence = payload.get("confidence", 0.0)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0

        eta = payload.get("eta_minutes")
        try:
            eta_value = int(eta) if eta is not None else None
        except (TypeError, ValueError):
            eta_value = None

        return cls(
            event_type=event_type,
            reason=str(payload.get("reason") or "No reason provided."),
            confidence=confidence_value,
            obstacle=payload.get("obstacle"),
            eta_minutes=eta_value,
            raw=payload,
        )


@dataclass(frozen=True)
class SceneDescription:
    summary: str
    pickup_cue: str | None = None
    visible_landmark: str | None = None
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SceneDescription":
        confidence = payload.get("confidence", 0.0)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0
        return cls(
            summary=str(payload.get("summary") or payload.get("reason") or "No scene description provided."),
            pickup_cue=payload.get("pickup_cue"),
            visible_landmark=payload.get("visible_landmark"),
            confidence=confidence_value,
            raw=payload,
        )


@dataclass(frozen=True)
class CallRequest:
    event_type: EventType
    script: str
    context: str
    system_prompt: str
    passenger_name: str
    to_number: str | None


@dataclass(frozen=True)
class CallResult:
    attempted: bool
    call_id: str | None
    message: str


@dataclass(frozen=True)
class PassengerDecision:
    action: str
    transcript: str
    call_id: str | None = None
