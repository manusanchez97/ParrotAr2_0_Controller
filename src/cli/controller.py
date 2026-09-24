"""Keyboard controller for the loopback AR.Drone simulator only."""

from __future__ import annotations

import argparse
import os
import time

from ardrone.client import NavdataClient, NavdataTimeout
from ardrone.state import DroneState, FlightState
from ardrone.transport import DroneTransport
from controller.map3d import FlightPath, IsometricMap
from simulator.controller import SimulatorFlightControls

SIMULATOR_IP = "127.0.0.1"
_POLL_SECONDS = 1.0 / 30.0


def _screen(
    state: DroneState | None,
    age: float,
    axes: tuple[float, float, float, float],
) -> str:
    if state is None:
        return (
            "AR.Drone 2.0 — SIMULATOR\n\n"
            "Connection   127.0.0.1\n"
            "State        WAITING FOR NAVDATA\n"
            f"NavData      waiting ({age:.2f} s)\n\n"
            "T takeoff   L land   ESC land and quit\n"
        )
    return (
        "AR.Drone 2.0 — SIMULATOR\n\n"
        "Connection   127.0.0.1\n"
        f"Battery      {state.battery_percent:3d} %\n"
        f"State        {state.flight_state.value}\n\n"
        f"Roll         {state.roll_deg:7.1f}°\n"
        f"Pitch        {state.pitch_deg:7.1f}°\n"
        f"Yaw          {state.yaw_deg:7.1f}°\n\n"
        f"Altitude     {state.altitude_m:7.2f} m\n\n"
        f"VX           {state.vx_m_s:7.2f} m/s\n"
        f"VY           {state.vy_m_s:7.2f} m/s\n"
        f"VZ           {state.vz_m_s:7.2f} m/s\n\n"
        f"NavData      {'OK' if age <= 0.5 else 'STALE'} ({age:.2f} s)\n"
        f"Input        roll={axes[0]:+.2f} pitch={axes[1]:+.2f} "
        f"gaz={axes[2]:+.2f} yaw={axes[3]:+.2f}\n\n"
        "T takeoff   L land   ESC land and quit\n"
        "W/S pitch   A/D roll   R/F gaz   Q/E yaw\n"
    )


