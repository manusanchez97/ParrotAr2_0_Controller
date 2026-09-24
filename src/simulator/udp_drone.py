"""Loopback UDP endpoint for NavData, AT configuration and basic flight dynamics."""

from __future__ import annotations

import ipaddress
import re
import select
import socket
import struct
import threading
import time
from dataclasses import dataclass

from ardrone.protocol import (
    COMMAND_MASK,
    COMMAND_PORT,
    NAVDATA_BOOTSTRAP_MASK,
    NAVDATA_CHECKSUM_TAG,
    NAVDATA_DEMO_TAG,
    NAVDATA_HEADER,
    NAVDATA_PORT,
    NAVDATA_TRIGGER,
)
from .dynamics import DroneDynamics, SimulatedFlightState

_HEADER = struct.Struct("<IIII")
_OPTION = struct.Struct("<HH")
_DEMO = struct.Struct("<IIfffifff")
_SEQ = re.compile(rb"^AT\*([A-Z0-9_]+)=(\d+)(?:,(.*))?$", re.DOTALL)
_CONFIG_ARGS = re.compile(rb'^"([^"\\]*)","([^"\\]*)"$')


@dataclass(frozen=True, slots=True)
class SimulatorSnapshot:
    navdata_sequence: int
    navdata_clients: int
    demo_enabled: bool
    command_pending: bool
    config_ids: tuple[str, str, str] | None
    unsupported_commands: int
    flight: SimulatedFlightState


def _navdata_packet(
    sequence: int,
    flight: SimulatedFlightState,
    *,
    bootstrap: bool,
    command_pending: bool,
) -> bytes:
    state = flight.raw_state | (NAVDATA_BOOTSTRAP_MASK if bootstrap else 0) | (
        COMMAND_MASK if command_pending else 0
    )
    body = bytearray(_HEADER.pack(NAVDATA_HEADER, state, sequence, 0))
    if not bootstrap:
        demo = _DEMO.pack(
            0,
            flight.battery_percent,
            flight.pitch_deg * 1000.0,
            flight.roll_deg * 1000.0,
            flight.yaw_deg * 1000.0,
            round(flight.altitude_m * 1000.0),
            flight.vx_m_s * 1000.0,
            flight.vy_m_s * 1000.0,
            flight.vz_m_s * 1000.0,
        )
        body.extend(_OPTION.pack(NAVDATA_DEMO_TAG, _OPTION.size + len(demo)))
        body.extend(demo)
    checksum = sum(body) & 0xFFFFFFFF
    body.extend(_OPTION.pack(NAVDATA_CHECKSUM_TAG, 8))
    body.extend(struct.pack("<I", checksum))
    return bytes(body)


