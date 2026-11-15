from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from test_policy import FakeClient, choice, snapshot

import jev_android_assistant
from jev_android_assistant.policy import JevClient, JevPolicy


def click_response(probability: float = 0.8) -> object:
    return SimpleNamespace(
        model="jev-test",
        answers={
            "operation": choice(
                "CLICK",
                {
                    "CLICK": probability,
                    **{
                        operation: (1 - probability) / 6
                        for operation in ("SCROLL_DOWN", "SCROLL_UP", "BACK", "WAIT", "DONE", "BLOCKED")
                    },
                },
            ),
            "goal_complete": SimpleNamespace(noul=0.1),
            "click_target": choice("1", {"1": 1.0}),
        },
    )


def test_jev_is_the_only_policy_export() -> None:
    assert "JevPolicy" in jev_android_assistant.__all__
    assert not hasattr(jev_android_assistant, "DualPolicy")
    assert not hasattr(jev_android_assistant, "UltrafastPolicy")


@pytest.mark.parametrize("probability", [0.8, 0.2])
def test_jev_preserves_the_decision_without_failback(probability: float) -> None:
    client = FakeClient(click_response(probability))
    decision = JevPolicy(client=client).decide(snapshot(), "打开市场情绪", [])

    assert decision.provider == "jev"
    assert decision.model == "jev-test"
    assert decision.execution_probability == probability
    assert len(client.calls) == 2


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("ULTRAFAST_PRIMARY_PROVIDER", "laya"),
        ("ULTRAFAST_PRIMARY_PROVIDER", "local"),
        ("ULTRAFAST_SECONDARY_PROVIDER", "laya"),
        ("ULTRAFAST_SECONDARY_PROVIDER", "jev"),
        ("ULTRAFAST_FAILBACK_PROVIDER", "laya"),
        ("LAYA_MLX_PATH", "/preserved/local/checkout"),
        ("LAYA_MLX_MODEL", "aac6fef/laya-multilingual-mlx"),
        ("LAYA_MLX_DTYPE", "float16"),
        ("LAYA_MLX_DEVICE", "gpu"),
    ],
)
def test_retired_config_rejects_remote_policy_before_any_request(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    client = FakeClient(click_response())

    with pytest.raises(ValueError, match=variable):
        JevPolicy(client=client)

    assert client.calls == []


def test_legacy_local_only_environment_cannot_be_masked_by_secondary_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ULTRAFAST_PRIMARY_PROVIDER", "laya")
    monkeypatch.setenv("ULTRAFAST_SECONDARY_PROVIDER", "none")
    with pytest.raises(ValueError, match="ULTRAFAST_PRIMARY_PROVIDER"):
        JevPolicy()


def test_legacy_failback_is_checked_even_when_secondary_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ULTRAFAST_SECONDARY_PROVIDER", "none")
    monkeypatch.setenv("ULTRAFAST_FAILBACK_PROVIDER", "laya")
    with pytest.raises(ValueError, match="ULTRAFAST_FAILBACK_PROVIDER"):
        JevPolicy()


@pytest.mark.parametrize("disabled", ["none", "off", "disabled", ""])
def test_compatible_jev_only_configuration(monkeypatch: pytest.MonkeyPatch, disabled: str) -> None:
    monkeypatch.setenv("ULTRAFAST_PRIMARY_PROVIDER", " JEV ")
    monkeypatch.setenv("ULTRAFAST_SECONDARY_PROVIDER", disabled)
    monkeypatch.setenv("ULTRAFAST_FAILBACK_PROVIDER", disabled)
    policy = JevPolicy(client=FakeClient(click_response()))
    assert policy.decide(snapshot(), "打开市场情绪", []).provider == "jev"


@pytest.mark.parametrize(
    "model",
    ["aac6fef/laya-multilingual-mlx", "/models/checkpoint", "./checkpoint", "../checkpoint", "~/checkpoint"],
)
def test_local_model_cannot_be_sent_to_jev(monkeypatch: pytest.MonkeyPatch, model: str) -> None:
    with pytest.raises(ValueError, match="Local model configuration"):
        JevPolicy(model=model)
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", model)
    with pytest.raises(ValueError, match="Local model configuration"):
        JevPolicy()


def test_jev_transport_rechecks_config_before_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    client = JevClient()
    remote = FakeClient(click_response())
    client._client = remote
    monkeypatch.setenv("ULTRAFAST_PRIMARY_PROVIDER", "laya")

    with pytest.raises(ValueError, match="ULTRAFAST_PRIMARY_PROVIDER"):
        client.system_one(state="private UI", questions={})
    assert remote.calls == []


def test_policy_rechecks_config_even_with_an_injected_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(click_response())
    policy = JevPolicy(client=client)
    monkeypatch.setenv("LAYA_MLX_MODEL", "/preserved/checkpoint")
    with pytest.raises(ValueError, match="LAYA_MLX_MODEL"):
        policy.decide(snapshot(), "打开市场情绪", [])
    assert client.calls == []


def test_jev_without_credentials_stays_unavailable() -> None:
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        JevPolicy().decide(snapshot(), "打开市场情绪", [])


def test_jev_uses_lazy_sdk_and_configured_model_without_local_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    remote = FakeClient(click_response())
    created: list[bool] = []

    def create_client() -> FakeClient:
        created.append(True)
        return remote

    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "jev-test-model")
    monkeypatch.setitem(sys.modules, "typesafe_sdk", SimpleNamespace(TypeSafeClient=create_client))
    policy = JevPolicy()
    assert created == []

    decision = policy.decide(snapshot(), "打开市场情绪", [])

    assert created == [True]
    assert decision.provider == "jev"
    assert all(call["model"] == "jev-test-model" for call in remote.calls)
    policy.close()
    assert policy.client is None
