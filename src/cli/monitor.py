"""Read-only, in-place AR.Drone 2.0 telemetry monitor."""

from __future__ import annotations

import argparse
import time

from ardrone.client import NavdataClient, NavdataTimeout
from ardrone.protocol import DRONE_IP
from ardrone.transport import DroneTransport


def _clear() -> None:
    # ANSI works in current Windows Terminal/PowerShell; fallback remains readable.
    print("\x1b[2J\x1b[H", end="")


def _screen(state: object, age: float) -> str:
    return (
        "AR.Drone 2.0\n\n"
        "Connection   OK\n"
        f"Battery      {state.battery_percent:3d} %\n"
        f"State        {state.flight_state.value}\n\n"
        f"Roll         {state.roll_deg:7.1f}°\n"
        f"Pitch        {state.pitch_deg:7.1f}°\n"
        f"Yaw          {state.yaw_deg:7.1f}°\n\n"
        f"Altitude     {state.altitude_m:7.2f} m\n\n"
        f"VX           {state.vx_m_s:7.2f} m/s\n"
        f"VY           {state.vy_m_s:7.2f} m/s\n"
        f"VZ           {state.vz_m_s:7.2f} m/s\n\n"
        f"NavData      OK ({age:.2f} s)\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", default=DRONE_IP)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--refresh", type=float, default=0.2, help="display refresh seconds")
    args = parser.parse_args()
    if args.refresh <= 0:
        parser.error("--refresh must be positive")
    client = NavdataClient(DroneTransport(args.ip, args.timeout), retries=2)
    last_draw = 0.0
    try:
        client.open()
        while True:
            navdata = client.receive()
            if navdata.demo is None:
                raise RuntimeError(
                    "NavData demo option absent; configure navdata_demo=TRUE using a trusted SDK client"
                )
            now = time.perf_counter()
            if now - last_draw >= args.refresh:
                _clear()
                received = client.last_received_at or now
                print(_screen(navdata.demo, now - received), end="", flush=True)
                last_draw = now
    except KeyboardInterrupt:
        print("\nMonitor stopped; sockets closed. No flight command was sent.")
        return 0
    except (OSError, NavdataTimeout, RuntimeError) as exc:
        print(f"\nNavData unavailable: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
