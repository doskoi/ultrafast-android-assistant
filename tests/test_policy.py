from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from jev_android_assistant.agent import AndroidAssistant
from jev_android_assistant.android import Bounds, Element, Snapshot, StaleScreen
from jev_android_assistant.policy import Decision, UltrafastPolicy

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


class FakeClient:
    def __init__(self, response: object):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def system_one(self, state: object, questions: object, *, model: str | None = None) -> object:
        self.calls.append({"state": state, "questions": questions, "model": model})
        return self.response


def choice(selected: str, values: dict[str, float], confidence: float = 0.9) -> object:
    return SimpleNamespace(choice=selected, probabilities=values, confidence=confidence)


def test_selects_operation_first_then_only_validates_its_target() -> None:
    operations = {
        "CLICK": 0.8,
        "SCROLL_DOWN": 0.04,
        "SCROLL_UP": 0.04,
        "BACK": 0.03,
        "WAIT": 0.03,
        "DONE": 0.03,
        "BLOCKED": 0.03,
    }
    client = FakeClient(
        SimpleNamespace(
            answers={
                "operation": choice("CLICK", operations),
                "click_target": choice("1", {"1": 1.0}),
                "scroll_down_target": object(),
                "scroll_up_target": object(),
                "goal_complete": SimpleNamespace(noul=0.1),
            },
            model="ultrafast-test",
        )
    )

    decision = UltrafastPolicy(client=client).decide(snapshot(), "打开市场情绪", [])

    assert len(client.calls) == 2
    assert decision.operation == "CLICK"
    assert decision.target == "1"
    assert decision.execution_probability == 0.8
    assert decision.model == "ultrafast-test"
    assert set(client.calls[0]["questions"]) == {"operation", "goal_complete"}
    assert set(client.calls[1]["questions"]) == {"click_target"}
    operation_question = client.calls[0]["questions"]["operation"]
    assert isinstance(operation_question["instructions"], str)
    assert operation_question["instructions"].startswith("用户目标：打开市场情绪")
    assert all(isinstance(value, str) for value in operation_question["criteria"].values())
    target_question = client.calls[1]["questions"]["click_target"]
    assert isinstance(target_question["instructions"], str)
    assert target_question["instructions"].startswith("用户目标：打开市场情绪\n当前操作：CLICK")
    assert all(isinstance(value, str) for value in target_question["criteria"].values())
    assert "1: 市场情绪" in str(client.calls[1]["state"])
    assert "2: 行情列表" not in str(client.calls[1]["state"])
    assert "页面文字" not in str(client.calls[1]["state"])
    assert "bounds" not in repr(client.calls[0]["state"])


def test_invalid_probability_shape_blocks_decision() -> None:
    client = FakeClient(
        SimpleNamespace(
            answers={
                "operation": choice("CLICK", {"CLICK": 1.0}),
                "goal_complete": SimpleNamespace(noul=0.1),
            }
        )
    )

    with pytest.raises(ValueError, match="Invalid typed-decision choice"):
        UltrafastPolicy(client=client).decide(snapshot(), "打开市场情绪", [])


@dataclass
class FakePolicy:
    decision: Decision

    def decide(self, current: Snapshot, goal: str, history: list[dict[str, object]]) -> Decision:
        return self.decision


class FakeDevice:
    def __init__(self, current: Snapshot, *, stale: bool = False):
        self.current = current
        self.stale = stale
        self.executed: list[tuple[str, str | None]] = []

    def observe(self) -> Snapshot:
        return self.current

    def execute(self, current: Snapshot, *, operation: str, target: str | None = None) -> None:
        if self.stale:
            raise StaleScreen("changed")
        self.executed.append((operation, target))


def decision(
    operation: str = "CLICK",
    *,
    target: str | None = "1",
    operation_probability: float = 0.9,
    target_probability: float | None = 0.8,
    completion_probability: float = 0.1,
) -> Decision:
    return Decision(
        operation=operation,
        target=target,
        operation_probability=operation_probability,
        target_probability=target_probability,
        operation_confidence=0.9,
        target_confidence=0.9 if target is not None else None,
        completion_probability=completion_probability,
        latency_ms=5,
        model="ultrafast-test",
    )


def test_execution_threshold_uses_weaker_of_operation_and_target() -> None:
    device = FakeDevice(snapshot())
    assistant = AndroidAssistant(device, FakePolicy(decision(target_probability=0.4)), min_probability=0.55)

    result = assistant.step("打开市场情绪", execute=True)

    assert result["status"] == "needs_review"
    assert device.executed == []


@pytest.mark.parametrize(
    ("operation_probability", "completion_probability"),
    [(0.9, 0.5), (0.4, 0.9)],
)
def test_done_needs_strong_operation_and_completion_probability(
    operation_probability: float, completion_probability: float
) -> None:
    device = FakeDevice(snapshot())
    assistant = AndroidAssistant(
        device,
        FakePolicy(
            decision(
                "DONE",
                target=None,
                target_probability=None,
                operation_probability=operation_probability,
                completion_probability=completion_probability,
            )
        ),
    )

    result = assistant.step("打开市场情绪", execute=True)

    assert result["status"] == "needs_review"
    assert device.executed == []


def test_stale_screen_is_reported_without_history() -> None:
    device = FakeDevice(snapshot(), stale=True)
    assistant = AndroidAssistant(device, FakePolicy(decision()))

    result = assistant.step("打开市场情绪", execute=True)

    assert result["status"] == "stale"
    assert assistant.history == []
