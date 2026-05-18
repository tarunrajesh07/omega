"""Thread-safe storage for the latest camera frame."""

from __future__ import annotations

from threading import Lock

from models import Frame, VehicleTelemetry


class LatestFrameStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._frame: Frame | None = None
        self._telemetry: VehicleTelemetry | None = None
        self._map: dict | None = None

    def update(self, frame: Frame) -> None:
        with self._lock:
            self._frame = frame

    def latest(self) -> Frame | None:
        with self._lock:
            return self._frame

    def update_telemetry(self, telemetry: VehicleTelemetry) -> None:
        with self._lock:
            self._telemetry = telemetry

    def latest_telemetry(self) -> VehicleTelemetry | None:
        with self._lock:
            return self._telemetry

    def update_map(self, map_payload: dict) -> None:
        with self._lock:
            self._map = map_payload

    def latest_map(self) -> dict | None:
        with self._lock:
            return self._map