class UdpDroneSimulator:
    """Serve NavData, configuration and simulated flight commands on loopback."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        *,
        navdata_port: int = NAVDATA_PORT,
        command_port: int = COMMAND_PORT,
        demo_hz: float = 15.0,
    ) -> None:
        if not 0 < demo_hz <= 200:
            raise ValueError("demo_hz must be in (0, 200]")
        bind_address = ipaddress.ip_address(host)
        if bind_address.version != 4 or not bind_address.is_loopback:
            raise ValueError("the simulator can bind only to a loopback IPv4 address")
        self.host = host
        self.navdata_port = navdata_port
        self.command_port = command_port
        self.demo_hz = demo_hz
        self._nav_socket: socket.socket | None = None
        self._at_socket: socket.socket | None = None
        self._stop = threading.Event()
        self._nav_peers: dict[tuple[str, int], float] = {}
        self._sequence = 0
        self._last_at_sequences: dict[tuple[str, int], int] = {}
        self._demo_enabled = False
        self._command_pending = False
        self._config_ids: tuple[str, str, str] | None = None
        self._unsupported_commands = 0
        self._dynamics = DroneDynamics()

    @property
    def snapshot(self) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            self._sequence,
            len(self._nav_peers),
            self._demo_enabled,
            self._command_pending,
            self._config_ids,
            self._unsupported_commands,
            self._dynamics.state,
        )

    def serve_forever(self) -> None:
        if self._nav_socket is not None or self._at_socket is not None:
            raise RuntimeError("simulator is already running")
        nav = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        at = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            nav.bind((self.host, self.navdata_port))
            at.bind((self.host, self.command_port))
            nav.setblocking(False)
            at.setblocking(False)
            self._nav_socket, self._at_socket = nav, at
            print(
                "UDP drone simulator listening on "
                f"{self.host}:{self.navdata_port}/{self.command_port}"
            )
            next_frame = time.monotonic()
            while not self._stop.is_set():
                ready, _, _ = select.select([nav, at], [], [], 0.05)
                for sock in ready:
                    try:
                        packet, peer = sock.recvfrom(4096)
                    except ConnectionResetError:
                        # Winsock reports ICMP port-unreachable on a UDP socket
                        # after a client closes its ephemeral NavData endpoint.
                        # ICMP does not identify which UDP peer closed. Keep
                        # the remaining clients and let inactive peers expire.
                        continue
                    if sock is nav:
                        self._handle_navdata(packet, peer)
                    else:
                        self._handle_at(packet, peer)
                if self._nav_peers and time.monotonic() >= next_frame:
                    self._send_navdata()
                    next_frame = time.monotonic() + 1.0 / self.demo_hz
        finally:
            self._nav_socket = self._at_socket = None
            nav.close()
            at.close()

    def stop(self) -> None:
        self._stop.set()

    def _handle_navdata(self, packet: bytes, peer: tuple[str, int]) -> None:
        if packet != NAVDATA_TRIGGER:
            return
        self._nav_peers[peer] = time.monotonic()
        self._send_navdata()

    def _send_navdata(self) -> None:
        if not self._nav_peers or self._nav_socket is None:
            return
        now = time.monotonic()
        self._nav_peers = {
            peer: last_seen
            for peer, last_seen in self._nav_peers.items()
            if now - last_seen <= 2.0
        }
        if not self._nav_peers:
            return
        self._sequence = (self._sequence + 1) & 0xFFFFFFFF or 1
        flight = self._dynamics.update()
        packet = _navdata_packet(
            self._sequence,
            flight,
            bootstrap=not self._demo_enabled,
            command_pending=self._command_pending,
        )
        for peer in tuple(self._nav_peers):
            try:
                self._nav_socket.sendto(packet, peer)
            except OSError:
                # A closed client is removed after its two-second lease expires.
                continue

    def _handle_at(self, packet: bytes, peer: tuple[str, int]) -> None:
        for raw_command in packet.split(b"\r"):
            if not raw_command:
                continue
            match = _SEQ.fullmatch(raw_command)
            if match is None:
                continue
            name, raw_sequence, raw_args = match.groups()
            sequence = int(raw_sequence)
            last_sequence = self._last_at_sequences.get(peer, 0)
            if sequence == 0 or sequence <= last_sequence:
                continue
            self._last_at_sequences[peer] = sequence
            self._dynamics.note_at_command()
            if name == b"CONFIG_IDS" and raw_args is not None:
                ids = re.fullmatch(
                    rb'"([A-Za-z0-9_.-]+)","([A-Za-z0-9_.-]+)","([A-Za-z0-9_.-]+)"',
                    raw_args,
                )
                if ids:
                    values = tuple(part.decode("ascii") for part in ids.groups())
                    self._config_ids = (values[0], values[1], values[2])
            elif name == b"CONFIG" and raw_args is not None:
                args = _CONFIG_ARGS.fullmatch(raw_args)
                if (
                    args
                    and args.group(1) == b"general:navdata_demo"
                    and args.group(2).upper() == b"TRUE"
                ):
                    self._command_pending = True
            elif name == b"CTRL" and raw_args == b"5,0" and self._command_pending:
                self._command_pending = False
                self._demo_enabled = True
            elif name == b"REF" and raw_args is not None and self._demo_enabled:
                try:
                    self._dynamics.apply_ref(int(raw_args))
                except ValueError:
                    continue
            elif name == b"PCMD" and raw_args is not None and self._demo_enabled:
                self._dynamics.apply_pcmd(raw_args)
            elif name in (b"PCMD_MAG",):
                self._unsupported_commands += 1


def main() -> int:
    simulator = UdpDroneSimulator()
    try:
        simulator.serve_forever()
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
    except OSError as exc:
        print(f"Unable to start UDP simulator: {exc}")
        return 1
    finally:
        simulator.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