def _held_axes() -> tuple[float, float, float, float]:
    """Read held WASD/RF/QE keys via the Windows asynchronous key state API."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    get_foreground = user32.GetForegroundWindow
    get_foreground.restype = wintypes.HWND
    get_console = ctypes.windll.kernel32.GetConsoleWindow
    get_console.restype = wintypes.HWND
    console = get_console()
    # Windows Terminal uses a hidden pseudoconsole HWND; compare focus when the
    # classic console window is visible, and otherwise rely on sampled key state.
    if user32.IsWindowVisible(console) and get_foreground() != console:
        return 0.0, 0.0, 0.0, 0.0

    def down(vk: int) -> bool:
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    forward = down(ord("W"))
    backward = down(ord("S"))
    left = down(ord("A"))
    right = down(ord("D"))
    up = down(ord("R"))
    down_key = down(ord("F"))
    yaw_left = down(ord("Q"))
    yaw_right = down(ord("E"))
    # Invert the roll axis so A/D produce left/right motion in the local map.
    roll = (int(left) - int(right)) * 0.25
    pitch = (int(backward) - int(forward)) * 0.25
    gaz = (int(up) - int(down_key)) * 0.25
    yaw = (int(yaw_right) - int(yaw_left)) * 0.25
    return roll, pitch, gaz, yaw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--simulator",
        action="store_true",
        help="required: connect only to the local UDP simulator at 127.0.0.1",
    )
    parser.add_argument("--refresh", type=float, default=0.2, help="screen refresh seconds")
    parser.add_argument("--no-map", action="store_true", help="disable the 3D map window")
    args = parser.parse_args()
    if not args.simulator:
        parser.error("this controller is simulator-only; pass --simulator")
    if args.refresh <= 0:
        parser.error("--refresh must be positive")
    if os.name != "nt":
        parser.error("keyboard control currently requires Windows")

    import msvcrt

    client = NavdataClient(DroneTransport(SIMULATOR_IP, timeout=0.02), retries=0)
    controls = SimulatorFlightControls(client)
    latest = None
    last_draw = 0.0
    stopping = False
    flight_command_pending: str | None = None
    flight_command_started_at = 0.0
    flight_command_last_sent_at = 0.0
    last_takeoff_attempt = 0.0
    last_land_attempt = 0.0
    flight_path = FlightPath()
    map_view = None
    print("Connecting to simulator at 127.0.0.1; no external address is configurable.")
    try:
        client.open()
        latest = client.initialize_demo(timeout=5.0)
        if latest.demo is not None and client.last_received_at is not None:
            flight_path.update(latest.sequence, client.last_received_at, latest.demo)
        if not args.no_map:
            try:
                map_view = IsometricMap()
            except (ImportError, RuntimeError) as exc:
                print(f"3D map unavailable ({exc}); continuing with telemetry panel only.")
        print("Demo NavData ready.")
        while not stopping:
            now_data = time.perf_counter()
            try:
                latest = client.receive()
                if latest.demo is not None and client.last_received_at is not None:
                    flight_path.update(latest.sequence, client.last_received_at, latest.demo)
            except NavdataTimeout:
                pass

            while msvcrt.kbhit():
                key = msvcrt.getch()
                if key in (b"\x00", b"\xe0"):
                    msvcrt.getch()
                    continue
                key = key.lower()
                fresh = (
                    latest is not None
                    and client.last_received_at is not None
                    and now_data - client.last_received_at <= 0.5
                    and latest.demo is not None
                )
                if key == b"\x1b":
                    stopping = True
                elif key == b"t" and fresh and latest.demo.flight_state is FlightState.LANDED:
                    if time.monotonic() - last_takeoff_attempt >= 0.5:
                        controls.takeoff()
                        last_takeoff_attempt = time.monotonic()
                        flight_command_pending = "takeoff"
                        flight_command_started_at = last_takeoff_attempt
                        flight_command_last_sent_at = last_takeoff_attempt
                elif key == b"l" and fresh and latest.demo.flight_state is FlightState.FLYING:
                    if time.monotonic() - last_land_attempt >= 0.5:
                        controls.land()
                        last_land_attempt = time.monotonic()
                        flight_command_pending = "land"
                        flight_command_started_at = last_land_attempt
                        flight_command_last_sent_at = last_land_attempt

            fresh_navdata = (
                latest is not None
                and latest.demo is not None
                and client.last_received_at is not None
                and time.perf_counter() - client.last_received_at <= 0.5
            )

            # REF changes a requested state; keep retrying briefly until fresh
            # NavData confirms the transition, even if the key was tapped once.
            if fresh_navdata and flight_command_pending is not None:
                flight_state = latest.demo.flight_state
                if (
                    flight_command_pending == "takeoff"
                    and flight_state is FlightState.FLYING
                ) or (
                    flight_command_pending == "land"
                    and flight_state is FlightState.LANDED
                ):
                    flight_command_pending = None
                elif time.monotonic() - flight_command_started_at < 2.0:
                    if time.monotonic() - flight_command_last_sent_at >= 0.4:
                        if flight_command_pending == "takeoff" and flight_state is FlightState.LANDED:
                            controls.takeoff()
                            flight_command_last_sent_at = time.monotonic()
                        elif flight_command_pending == "land" and flight_state is FlightState.FLYING:
                            controls.land()
                            flight_command_last_sent_at = time.monotonic()
                else:
                    flight_command_pending = None

            axes = _held_axes()

            if (
                fresh_navdata
                and latest.demo.flight_state is FlightState.FLYING
                and not stopping
            ):
                controls.pcmd(*axes)

            if time.monotonic() - last_draw >= args.refresh:
                age = (
                    time.perf_counter() - client.last_received_at
                    if client.last_received_at is not None
                    else float("inf")
                )
                state = latest.demo if latest is not None else None
                print("\x1b[2J\x1b[H" + _screen(state, age, axes), end="", flush=True)
                if (
                    map_view is not None
                    and state is not None
                    and client.last_received_at is not None
                ):
                    map_view.update(flight_path, state, age)
                last_draw = time.monotonic()
            time.sleep(_POLL_SECONDS)
    except (OSError, NavdataTimeout, RuntimeError) as exc:
        print(f"\nController unavailable: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nController interrupted.")
    finally:
        if (
            latest is not None
            and latest.demo is not None
            and latest.demo.flight_state is FlightState.FLYING
        ):
            try:
                controls.land()
            except (OSError, RuntimeError):
                pass
        client.close()
        if map_view is not None:
            map_view.close()
        print("\nSimulator controller stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
