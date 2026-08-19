"""Small cross-platform UDP transport; works with CPython's Winsock backend."""

from __future__ import annotations

import socket

from .protocol import COMMAND_PORT, DRONE_IP, NAVDATA_PORT, NAVDATA_TRIGGER


class DroneTransport:
    def __init__(self, drone_ip: str = DRONE_IP, timeout: float = 1.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.drone_ip = drone_ip
        self.timeout = timeout
        self._command: socket.socket | None = None
        self._navdata: socket.socket | None = None

    @property
    def local_ip(self) -> str:
        sock = self._require_command()
        return str(sock.getsockname()[0])

    def open(self) -> None:
        if self._command is not None or self._navdata is not None:
            return
        command = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        navdata = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            command.settimeout(self.timeout)
            command.connect((self.drone_ip, COMMAND_PORT))
            navdata.settimeout(self.timeout)
            # An ephemeral local port avoids conflicts with other drone clients.
            navdata.bind(("", 0))
            self._command, self._navdata = command, navdata
        except BaseException:
            command.close()
            navdata.close()
            raise

    def request_navdata(self) -> None:
        self._require_navdata().sendto(NAVDATA_TRIGGER, (self.drone_ip, NAVDATA_PORT))

    def receive_navdata(self, maximum: int = 65535) -> tuple[bytes, tuple[str, int]]:
        return self._require_navdata().recvfrom(maximum)

    def _require_command(self) -> socket.socket:
        if self._command is None:
            raise RuntimeError("transport is not open")
        return self._command

    def _require_navdata(self) -> socket.socket:
        if self._navdata is None:
            raise RuntimeError("transport is not open")
        return self._navdata

    def close(self) -> None:
        command, navdata = self._command, self._navdata
        self._command = self._navdata = None
        if navdata is not None:
            navdata.close()
        if command is not None:
            command.close()

    def __enter__(self) -> "DroneTransport":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

