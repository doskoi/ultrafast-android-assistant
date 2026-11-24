from __future__ import annotations

import pytest

from jev_android_assistant.policy import JevClient


@pytest.mark.parametrize("variable", ["ULTRAFAST_SECONDARY_PROVIDER", "ULTRAFAST_FALLBACK_PROVIDER"])
def test_rejects_a_removed_provider(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv("ULTRAFAST_PRIMARY_PROVIDER", "jev")
    monkeypatch.setenv("ULTRAFAST_SECONDARY_PROVIDER", "none")
    monkeypatch.setenv("ULTRAFAST_FALLBACK_PROVIDER", "none")
    monkeypatch.setenv(variable, "laya")

    with pytest.raises(ValueError, match=f"{variable} selects a removed provider"):
        JevClient().system_one({}, {})


@pytest.mark.parametrize("value", ["", "none", "off", "disabled", " DISABLED "])
def test_accepts_a_disabled_secondary_or_fallback(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("ULTRAFAST_PRIMARY_PROVIDER", "jev")
    monkeypatch.setenv("ULTRAFAST_SECONDARY_PROVIDER", value)
    monkeypatch.setenv("ULTRAFAST_FALLBACK_PROVIDER", value)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TypeSafe Jev unavailable"):
        JevClient().system_one({}, {})
