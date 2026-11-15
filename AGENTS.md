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
- Jev is the only model provider. It is remote and requires `TYPESAFE_API_KEY`; never commit that credential.
  Do not send a sensitive UI tree to remote Jev. Use deterministic local navigation or human review instead.
  Any data authorization must cover the exact tree and recipient and retain all applicable Skill restrictions;
  local-only authorization never permits remote transmission or restores removed integrations.
- Local model adapters and provider switching have been removed. Reject retired provider-routing configuration
  before making a remote request; never silently reinterpret local-only settings as permission to use Jev.
  Preserve separately installed local programs, model files and historical validation records.
- ADB may not be on `PATH`. Use `ANDROID_ADB` or pass `--adb`; on this machine the verified binary is
  `/Users/sj/Library/Android/sdk/platform-tools/adb`. Always pass the intended `--package` and verify the
  foreground package before execution.
- `inspect` is read-only and does not call a model, `suggest` does not execute, and `run` is the bounded execution
  path. Low-confidence or incorrect target selection must remain blocked; do not lower the safety threshold just
  to force a live test through.
- Run Ruff, pytest, and `uv build` before delivery.
