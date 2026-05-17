"""Frame capture from CARLA with a deterministic demo fallback."""

from __future__ import annotations

import asyncio
import io
import logging
import math
from dataclasses import dataclass
from typing import AsyncIterator

from PIL import Image, ImageDraw

from config import Settings
from frame_store import LatestFrameStore
from models import Frame

logger = logging.getLogger(__name__)


@dataclass
class CarlaHandles:
    world: object
    vehicle: object
    camera: object


class FrameCaptureService:
    """Captures RGB frames from CARLA or emits synthetic frames for demos."""

    def __init__(self, settings: Settings, frame_store: LatestFrameStore | None = None) -> None:
        self.settings = settings
        self.frame_store = frame_store
        self._queue: asyncio.Queue[Frame] = asyncio.Queue(maxsize=3)
        self._handles: CarlaHandles | None = None
        self._running = False

    async def frames(self) -> AsyncIterator[Frame]:
        if self.settings.demo_mode:
            async for frame in self._demo_frames():
                yield frame
            return

        try:
            await self._connect_carla()
        except Exception as exc:  # pragma: no cover - depends on CARLA runtime.
            logger.warning("CARLA capture unavailable (%s); falling back to demo frames", exc)
            async for frame in self._demo_frames():
                yield frame
            return

        self._running = True
        try:
            while self._running:
                yield await self._queue.get()
        finally:
            self.close()

    async def _connect_carla(self) -> None:  # pragma: no cover - depends on CARLA runtime.
        import carla

        client = carla.Client(self.settings.carla_host, self.settings.carla_port)
        client.set_timeout(self.settings.carla_timeout_seconds)
        world = client.get_world()
        vehicle = self._find_ego_vehicle(world)

        blueprint_library = world.get_blueprint_library()
        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", str(self.settings.camera_width))
        camera_bp.set_attribute("image_size_y", str(self.settings.camera_height))
        camera_bp.set_attribute("fov", str(self.settings.camera_fov))

        transform = carla.Transform(carla.Location(x=1.5, z=2.4))
        camera = world.spawn_actor(camera_bp, transform, attach_to=vehicle)
        camera.listen(self._on_carla_image)
        self._handles = CarlaHandles(world=world, vehicle=vehicle, camera=camera)
        if self.settings.follow_spectator:
            self._start_spectator_follow()
        logger.info("Connected to CARLA at %s:%s", self.settings.carla_host, self.settings.carla_port)

    def _find_ego_vehicle(self, world: object) -> object:  # pragma: no cover - depends on CARLA runtime.
        actors = world.get_actors().filter("vehicle.*")
        for actor in actors:
            if actor.attributes.get("role_name") == "hero":
                return actor
        if actors:
            return actors[0]
        raise RuntimeError("No vehicle actors found in CARLA world")

    def _on_carla_image(self, image: object) -> None:  # pragma: no cover - depends on CARLA runtime.
        data = bytes(image.raw_data)
        # CARLA camera buffers are BGRA by default. Decode directly instead of
        # calling image.convert(), whose enum binding differs across versions.
        pil = Image.frombytes("RGBA", (image.width, image.height), data, "raw", "BGRA").convert("RGB")
        buffer = io.BytesIO()
        pil.save(buffer, format="JPEG", quality=80)
        frame = Frame(jpeg_bytes=buffer.getvalue(), sequence=image.frame, source="carla")
        if self.frame_store:
            self.frame_store.update(frame)

        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            _ = self._queue.get_nowait()
            self._queue.put_nowait(frame)

    async def _demo_frames(self) -> AsyncIterator[Frame]:
        interval = 1.0 / max(self.settings.frame_rate, 0.1)
        for sequence in range(self.settings.demo_frame_count):
            frame = Frame(
                jpeg_bytes=self._render_demo_frame(sequence),
                sequence=sequence,
                source="demo",
            )
            if self.frame_store:
                self.frame_store.update(frame)
            yield frame
            await asyncio.sleep(interval)

    def _start_spectator_follow(self) -> None:  # pragma: no cover - depends on CARLA runtime.
        async def follow() -> None:
            while self._running and self._handles is not None:
                self._update_spectator()
                await asyncio.sleep(0.1)

        asyncio.create_task(follow())

    def _update_spectator(self) -> None:  # pragma: no cover - depends on CARLA runtime.
        if self._handles is None:
            return
        import carla

        vehicle_transform = self._handles.vehicle.get_transform()
        yaw_radians = math.radians(vehicle_transform.rotation.yaw)
        distance = self.settings.spectator_distance
        location = carla.Location(
            x=vehicle_transform.location.x - distance * math.cos(yaw_radians),
            y=vehicle_transform.location.y - distance * math.sin(yaw_radians),
            z=vehicle_transform.location.z + self.settings.spectator_height,
        )
        rotation = carla.Rotation(
            pitch=-18.0,
            yaw=vehicle_transform.rotation.yaw,
            roll=0.0,
        )
        self._handles.world.get_spectator().set_transform(carla.Transform(location, rotation))

    def _render_demo_frame(self, sequence: int) -> bytes:
        width = self.settings.camera_width
        height = self.settings.camera_height
        image = Image.new("RGB", (width, height), "#7aa4a8")
        draw = ImageDraw.Draw(image)

        horizon = int(height * 0.42)
        draw.rectangle((0, horizon, width, height), fill="#3f4840")
        draw.polygon(
            [(int(width * 0.38), height), (int(width * 0.47), horizon), (int(width * 0.53), horizon), (int(width * 0.62), height)],
            fill="#2f3330",
        )
        draw.line((width // 2, horizon, width // 2, height), fill="#f2d45c", width=4)

        if 8 <= sequence < 22:
            draw.rectangle((int(width * 0.44), int(height * 0.52), int(width * 0.62), int(height * 0.65)), fill="#a12b2b")
            draw.text((20, 20), "DEMO: blocked by parked vehicle", fill="white")
        elif 28 <= sequence < 34:
            draw.rectangle((int(width * 0.3), int(height * 0.35), int(width * 0.7), int(height * 0.5)), fill="#d6d0be")
            draw.text((20, 20), "DEMO: destination ahead", fill="white")
        elif sequence >= 34:
            draw.rectangle((int(width * 0.2), int(height * 0.28), int(width * 0.8), int(height * 0.52)), fill="#ded8c5")
            draw.text((20, 20), "DEMO: arrived outside destination", fill="white")
        else:
            draw.text((20, 20), "DEMO: en route", fill="white")

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()

    def close(self) -> None:
        self._running = False
        if self._handles is not None:  # pragma: no cover - depends on CARLA runtime.
            self._handles.camera.stop()
            self._handles.camera.destroy()
            self._handles = None
