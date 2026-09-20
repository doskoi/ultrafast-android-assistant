from __future__ import annotations

from types import SimpleNamespace

from jev_android_assistant.laya import LayaClient


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def predict(self, state: object, questions: object) -> object:
        self.calls.append((state, questions))
        return {
            "model": "laya-test",
            "answers": {
                "operation": {
                    "choice": "DONE",
                    "probabilities": {"DONE": 1.0},
                    "confidence": 1.0,
                },
                "goal_complete": {"noul": 0.9},
            },
        }


def test_laya_client_uses_local_agent_and_preserves_answer_maps() -> None:
    agent = FakeAgent()
    client = LayaClient(agent=agent)
    response = client.system_one({"screen": "home"}, {"operation": {"type": "choice"}})

    assert agent.calls == [({"screen": "home"}, {"operation": {"type": "choice"}})]
    assert isinstance(response, SimpleNamespace)
    assert response.model == "laya-test"
    assert response.answers["operation"].choice == "DONE"
    assert response.answers["operation"].probabilities == {"DONE": 1.0}
