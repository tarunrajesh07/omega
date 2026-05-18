"""Spawn an ego vehicle in CARLA for Omega live runs."""

from __future__ import annotations

import argparse
import json
import math
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
    parser.add_argument("--reroute-target-index", type=int, help="Second map spawn point index to drive toward after a reroute command")
    parser.add_argument("--arrival-distance", type=float, default=8.0, help="Meters from target considered arrived")
    parser.add_argument("--curb-offset-feet", type=float, default=0.0, help="After arrival, pull over this many feet to the vehicle's right before marking arrived")
    parser.add_argument("--curb-pull-over-seconds", type=float, default=8.0, help="Maximum seconds to spend on the curb pull-over maneuver")
    parser.add_argument("--scenario-state-file", default=settings.scenario_state_file)
    parser.add_argument("--scenario-run-id", default=settings.scenario_run_id)
    parser.add_argument("--min-route-distance", type=float, default=20.0, help="Reject target routes shorter than this many meters")
    parser.add_argument("--max-drive-seconds", type=float, default=120.0, help="Abort target driving after this many seconds")
    parser.add_argument("--exact-spawn", action="store_true", help="Use only --spawn-index and fail if that point is occupied")
    parser.add_argument("--destroy-existing-heroes", action="store_true", help="Destroy existing role_name=hero vehicles before spawning")
    parser.add_argument("--hold-position", action="store_true", help="Disable physics so the vehicle remains at the spawn point")
    parser.add_argument("--arrive-at-spawn", action="store_true", help="Mark the vehicle arrived immediately at its spawn point before any reroute leg")
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

    if args.destroy_existing_heroes:
        _destroy_existing_heroes(world)

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

    if not spawn_points:
        raise RuntimeError("CARLA map has no spawn points")

    first_index = args.spawn_index % len(spawn_points)
    preferred = spawn_points[first_index]
    if args.exact_spawn:
        ordered_spawn_points = [preferred]
    else:
        rest = spawn_points[:first_index] + spawn_points[first_index + 1 :]
        random.shuffle(rest)
        ordered_spawn_points = [preferred] + rest

    vehicle = None
    for spawn_point in ordered_spawn_points:
        vehicle = world.try_spawn_actor(blueprint, spawn_point)
        if vehicle is not None:
            break

    if vehicle is None:
        raise RuntimeError("Could not spawn vehicle; all spawn points may be occupied")

    actual = vehicle.get_transform().location
    print(
        f"Spawned {vehicle.type_id} id={vehicle.id} role_name={args.role_name} "
        f"at x={actual.x:.2f} y={actual.y:.2f} from requested spawn_index={args.spawn_index}",
        flush=True,
    )

    if args.hold_position:
        vehicle.set_simulate_physics(False)
        print("Vehicle physics disabled; holding position for scenario")

    if args.arrive_at_spawn:
        vehicle.apply_control(_stop_control())
        vehicle.set_autopilot(False)
        _write_scenario_state(args.scenario_state_file, "arrived", vehicle.id, vehicle.get_location(), args.scenario_run_id)
        print("Marked vehicle arrived at spawn; waiting at pickup location", flush=True)
        if args.reroute_target_index is not None:
            reroute_target = spawn_points[args.reroute_target_index % len(spawn_points)]
            _wait_for_reroute_command(args.scenario_state_file, args.scenario_run_id)
            _drive_to_target(
                client,
                vehicle,
                reroute_target.location,
                args,
                driving_status="rerouting",
                arrived_status="reroute_arrived",
            )
    elif args.target_index is not None:
        target = spawn_points[args.target_index % len(spawn_points)]
        route_distance = _distance(vehicle.get_location(), target.location)
        print(f"Route distance from spawn to target: {route_distance:.1f}m")
        if route_distance < args.min_route_distance:
            raise RuntimeError(
                f"Spawn index {args.spawn_index} and target index {args.target_index} are only "
                f"{route_distance:.1f}m apart. Choose farther points or lower --min-route-distance.",
            )
        vehicle.set_autopilot(False)
        _drive_to_target(client, vehicle, target.location, args)
        if args.reroute_target_index is not None:
            reroute_target = spawn_points[args.reroute_target_index % len(spawn_points)]
            _wait_for_reroute_command(args.scenario_state_file, args.scenario_run_id)
            _drive_to_target(
                client,
                vehicle,
                reroute_target.location,
                args,
                driving_status="rerouting",
                arrived_status="reroute_arrived",
            )
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


