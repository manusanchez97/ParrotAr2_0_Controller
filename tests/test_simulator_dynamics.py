from __future__ import annotations

import math

import pytest

from ardrone.commands import AtCommandEncoder
from ardrone.protocol import FLY_MASK
from simulator import dynamics
from simulator.dynamics import DroneDynamics, SimulatedFlightState


class FakeClock:
    def __init__(self) -> None:
        self.now = 10.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _pcmd_args(*, roll: float = 0.0, pitch: float = 0.0) -> bytes:
    command = AtCommandEncoder().pcmd(roll=roll, pitch=pitch)
    return command.split(b",", 1)[1].rstrip(b"\r")


def test_forward_velocity_rotates_with_drone_yaw(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(dynamics.time, "monotonic", clock.monotonic)
    drone = DroneDynamics()
    drone._state = SimulatedFlightState(flying=True, altitude_m=0.8, yaw_deg=90.0)
    drone.apply_pcmd(_pcmd_args(pitch=-0.25))

    clock.advance(0.1)
    state = drone.update()

    assert state.vx_m_s == pytest.approx(0.0, abs=1e-6)
    assert state.vy_m_s == pytest.approx(0.5)


def test_takeoff_and_land_reach_expected_states(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(dynamics.time, "monotonic", clock.monotonic)
    drone = DroneDynamics()

    drone.apply_ref(AtCommandEncoder.TAKEOFF_FLAGS)
    assert drone.state.flying
    for _ in range(math.ceil(drone.TAKEOFF_ALTITUDE_M / (0.7 * 0.2))):
        clock.advance(0.2)
        state = drone.update()
    assert state.altitude_m == pytest.approx(drone.TAKEOFF_ALTITUDE_M)

    drone.apply_ref(AtCommandEncoder.LAND_FLAGS)
    for _ in range(math.ceil(drone.TAKEOFF_ALTITUDE_M / (0.5 * 0.2))):
        clock.advance(0.2)
        state = drone.update()
    assert state.altitude_m == pytest.approx(0.0)
    assert not state.flying
    assert not state.raw_state & FLY_MASK
