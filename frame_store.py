"""Thread-safe storage for the latest camera frame."""

from __future__ import annotations

from threading import Lock

from models import Frame


class LatestFrameStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._frame: Frame | None = None

    def update(self, frame: Frame) -> None:
        with self._lock:
            self._frame = frame

    def latest(self) -> Frame | None:
        with self._lock:
            return self._frame

