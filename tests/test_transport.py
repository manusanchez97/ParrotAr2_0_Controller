import socket

import pytest

from ardrone.transport import DroneTransport


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError):
        DroneTransport(timeout=0)


def test_closed_transport_rejects_operations() -> None:
    transport = DroneTransport()
    with pytest.raises(RuntimeError, match="not open"):
        transport.request_navdata()
    with pytest.raises(RuntimeError, match="not open"):
        transport.receive_navdata()


def test_open_and_close_are_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    created = []

    class FakeSocket:
        def __init__(self, *_: object) -> None:
            self.closed = False
            self.address = ("192.168.1.20", 49152)
            created.append(self)

        def settimeout(self, timeout: float) -> None:
            assert timeout == 0.25

        def connect(self, target: tuple[str, int]) -> None:
            assert target == ("192.168.1.1", 5556)

        def bind(self, target: tuple[str, int]) -> None:
            assert target == ("", 0)

        def getsockname(self) -> tuple[str, int]:
            return self.address

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(socket, "socket", FakeSocket)
    transport = DroneTransport(timeout=0.25)
    transport.open()
    transport.open()
    assert transport.local_ip == "192.168.1.20"
    assert len(created) == 2
    transport.close()
    transport.close()
    assert all(sock.closed for sock in created)

