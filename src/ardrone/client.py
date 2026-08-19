"""Recoverable receive session for validated NavData."""

from __future__ import annotations

import socket
import time

from .navdata import Navdata, NavdataError, parse_navdata
from .transport import DroneTransport


class NavdataTimeout(TimeoutError):
    pass


class NavdataClient:
    def __init__(self, transport: DroneTransport | None = None, retries: int = 2) -> None:
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.transport = transport or DroneTransport()
        self.retries = retries
        self.last_received_at: float | None = None
        self.invalid_packets = 0

    def open(self) -> None:
        self.transport.open()
        self.transport.request_navdata()

    def receive(self) -> Navdata:
        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                packet, sender = self.transport.receive_navdata()
                if sender[0] != self.transport.drone_ip:
                    self.invalid_packets += 1
                    continue
                navdata = parse_navdata(packet)
                self.last_received_at = time.perf_counter()
                return navdata
            except (socket.timeout, TimeoutError) as exc:
                last_error = exc
                # UDP has no connection state: retriggering is the recovery probe.
                self.transport.request_navdata()
            except NavdataError as exc:
                self.invalid_packets += 1
                last_error = exc
        raise NavdataTimeout("no valid NavData received after retrying") from last_error

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "NavdataClient":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

