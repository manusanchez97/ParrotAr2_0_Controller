"""Pure parser for the little-endian AR.Drone NavData datagram."""

from dataclasses import dataclass
import struct

from .protocol import (
    EMERGENCY_MASK,
    FLY_MASK,
    NAVDATA_CHECKSUM_TAG,
    NAVDATA_DEMO_TAG,
    NAVDATA_HEADER,
)
from .state import DroneState, FlightState

_HEADER = struct.Struct("<IIII")
_OPTION_HEADER = struct.Struct("<HH")
# navdata_demo_t fields through velocity; the remainder is optional to this MVP.
_DEMO_PREFIX = struct.Struct("<IIfffifff")


class NavdataError(ValueError):
    """Raised for a malformed, incomplete, or checksum-invalid datagram."""


@dataclass(frozen=True, slots=True)
class Navdata:
    sequence: int
    vision_defined: int
    raw_state: int
    demo: DroneState | None
    checksum_valid: bool


def _flight_state(raw_state: int) -> FlightState:
    if raw_state & EMERGENCY_MASK:
        return FlightState.EMERGENCY
    return FlightState.FLYING if raw_state & FLY_MASK else FlightState.LANDED


def parse_navdata(packet: bytes, *, require_checksum: bool = True) -> Navdata:
    """Parse one datagram without retaining state or performing network I/O."""
    if len(packet) < _HEADER.size:
        raise NavdataError("datagram shorter than the 16-byte NavData header")
    header, raw_state, sequence, vision = _HEADER.unpack_from(packet)
    if header != NAVDATA_HEADER:
        raise NavdataError(f"invalid NavData header 0x{header:08x}")
    if sequence == 0:
        raise NavdataError("NavData sequence number must be non-zero")

    offset = _HEADER.size
    demo: DroneState | None = None
    checksum_seen = False
    checksum_valid = False
    while offset < len(packet):
        if len(packet) - offset < _OPTION_HEADER.size:
            raise NavdataError("truncated option header")
        tag, size = _OPTION_HEADER.unpack_from(packet, offset)
        if size < _OPTION_HEADER.size:
            raise NavdataError(f"invalid option size {size} for tag {tag}")
        end = offset + size
        if end > len(packet):
            raise NavdataError(f"option tag {tag} extends past datagram")

        payload_offset = offset + _OPTION_HEADER.size
        payload_size = size - _OPTION_HEADER.size
        if tag == NAVDATA_DEMO_TAG:
            if payload_size < _DEMO_PREFIX.size:
                raise NavdataError("NavData demo option is truncated")
            values = _DEMO_PREFIX.unpack_from(packet, payload_offset)
            control_state, battery, theta, phi, psi, altitude, vx, vy, vz = values
            demo = DroneState(
                flight_state=_flight_state(raw_state),
                control_state=control_state >> 16,
                raw_state=raw_state,
                battery_percent=battery,
                roll_deg=phi / 1000.0,
                pitch_deg=theta / 1000.0,
                yaw_deg=psi / 1000.0,
                altitude_m=altitude / 1000.0,
                vx_m_s=vx / 1000.0,
                vy_m_s=vy / 1000.0,
                vz_m_s=vz / 1000.0,
            )
        elif tag == NAVDATA_CHECKSUM_TAG:
            if payload_size != 4:
                raise NavdataError("checksum option must contain one uint32")
            expected = struct.unpack_from("<I", packet, payload_offset)[0]
            checksum_valid = (sum(packet[:offset]) & 0xFFFFFFFF) == expected
            checksum_seen = True
            if end != len(packet):
                raise NavdataError("checksum is not the final option")
        offset = end

    if require_checksum and not checksum_seen:
        raise NavdataError("NavData checksum option is missing")
    if checksum_seen and not checksum_valid:
        raise NavdataError("NavData checksum mismatch")
    return Navdata(sequence, vision, raw_state, demo, checksum_valid)

