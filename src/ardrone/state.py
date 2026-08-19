"""Stable application-facing telemetry types."""

from dataclasses import dataclass
from enum import Enum


class FlightState(str, Enum):
    LANDED = "LANDED"
    FLYING = "FLYING"
    EMERGENCY = "EMERGENCY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DroneState:
    flight_state: FlightState
    control_state: int
    raw_state: int
    battery_percent: int
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    altitude_m: float
    vx_m_s: float
    vy_m_s: float
    vz_m_s: float

