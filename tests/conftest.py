from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_model_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests use injected clients and must never inherit credentials or local model routing."""
    import os

    for variable in tuple(os.environ):
        if variable.startswith(("LAYA_MLX_", "ULTRAFAST_", "TYPESAFE_")):
            monkeypatch.delenv(variable)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is forbidden in this test suite")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
