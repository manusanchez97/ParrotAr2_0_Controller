"""Pure AT command encoding for configuration and simulator control."""

from __future__ import annotations

import math
import struct


class AtCommandEncoder:
    """Encode AT commands with one monotonically increasing session sequence."""

    TAKEOFF_FLAGS = 290718208
    LAND_FLAGS = 290717696

    def __init__(self) -> None:
        self.sequence = 0

    def encode(self, name: str, arguments: str = "") -> bytes:
        if (
            not name.isascii()
            or not name.replace("_", "").isalnum()
            or not name.isupper()
        ):
            raise ValueError("invalid AT command name")
        if any(char in arguments for char in "\r\n"):
            raise ValueError("AT arguments cannot contain line breaks")
        self.sequence += 1
        line = f"AT*{name}={self.sequence}{',' if arguments else ''}{arguments}\r"
        return line.encode("ascii")

    def config_ids(self, ids: tuple[str, str, str]) -> bytes:
        if len(ids) != 3 or any(
            not value
            or not value.isascii()
            or any(char in value for char in '\\"\r\n')
            for value in ids
        ):
            raise ValueError("config IDs must be three non-empty ASCII values")
        return self.encode("CONFIG_IDS", ",".join(f'"{value}"' for value in ids))

    def configure_demo(self) -> bytes:
        return self.encode("CONFIG", '"general:navdata_demo","TRUE"')

    def acknowledge_config(self) -> bytes:
        return self.encode("CTRL", "5,0")

    def ref(self, flags: int) -> bytes:
        if not isinstance(flags, int) or flags < 0 or flags > 0xFFFFFFFF:
            raise ValueError("REF flags must be an unsigned 32-bit integer")
        return self.encode("REF", str(flags))

    def takeoff(self) -> bytes:
        return self.ref(self.TAKEOFF_FLAGS)

    def land(self) -> bytes:
        return self.ref(self.LAND_FLAGS)

    def pcmd(
        self,
        roll: float = 0.0,
        pitch: float = 0.0,
        gaz: float = 0.0,
        yaw: float = 0.0,
        *,
        progressive: bool = True,
    ) -> bytes:
        axes = (roll, pitch, gaz, yaw)
        values: list[str] = []
        for axis in axes:
            if not math.isfinite(axis) or not -1.0 <= axis <= 1.0:
                raise ValueError("PCMD axes must be finite and within [-1, 1]")
            bits = struct.unpack("<i", struct.pack("<f", axis))[0]
            values.append(str(bits))
        args = f"{int(progressive)},{','.join(values)}"
        return self.encode("PCMD", args)

    def comwdg(self) -> bytes:
        return self.encode("COMWDG")