def _drive_to_target(
    client: object,
    vehicle: object,
    target_location: object,
    args: argparse.Namespace,
    driving_status: str = "driving",
    arrived_status: str = "arrived",
) -> None:
    from agents.navigation.basic_agent import BasicAgent

    _write_scenario_state(args.scenario_state_file, driving_status, vehicle.id, target_location, args.scenario_run_id)
    agent = BasicAgent(vehicle, target_speed=25)
    agent.set_destination(target_location)
    world = vehicle.get_world()

    print(
        "Driving to target "
        f"x={target_location.x:.2f} y={target_location.y:.2f} z={target_location.z:.2f} "
        f"arrival_distance={args.arrival_distance:.1f}m",
        flush=True,
    )

    started_at = time.monotonic()
    tick_count = 0
    while True:
        distance = _distance(vehicle.get_location(), target_location)
        if distance <= args.arrival_distance:
            vehicle.set_autopilot(False)
            if args.curb_offset_feet:
                _pull_over_right(vehicle, args.curb_offset_feet, args.curb_pull_over_seconds)
            else:
                vehicle.apply_control(_stop_control())
            _write_scenario_state(args.scenario_state_file, arrived_status, vehicle.id, target_location, args.scenario_run_id)
            print(f"Arrived at target status={arrived_status}; vehicle stopped distance={distance:.1f}m", flush=True)
            return

        if time.monotonic() - started_at > args.max_drive_seconds:
            vehicle.apply_control(_stop_control())
            raise RuntimeError(f"Timed out driving to target; last distance={distance:.1f}m")

        if agent.done():
            print(f"BasicAgent route done early while distance={distance:.1f}m; continuing until physically near target", flush=True)

        control = agent.run_step()
        control.manual_gear_shift = False
        vehicle.apply_control(control)
        world.wait_for_tick()
        tick_count += 1
        if tick_count % 20 == 0:
            location = vehicle.get_location()
            print(f"Driving progress distance={distance:.1f}m x={location.x:.1f} y={location.y:.1f}", flush=True)


def _wait_for_reroute_command(path: str, run_id: str) -> None:
    print("Waiting for passenger reroute command", flush=True)
    while True:
        payload = _read_scenario_state(path)
        if payload and (not run_id or payload.get("run_id") == run_id):
            if payload.get("command") == "reroute" or payload.get("status") == "reroute_requested":
                print("Passenger reroute command received", flush=True)
                return
        time.sleep(0.25)


def _read_scenario_state(path: str) -> dict | None:
    state_path = Path(path)
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return None


def _destroy_existing_heroes(world: object) -> None:
    heroes = [actor for actor in world.get_actors().filter("vehicle.*") if actor.attributes.get("role_name") == "hero"]
    for actor in heroes:
        print(f"Destroying existing hero vehicle id={actor.id}", flush=True)
        actor.destroy()


def _distance(a: object, b: object) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def _stop_control() -> object:
    import carla

    return carla.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True)


def _pull_over_right(vehicle: object, offset_feet: float, max_seconds: float) -> None:
    import carla

    target_offset_meters = abs(offset_feet) * 0.3048
    start_transform = vehicle.get_transform()
    start_location = start_transform.location
    right_vector = start_transform.get_right_vector()
    world = vehicle.get_world()

    print(f"Pulling over right toward curb target_offset={offset_feet:.1f}ft", flush=True)
    started_at = time.monotonic()
    last_lateral = 0.0
    while time.monotonic() - started_at < max_seconds:
        location = vehicle.get_location()
        delta_x = location.x - start_location.x
        delta_y = location.y - start_location.y
        lateral = (delta_x * right_vector.x) + (delta_y * right_vector.y)
        last_lateral = lateral
        if lateral >= target_offset_meters:
            break

        vehicle.apply_control(carla.VehicleControl(throttle=0.22, steer=0.38, brake=0.0, hand_brake=False))
        world.wait_for_tick()

    _straighten_after_pull_over(vehicle, start_transform.rotation.yaw, duration_seconds=2.0)
    vehicle.apply_control(_stop_control())
    print(
        f"Completed curb pull-over lateral={last_lateral / 0.3048:.1f}ft "
        f"target={offset_feet:.1f}ft",
        flush=True,
    )


def _straighten_after_pull_over(vehicle: object, target_yaw: float, duration_seconds: float) -> None:
    import carla

    world = vehicle.get_world()
    started_at = time.monotonic()
    while time.monotonic() - started_at < duration_seconds:
        current_yaw = vehicle.get_transform().rotation.yaw
        yaw_error = _angle_delta(target_yaw, current_yaw)
        if abs(yaw_error) < 2.0:
            break
        steer = max(-0.35, min(0.35, yaw_error / 28.0))
        vehicle.apply_control(carla.VehicleControl(throttle=0.16, steer=steer, brake=0.0, hand_brake=False))
        world.wait_for_tick()

    vehicle.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=0.7, hand_brake=False))
    world.wait_for_tick()


def _angle_delta(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


def _write_scenario_state(path: str, status: str, vehicle_id: int, target_location: object, run_id: str) -> None:
    payload = {
        "status": status,
        "vehicle_id": vehicle_id,
        "run_id": run_id,
        "target": {"x": target_location.x, "y": target_location.y, "z": target_location.z},
        "updated_at": time.time(),
    }
    Path(path).write_text(json.dumps(payload))


if __name__ == "__main__":
    main()
