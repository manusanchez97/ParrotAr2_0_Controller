"""Flight command interface restricted to loopback simulator sessions."""

from __future__ import annotations

import ipaddress

from ardrone.client import NavdataClient


class SimulatorFlightControls:
    """Send simulated flight commands only when NavDataClient targets loopback."""

    def __init__(self, client: NavdataClient) -> None:
        address = ipaddress.ip_address(client.transport.drone_ip)
        if address.version != 4 or not address.is_loopback:
            raise ValueError("simulated flight controls require an IPv4 loopback target")
        self.client = client

    def takeoff(self) -> None:
        self.client.transport.send_at(self.client.commands.takeoff())

    def land(self) -> None:
        self.client.transport.send_at(self.client.commands.land())

    def pcmd(
        self, roll: float = 0.0, pitch: float = 0.0, gaz: float = 0.0, yaw: float = 0.0
    ) -> None:
        self.client.transport.send_at(
            self.client.commands.pcmd(
                roll, pitch, gaz, yaw, progressive=any((roll, pitch, gaz, yaw))
            )
        )
