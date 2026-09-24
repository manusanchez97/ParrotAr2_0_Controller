"""Small, deterministic kinematic model for the loopback-only drone twin."""

from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass, replace

from ardrone.protocol import EMERGENCY_MASK, FLY_MASK


@dataclass(frozen=True, slots=True)
class SimulatedFlightState:
    flying: bool = False
    emergency: bool = False
    battery_percent: int = 87
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    altitude_m: float = 0.0
    vx_m_s: float = 0.0
    vy_m_s: float = 0.0
    vz_m_s: float = 0.0

    @property
    def raw_state(self) -> int:
        return (FLY_MASK if self.flying else 0) | (EMERGENCY_MASK if self.emergency else 0)


class DroneDynamics:
    """Approximate first-order response; intended for software integration only."""

    MAX_TILT_DEG = 20.0
    MAX_HORIZONTAL_SPEED_M_S = 2.0
    MAX_VERTICAL_SPEED_M_S = 1.0
    MAX_YAW_RATE_DEG_S = 90.0
    TAKEOFF_ALTITUDE_M = 0.8

    def __init__(self) -> None:
        self._state = SimulatedFlightState()
        self._controls = (0.0, 0.0, 0.0, 0.0)  # roll, pitch, gaz, yaw
        self._takeoff_requested = False
        self._land_requested = False
        self._emergency_toggle_armed = True
        self._last_update = time.monotonic()
        self._last_at = self._last_update
        self._last_pcmd: float | None = None

    def note_at_command(self) -> None:
        self._last_at = time.monotonic()

    @property
    def state(self) -> SimulatedFlightState:
        self.update()
        return self._state

    def apply_ref(self, flags: int) -> None:
        self.note_at_command()
        if flags & (1 << 8):
            if self._emergency_toggle_armed:
                emergency = not self._state.emergency
                self._state = replace(self._state, emergency=emergency)
                if emergency:
                    self._controls = (0.0, 0.0, 0.0, 0.0)
                    self._takeoff_requested = False
                    self._land_requested = False
                self._emergency_toggle_armed = False
            return
        self._emergency_toggle_armed = True
        if self._state.emergency:
            return
        self._takeoff_requested = bool(flags & (1 << 9))
        self._land_requested = not self._takeoff_requested
        self._controls = (0.0, 0.0, 0.0, 0.0)
        self._last_pcmd = None
        if self._takeoff_requested:
            self._state = replace(self._state, flying=True)

    def apply_pcmd(self, args: bytes) -> None:
        self.note_at_command()
        if self._state.emergency or not self._state.flying or self._land_requested:
            return
        try:
            progressive, *encoded_axes = (int(part) for part in args.split(b","))
        except (ValueError, TypeError):
            return
        if len(encoded_axes) != 4:
            return
        if progressive == 0:
            self._controls = (0.0, 0.0, 0.0, 0.0)
            self._last_pcmd = time.monotonic()
            return
        decoded: list[float] = []
        for value in encoded_axes:
            try:
                axis = struct.unpack("<f", struct.pack("<i", value))[0]
            except struct.error:
                return
            if not math.isfinite(axis):
                return
            decoded.append(max(-1.0, min(1.0, axis)))
        self._controls = (decoded[0], decoded[1], decoded[2], decoded[3])
        self._last_pcmd = time.monotonic()

    def update(self) -> SimulatedFlightState:
        now = time.monotonic()
        dt = min(max(now - self._last_update, 0.0), 0.2)
        self._last_update = now
        if dt == 0.0:
            return self._state

        state = self._state
        if state.flying and now - self._last_at > 2.0:
            self._takeoff_requested = False
            self._land_requested = True
            self._controls = (0.0, 0.0, 0.0, 0.0)
        elif self._last_pcmd is not None and now - self._last_pcmd > 0.5:
            self._controls = (0.0, 0.0, 0.0, 0.0)
            self._last_pcmd = None

        roll_cmd, pitch_cmd, gaz_cmd, yaw_cmd = self._controls
        roll_target = roll_cmd * self.MAX_TILT_DEG if state.flying else 0.0
        pitch_target = pitch_cmd * self.MAX_TILT_DEG if state.flying else 0.0
        blend = min(dt * 4.0, 1.0)
        roll = state.roll_deg + (roll_target - state.roll_deg) * blend
        pitch = state.pitch_deg + (pitch_target - state.pitch_deg) * blend
        yaw = (state.yaw_deg + yaw_cmd * self.MAX_YAW_RATE_DEG_S * dt) % 360.0
        # PCMD pitch/roll are body-frame commands. Rotate their resulting
        # horizontal velocity into the simulator's world frame using yaw.
        body_forward = -pitch_cmd * self.MAX_HORIZONTAL_SPEED_M_S
        body_right = roll_cmd * self.MAX_HORIZONTAL_SPEED_M_S
        heading = math.radians(state.yaw_deg)
        vx = (
            body_forward * math.cos(heading) - body_right * math.sin(heading)
            if state.flying
            else 0.0
        )
        vy = (
            body_forward * math.sin(heading) + body_right * math.cos(heading)
            if state.flying
            else 0.0
        )

        altitude = state.altitude_m
        vz = 0.0
        flying = state.flying
        if state.emergency and altitude > 0.0:
            vz = -2.0
            altitude = max(0.0, altitude + vz * dt)
        elif self._takeoff_requested and altitude < self.TAKEOFF_ALTITUDE_M:
            vz = 0.7
            altitude = min(self.TAKEOFF_ALTITUDE_M, altitude + vz * dt)
        elif self._land_requested and altitude > 0.0:
            vz = -0.5
            altitude = max(0.0, altitude + vz * dt)
        elif flying:
            vz = gaz_cmd * self.MAX_VERTICAL_SPEED_M_S
            altitude = max(0.0, altitude + vz * dt)
        if altitude < 1e-9:
            altitude = 0.0
        if altitude == 0.0 and (self._land_requested or state.emergency):
            flying = False
            self._land_requested = False
            self._controls = (0.0, 0.0, 0.0, 0.0)
            roll = pitch = vx = vy = vz = 0.0
        self._state = SimulatedFlightState(
            flying=flying,
            emergency=state.emergency,
            battery_percent=state.battery_percent,
            roll_deg=roll,
            pitch_deg=pitch,
            yaw_deg=yaw,
            altitude_m=altitude,
            vx_m_s=vx,
            vy_m_s=vy,
            vz_m_s=vz,
        )
        return self._state
