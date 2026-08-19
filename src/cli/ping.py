"""Protocol-level network diagnostics (does not use ICMP)."""

from __future__ import annotations

import argparse

from ardrone.client import NavdataClient, NavdataTimeout
from ardrone.protocol import DRONE_IP
from ardrone.transport import DroneTransport


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", default=DRONE_IP, help="drone IPv4 address")
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()
    transport = DroneTransport(args.ip, args.timeout)
    print("AR.Drone 2.0 network diagnostics\n")
    print(f"Target IP:          {args.ip}")
    try:
        with NavdataClient(transport, retries=2) as client:
            print(f"Local interface:    {transport.local_ip}\n")
            print("Command socket:     OK")
            print("NavData socket:     OK\n")
            packet = client.receive()
            detail = "NavData valid" if packet.demo is not None else "NavData valid (no demo option)"
            print(f"Drone communication: OK ({detail})")
            return 0
    except (OSError, NavdataTimeout) as exc:
        print(f"Drone communication: FAILED ({exc})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
