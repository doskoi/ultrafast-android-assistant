"""Local laya-mlx adapter for typed decisions."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol


class LayaAgent(Protocol):
    def predict(self, state: object, questions: object) -> object: ...


def _response_namespace(value: dict[str, object]) -> object:
    answers = value.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("Local Laya returned an invalid answers object")
    usage = value.get("usage")
    return SimpleNamespace(
        model=value.get("model"),
        answers={
            key: SimpleNamespace(**answer) if isinstance(answer, dict) else answer
            for key, answer in answers.items()
        },
        usage=usage if isinstance(usage, dict) else None,
    )


class LayaClient:
    """Lazily load one local Laya agent and expose the old System One call shape."""

    def __init__(
        self,
        *,
        agent: LayaAgent | None = None,
        model: str | None = None,
        dtype: str | None = None,
        device: str | None = None,
    ):
        self.model = model or os.environ.get("LAYA_MLX_MODEL", "aac6fef/laya-multilingual-mlx")
        self.dtype = dtype or os.environ.get("LAYA_MLX_DTYPE", "float16")
        self.device = device or os.environ.get("LAYA_MLX_DEVICE", "gpu")
        self._agent = agent

    def _load(self) -> LayaAgent:
        if self._agent is not None:
            return self._agent
        source_path = os.environ.get("LAYA_MLX_PATH")
        if source_path:
            sys.path.insert(0, str(Path(source_path).expanduser()))
        try:
            import laya_mlx
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Local Laya runtime unavailable; install the local laya-mlx checkout "
                "or set LAYA_MLX_PATH to it"
            ) from exc
        self._agent = laya_mlx.load(self.model, dtype=self.dtype, device=self.device)
        return self._agent

    def system_one(self, state: object, questions: object, *, model: str | None = None) -> object:
        del model
        result = self._load().predict(state, questions)
        if not isinstance(result, dict):
            raise ValueError("Local Laya returned an invalid decision")
        return _response_namespace(result)
