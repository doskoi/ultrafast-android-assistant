"""Bounded observe-decide-act loop for an Android device or emulator."""

from __future__ import annotations

from dataclasses import asdict

from .android import AdbDevice, Snapshot, StaleScreen
from .policy import Decision, JevPolicy


class AndroidAssistant:
    def __init__(
        self,
        device: AdbDevice,
        policy: JevPolicy,
        *,
        min_probability: float = 0.55,
        completion_threshold: float = 0.85,
    ):
        if not 0 <= min_probability <= 1 or not 0 <= completion_threshold <= 1:
            raise ValueError("Probability thresholds must be between 0 and 1")
        self.device = device
        self.policy = policy
        self.min_probability = min_probability
        self.completion_threshold = completion_threshold
        self.history: list[dict[str, object]] = []

    def inspect(self) -> Snapshot:
        return self.device.observe()

    def suggest(self, goal: str, snapshot: Snapshot | None = None) -> tuple[Snapshot, Decision]:
        snapshot = snapshot or self.inspect()
        return snapshot, self.policy.decide(snapshot, goal, self.history)

    def step(self, goal: str, *, execute: bool) -> dict[str, object]:
        snapshot, decision = self.suggest(goal)
        result: dict[str, object] = {
            "status": "suggested",
            "screen": {"activity": snapshot.activity, "fingerprint": snapshot.fingerprint},
            "decision": asdict(decision),
        }
        if decision.operation == "DONE":
            completion_is_strong = decision.completion_probability >= self.completion_threshold
            operation_is_strong = decision.operation_probability >= self.min_probability
            result["status"] = (
                "done" if completion_is_strong and operation_is_strong else "needs_review"
            )
            result["reason"] = (
                "goal visibly complete"
                if result["status"] == "done"
                else "Jev chose DONE without enough operation and completion probability"
            )
            return result
        if decision.operation == "BLOCKED":
            result.update(status="blocked", reason="Jev found no supported read-only action")
            return result
        if not execute:
            return result
        if decision.execution_probability < self.min_probability:
            result.update(status="needs_review", reason="decision probability below the execution threshold")
            return result
        try:
            self.device.execute(snapshot, operation=decision.operation, target=decision.target)
        except StaleScreen as exc:
            result.update(status="stale", reason=str(exc))
            return result
        action = {
            "operation": decision.operation,
            "target": decision.target,
            "label": snapshot.element(decision.target).label if decision.target else decision.operation,
            "probability": decision.execution_probability,
        }
        self.history.append(action)
        result.update(status="executed", action=action)
        return result

    def run(self, goal: str, *, max_steps: int = 30):
        for _ in range(max_steps):
            result = self.step(goal, execute=True)
            yield result
            if result["status"] != "executed":
                return
        yield {"status": "blocked", "reason": f"Reached the {max_steps}-step action budget"}
