import struct

import pytest

from ardrone.navdata import NavdataError, parse_navdata
from ardrone.protocol import NAVDATA_HEADER
from ardrone.state import FlightState


def packet(*, raw_state: int = 0, sequence: int = 7, corrupt: bool = False) -> bytes:
    header = struct.pack("<IIII", NAVDATA_HEADER, raw_state, sequence, 0)
    demo_payload = struct.pack(
        "<IIfffifff", 2 << 16, 83, -1200.0, 400.0, 63500.0, 1234, 10.0, -20.0, 30.0
    )
    body = header + struct.pack("<HH", 0, len(demo_payload) + 4) + demo_payload
    checksum = (sum(body) + int(corrupt)) & 0xFFFFFFFF
    return body + struct.pack("<HHI", 0xFFFF, 8, checksum)


def test_parses_demo_units_and_control_state() -> None:
    nav = parse_navdata(packet())
    assert nav.sequence == 7
    assert nav.checksum_valid
    assert nav.demo is not None
    assert nav.demo.flight_state is FlightState.LANDED
    assert nav.demo.control_state == 2
    assert nav.demo.battery_percent == 83
    assert nav.demo.roll_deg == pytest.approx(0.4)
    assert nav.demo.pitch_deg == pytest.approx(-1.2)
    assert nav.demo.yaw_deg == pytest.approx(63.5)
    assert nav.demo.altitude_m == pytest.approx(1.234)
    assert nav.demo.vy_m_s == pytest.approx(-0.02)


def test_state_masks_prioritize_emergency() -> None:
    nav = parse_navdata(packet(raw_state=(1 << 0) | (1 << 31)))
    assert nav.demo is not None
    assert nav.demo.flight_state is FlightState.EMERGENCY


@pytest.mark.parametrize(
    "bad_packet, message",
    [
        (b"short", "shorter"),
        (struct.pack("<IIII", 0, 0, 1, 0), "header"),
        (packet(sequence=0), "non-zero"),
        (packet(corrupt=True), "mismatch"),
    ],
)
def test_rejects_malformed_packets(bad_packet: bytes, message: str) -> None:
    with pytest.raises(NavdataError, match=message):
        parse_navdata(bad_packet)


def test_rejects_zero_sized_option_without_looping() -> None:
    raw = struct.pack("<IIIIHH", NAVDATA_HEADER, 0, 1, 0, 3, 0)
    with pytest.raises(NavdataError, match="option size"):
        parse_navdata(raw, require_checksum=False)

