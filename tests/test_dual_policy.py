from __future__ import annotations

from types import SimpleNamespace

import pytest

from jev_android_assistant.android import Bounds, Element, Snapshot
from jev_android_assistant.policy import DecisionProvidersUnavailableError, DualPolicy

APP_PACKAGE = "com.example.reader"


def snapshot() -> Snapshot:
    elements = (
        Element(
            index="1",
            role="button",
            label="市场情绪",
            resource_id="market_mood",
            class_name="android.widget.Button",
            package=APP_PACKAGE,
            bounds=Bounds(10, 20, 110, 80),
            operations=("CLICK",),
        ),
        Element(
            index="2",
            role="scrollable",
            label="行情列表",
            resource_id="list",
            class_name="androidx.recyclerview.widget.RecyclerView",
            package=APP_PACKAGE,
            bounds=Bounds(0, 100, 1080, 2100),
            operations=("SCROLL_DOWN", "SCROLL_UP"),
        ),
    )
    return Snapshot("com.example.reader/.MainActivity", APP_PACKAGE, "首页", elements, "snapshot")


def response(operation_probability: float, model: str) -> object:
    other_probability = (1 - operation_probability) / 6
    return SimpleNamespace(
        model=model,
        answers={
            "operation": SimpleNamespace(
                choice="CLICK",
                confidence=operation_probability,
                probabilities={
                    "CLICK": operation_probability,
                    "SCROLL_DOWN": other_probability,
                    "SCROLL_UP": other_probability,
                    "BACK": other_probability,
                    "WAIT": other_probability,
                    "DONE": other_probability,
                    "BLOCKED": other_probability,
                },
            ),
            "click_target": SimpleNamespace(choice="1", confidence=1, probabilities={"1": 1}),
            "scroll_down_target": SimpleNamespace(choice="2", confidence=1, probabilities={"2": 1}),
            "scroll_up_target": SimpleNamespace(choice="2", confidence=1, probabilities={"2": 1}),
            "goal_complete": SimpleNamespace(noul=0.05),
        },
    )


class FakeClient:
    def __init__(self, result: object | None = None, failure: Exception | None = None):
        self.result = result
        self.failure = failure
        self.calls = 0

    def system_one(self, state: object, questions: object, *, model: str | None = None) -> object:
        del state, questions, model
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.result


def test_primary_is_kept_without_calling_secondary() -> None:
    primary = FakeClient(response(0.8, "laya-test"))
    secondary = FakeClient(response(0.9, "jev-test"))
    policy = DualPolicy(primary="laya", secondary="jev", laya_client=primary, jev_client=secondary)

    decision = policy.decide(snapshot(), "打开市场情绪", [])

    assert decision.provider == "laya"
    assert decision.model == "laya-test"
    assert primary.calls == 1
    assert secondary.calls == 0


def test_defaults_to_jev_primary_and_laya_failback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ULTRAFAST_PRIMARY_PROVIDER", raising=False)
    monkeypatch.delenv("ULTRAFAST_SECONDARY_PROVIDER", raising=False)
    monkeypatch.delenv("ULTRAFAST_FAILBACK_PROVIDER", raising=False)
    jev = FakeClient(response(0.8, "jev-test"))
    laya = FakeClient(response(0.9, "laya-test"))
    policy = DualPolicy(jev_client=jev, laya_client=laya)

    decision = policy.decide(snapshot(), "打开市场情绪", [])

    assert decision.provider == "jev"
    assert jev.calls == 1
    assert laya.calls == 0


def test_weak_primary_fails_back_to_secondary() -> None:
    primary = FakeClient(response(0.2, "laya-test"))
    secondary = FakeClient(response(0.8, "jev-test"))
    policy = DualPolicy(primary="laya", secondary="jev", laya_client=primary, jev_client=secondary)

    decision = policy.decide(snapshot(), "打开市场情绪", [])

    assert decision.provider == "jev"
    assert decision.model == "jev-test"
    assert primary.calls == 1
    assert secondary.calls == 1


def test_primary_runtime_failure_fails_back() -> None:
    primary = FakeClient(failure=RuntimeError("Local Laya runtime unavailable"))
    secondary = FakeClient(response(0.8, "jev-test"))
    policy = DualPolicy(primary="laya", secondary="jev", laya_client=primary, jev_client=secondary)

    decision = policy.decide(snapshot(), "打开市场情绪", [])

    assert decision.provider == "jev"
    assert primary.calls == 1
    assert secondary.calls == 1


def test_both_provider_failures_are_reported() -> None:
    policy = DualPolicy(
        primary="laya",
        secondary="jev",
        laya_client=FakeClient(failure=RuntimeError("Local Laya runtime unavailable")),
        jev_client=FakeClient(failure=RuntimeError("TypeSafe Jev unavailable")),
    )

    with pytest.raises(DecisionProvidersUnavailableError):
        policy.decide(snapshot(), "打开市场情绪", [])


def test_jev_can_be_primary_with_laya_failback() -> None:
    jev = FakeClient(response(0.8, "jev-test"))
    laya = FakeClient(response(0.9, "laya-test"))
    policy = DualPolicy(primary="jev", secondary="laya", jev_client=jev, laya_client=laya)

    decision = policy.decide(snapshot(), "打开市场情绪", [])

    assert decision.provider == "jev"
    assert jev.calls == 1
    assert laya.calls == 0
