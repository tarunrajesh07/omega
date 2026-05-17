"""Spawn an ego vehicle in CARLA for Omega live runs."""

from __future__ import annotations

import argparse
import json
import random
import signal
import time
from pathlib import Path
from threading import Event

from config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spawn a CARLA ego vehicle for Omega")
    parser.add_argument("--host", default=settings.carla_host)
    parser.add_argument("--port", type=int, default=settings.carla_port)
    parser.add_argument("--timeout", type=float, default=settings.carla_timeout_seconds)
    parser.add_argument("--filter", default="vehicle.tesla.model3", help="CARLA blueprint filter")
    parser.add_argument("--role-name", default="hero")
    parser.add_argument("--autopilot", action="store_true", help="Enable CARLA Traffic Manager autopilot")
    parser.add_argument("--tm-port", type=int, default=8000, help="Traffic Manager port")
    parser.add_argument("--keep-alive", action="store_true", help="Keep the script running so Ctrl+C destroys the vehicle")
    parser.add_argument("--spawn-index", type=int, default=0, help="Map spawn point index to try first")
    parser.add_argument("--target-index", type=int, help="Map spawn point index to drive toward before holding position")
    parser.add_argument("--arrival-distance", type=float, default=8.0, help="Meters from target considered arrived")
    parser.add_argument("--scenario-state-file", default=settings.scenario_state_file)
    parser.add_argument("--hold-position", action="store_true", help="Disable physics so the vehicle remains at the spawn point")
    parser.add_argument("--list-spawns", action="store_true", help="List available spawn points and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import carla

    print(f"Using CARLA Python API from {getattr(carla, '__file__', 'unknown')}")
    print(f"CARLA Python API version {getattr(carla, '__version__', 'unknown')}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.get_world()
    carla_version = client.get_client_version()
    simulator_version = client.get_server_version()
    print(f"CARLA client API version {carla_version}")
    print(f"CARLA simulator API version {simulator_version}")
    if carla_version != simulator_version:
        print("WARNING: CARLA client/server versions differ. Install the Python API that ships with this simulator build.")

    blueprint_library = world.get_blueprint_library()
    blueprints = blueprint_library.filter(args.filter)
    if not blueprints:
        raise RuntimeError(f"No vehicle blueprints matched {args.filter!r}")

    blueprint = random.choice(blueprints)
    blueprint.set_attribute("role_name", args.role_name)
    if blueprint.has_attribute("color"):
        color = random.choice(blueprint.get_attribute("color").recommended_values)
        blueprint.set_attribute("color", color)

    spawn_points = world.get_map().get_spawn_points()
    if args.list_spawns:
        for index, spawn_point in enumerate(spawn_points):
            location = spawn_point.location
            rotation = spawn_point.rotation
            print(
                f"{index}: x={location.x:.2f} y={location.y:.2f} z={location.z:.2f} "
                f"pitch={rotation.pitch:.2f} yaw={rotation.yaw:.2f} roll={rotation.roll:.2f}",
            )
        return

    ordered_spawn_points = spawn_points[:]
    if ordered_spawn_points:
        first_index = args.spawn_index % len(ordered_spawn_points)
        preferred = ordered_spawn_points[first_index]
        rest = ordered_spawn_points[:first_index] + ordered_spawn_points[first_index + 1 :]
        random.shuffle(rest)
        ordered_spawn_points = [preferred] + rest
    vehicle = None
    for spawn_point in ordered_spawn_points:
        vehicle = world.try_spawn_actor(blueprint, spawn_point)
        if vehicle is not None:
            break

    if vehicle is None:
        raise RuntimeError("Could not spawn vehicle; all spawn points may be occupied")

    print(f"Spawned {vehicle.type_id} id={vehicle.id} role_name={args.role_name}")

    if args.hold_position:
        vehicle.set_simulate_physics(False)
        print("Vehicle physics disabled; holding position for scenario")

    if args.target_index is not None:
        target = spawn_points[args.target_index % len(spawn_points)]
        vehicle.set_autopilot(False)
        _drive_to_target(client, vehicle, target.location, args)
    elif args.autopilot and not args.hold_position:
        traffic_manager = client.get_trafficmanager(args.tm_port)
        traffic_manager.set_global_distance_to_leading_vehicle(2.5)
        vehicle.set_autopilot(True, traffic_manager.get_port())
        print(f"Autopilot enabled via Traffic Manager port {traffic_manager.get_port()}")

    if args.keep_alive:
        stop_event = Event()

        def stop(_signum: int, _frame: object) -> None:
            stop_event.set()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        print("Keeping vehicle alive. Press Ctrl+C to destroy it.")
        try:
            while not stop_event.is_set():
                time.sleep(1)
        finally:
            print("Destroying vehicle")
            vehicle.destroy()


def _drive_to_target(client: object, vehicle: object, target_location: object, args: argparse.Namespace) -> None:
    from agents.navigation.basic_agent import BasicAgent

    _write_scenario_state(args.scenario_state_file, "driving", vehicle.id, target_location)
    agent = BasicAgent(vehicle, target_speed=25)
    agent.set_destination(target_location)
    world = vehicle.get_world()

    print(
        "Driving to target "
        f"x={target_location.x:.2f} y={target_location.y:.2f} z={target_location.z:.2f} "
        f"arrival_distance={args.arrival_distance:.1f}m",
    )

    while True:
        if _distance(vehicle.get_location(), target_location) <= args.arrival_distance or agent.done():
            vehicle.apply_control(_stop_control())
            vehicle.set_autopilot(False)
            _write_scenario_state(args.scenario_state_file, "arrived", vehicle.id, target_location)
            print("Arrived at target; vehicle stopped")
            return

        control = agent.run_step()
        control.manual_gear_shift = False
        vehicle.apply_control(control)
        world.wait_for_tick()


def _distance(a: object, b: object) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def _stop_control() -> object:
    import carla

    return carla.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)


def _write_scenario_state(path: str, status: str, vehicle_id: int, target_location: object) -> None:
    payload = {
        "status": status,
        "vehicle_id": vehicle_id,
        "target": {"x": target_location.x, "y": target_location.y, "z": target_location.z},
        "updated_at": time.time(),
    }
    Path(path).write_text(json.dumps(payload))


if __name__ == "__main__":
    main()
