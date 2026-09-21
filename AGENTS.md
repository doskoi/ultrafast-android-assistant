# Agent guide

This repository owns a reusable Android UI navigation assistant. App-specific code belongs in examples or
configuration, not in the core package.

- Keep UI observation, semantic judgment, and input execution as separate boundaries.
- Prefer deterministic UIAutomator/ADB matching for known screens; invoke Ultrafast only when the page or target is
  ambiguous or changed, and do not make a separate `suggest` request before a `run` step that will decide again.
- The model must never generate coordinates, selectors, shell commands, or arbitrary text input.
- Re-observe the full UI before every input and reject stale decisions.
- Default to read-only navigation. New write capabilities require an explicit design and dedicated tests.
- Do not commit model credentials, device credentials, login data, raw private UI dumps, screenshots, or app artifacts.
- Local Laya is loaded in the Android repo's Python process. Run `uv sync` and preferably install the local checkout
  with `uv pip install --python .venv/bin/python -e /Users/sj/projects/laya-mlx`; `LAYA_MLX_PATH` can locate the
  source as an import fallback, but it does not install laya-mlx's dependencies. `LAYA_MLX_MODEL` accepts a local
  checkpoint directory or a model ID; an unset model may download `aac6fef/laya-multilingual-mlx`, so strict
  offline checks use a local path.
- ADB may not be on `PATH`. Use `ANDROID_ADB` or pass `--adb`; on this machine the verified binary is
  `/Users/sj/Library/Android/sdk/platform-tools/adb`. Always pass the intended `--package` and verify the
  foreground package before execution.
- `inspect` is read-only and does not call Laya, `suggest` does not execute, and `run` is the bounded execution
  path. Low-confidence or incorrect target selection must remain blocked; do not lower the safety threshold just
  to force a live test through.
- Run Ruff, pytest, and `uv build` before delivery.
