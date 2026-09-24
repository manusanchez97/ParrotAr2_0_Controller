"""Recoverable receive session for validated NavData."""

from __future__ import annotations

import socket
import time

from .commands import AtCommandEncoder
from .navdata import Navdata, NavdataError, parse_navdata
from .transport import DroneTransport


class NavdataTimeout(TimeoutError):
    pass


class NavdataClient:
    def __init__(
        self,
        transport: DroneTransport | None = None,
        retries: int = 2,
        *,
        config_ids: tuple[str, str, str] | None = None,
    ) -> None:
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.transport = transport or DroneTransport()
        self.retries = retries
        self.config_ids = config_ids
        self.commands = AtCommandEncoder()
        self._config_sent = False
        self._ack_sent = False
        self.last_received_at: float | None = None
        self.invalid_packets = 0

        if config_ids is not None and (
            len(config_ids) != 3
            or any(
                not value
                or not value.isascii()
                or any(ch in value for ch in '\\"\r\n')
                for value in config_ids
            )
        ):
            raise ValueError("config_ids must contain three non-empty ASCII values without quotes")

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

    def initialize_demo(self, timeout: float = 8.0) -> Navdata:
        """Negotiate demo NavData using CONFIG and the observed CTRL ACK bit."""
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                navdata = self.receive()
            except NavdataTimeout:
                # Individual UDP waits are expected during startup. receive()
                # already retriggers NavData; keep negotiating until the
                # overall initialization deadline expires.
                continue
            if (
                navdata.demo is not None
                and not navdata.is_bootstrap
                and not navdata.command_pending
            ):
                return navdata
            if navdata.is_bootstrap and not self._config_sent:
                if self.config_ids is not None:
                    self.transport.send_at(self.commands.config_ids(self.config_ids))
                self.transport.send_at(self.commands.configure_demo())
                self._config_sent = True
            if navdata.command_pending and not self._ack_sent:
                self.transport.send_at(self.commands.acknowledge_config())
                self._ack_sent = True
            if self._ack_sent and not navdata.command_pending:
                self._ack_sent = False
        raise NavdataTimeout("NavData demo initialization timed out")

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "NavdataClient":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

