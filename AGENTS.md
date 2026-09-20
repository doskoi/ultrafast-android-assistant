# Agent guide

This repository owns a reusable Android UI navigation assistant. App-specific code belongs in examples or
configuration, not in the core package.

- Keep UI observation, semantic judgment, and input execution as separate boundaries.
- The model must never generate coordinates, selectors, shell commands, or arbitrary text input.
- Re-observe the full UI before every input and reject stale decisions.
- Default to read-only navigation. New write capabilities require an explicit design and dedicated tests.
- Do not commit model credentials, device credentials, login data, raw private UI dumps, screenshots, or app artifacts.
- Run Ruff, pytest, and `uv build` before delivery.
