# Ultrafast Android Assistant

A reusable Android UI navigation assistant. It reads the current screen through UIAutomator, turns the
visible, actionable controls into a numbered bounded action space, and asks the remote Jev provider to
choose the next operation and its target. Jev is the only model provider; local model wiring and fallback
have been removed.

The design is "current-screen action space + two-stage typed decision + pre-execution freshness check":

- every step rebuilds the action space from the current screen;
- the first System One request uses `Choice` for the operation and `Noul` for completion;
- when the operation needs a target, the second request generates only that operation's candidates, so
  unrelated target branches do not inflate the token count;
- the screen is observed again before execution, and a changed screen rejects the input.

It does not port a browser DOM, selectors, or a browser harness. On Android, UIAutomator supplies the
accessibility tree and ADB executes code-validated clicks, scrolls, back actions, and waits.

## Installation

Requires Python 3.12, `uv`, and ADB:

```bash
uv sync
```

If an existing environment still has a separately installed local model program, update this project with
`uv pip install --no-deps -e .` so that a command which synchronizes dependencies exactly does not remove
those separate installations. There is no need to uninstall local programs, delete models, or change
machine configuration.

Jev calls the remote service through `typesafe-sdk` and needs `TYPESAFE_API_KEY`. Running `suggest` or
`run` sends the semantic content of the current UI to that service. Do not commit the key to the
repository; before running Android commands, load it from a machine-local file with mode `0600`:

```bash
source ~/.config/ultrafast/jev.env
```

UI trees containing sensitive content must not be sent to remote Jev; use local deterministic
UIAutomator/ADB navigation or human confirmation instead. Any data authorization must be limited to the
exact UI tree and recipient and must retain all applicable Skill data restrictions; a local-only
authorization does not permit remote transmission and does not restore removed wiring. `inspect` does not
call the model.

The old local-model adapter, `UltrafastPolicy`, `DualPolicy`, `--primary-provider`, and
`--secondary-provider` have been removed. Code should use `JevPolicy` explicitly. `--model` and
`TYPESAFE_DEFAULT_MODEL` still select the remote Jev model.

To avoid silently turning an old local configuration into a remote request, these settings fail before the
request:

- `ULTRAFAST_PRIMARY_PROVIDER` selects a provider other than `jev`;
- `ULTRAFAST_SECONDARY_PROVIDER` or `ULTRAFAST_FALLBACK_PROVIDER` selects any provider.

A shared environment may keep `ULTRAFAST_PRIMARY_PROVIDER=jev` and a secondary/fallback value of `none`,
`off`, or `disabled`; those values only satisfy the compatibility check and no longer provide routing. Clear
the old settings from the current process only after confirming that remote handling is allowed. A
separately installed Laya program and model may stay; this project does not import, load, or uninstall
them. `ULTRAFAST_FALLBACK_THRESHOLD` and `ULTRAFAST_COMPLETION_THRESHOLD` no longer control provider
switching; execution and completion probability remain controlled by `--min-probability` and
`--completion-threshold`.

ADB is looked up on `PATH` by default. On this machine the SDK ADB is at
`/Users/sj/Library/Android/sdk/platform-tools/adb`; if `adb` is not on `PATH`, set `ANDROID_ADB` or pass
`--adb /Users/sj/Library/Android/sdk/platform-tools/adb` on each command.

Run it in the same environment:

```bash
uv run --no-sync ultrafast-android-assistant --serial emulator-5554 --package com.example.reader \
  suggest "Open today's ranking and stop when the ranking title is visible"
```

Every run must name the Android package it is allowed to operate; the assistant stops immediately when the
foreground app is not that package.

## Usage

Read the current action space without calling the model:

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  inspect
```

Ask remote Jev for one suggested step without executing it:

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  suggest "From the current page, open today's ranking and stop when the ranking title is visible"
```

Run navigation with a step limit:

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  run "From the current page, open today's ranking and stop when the ranking title is visible" \
  --max-steps 12
```

Kaipl can call the assistant directly; the assistant code does not need to live in the Kaipl repository.
The package below was measured on 6.0.10; confirm the package with ADB for other versions:

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.yzj.kaipanh \
  suggest "From the current home page, open the market-mood page and stop when its title is visible"
```

## Recommended operating strategy: deterministic first, Ultrafast as the fallback

Ultrafast is a navigation judge, not a mandatory step for every Android action. To make batch
investigations and version comparisons efficient, choose the path in this order:

1. **Static APK comparison does not start an emulator and does not call Ultrafast.** Compare JADX/DEX,
   resources, the manifest, strings, network entry points, and already recorded API evidence directly.
2. **Known screens and stable controls do not call Ultrafast.** Local code reads the UIAutomator tree,
   matches the target by stable `resource-id`, text, content description, or control role, and then
   performs validated ADB clicks, scrolls, back actions, and waits. Every input must still re-observe the
   screen and check the fingerprint; never reuse stale coordinates or old nodes.
3. **Call Ultrafast only when the screen structure changed, the entry point is uncertain, or several
   controls are semantically similar.** Ultrafast returns only the operation and target index from the
   current observation; local code takes the bounds from the same freshly observed UI tree and hands the
   action to ADB. The model must not generate coordinates, selectors, shell commands, or input text.
4. **Verify locally after each action.** Confirm the state change first with UIAutomator, the screen
   fingerprint, the foreground activity, logs, or network observation; do not call the model again just to
   verify each step.

The typical efficient chain is:

```text
static APK scan
  -> local rules match a known control
  -> ADB executes and waits for the screen to change
  -> local verification
  -> call Ultrafast once only when matching fails or semantics are uncertain
```

For a new screen, `inspect` reads the action space; `suggest` is useful for a single step while confirming
the path. Once the trace is confirmed to be read-only navigation, use `run` with a step limit directly;
do not call `suggest` for a step and then let `run` judge it again, because that duplicates model requests.
Code callers may also use `AndroidAssistant.step(..., execute=True)` so that one Ultrafast judgement is
followed by one local ADB execution.

A functional gap scan should therefore follow "static evidence -> deterministic regression of known flows
-> Ultrafast only for unknown branches". Ultrafast's click log only proves that navigation reached some
screen; it cannot by itself prove API requests, field semantics, pagination, or Gateway contracts.

## Execution boundaries

The model receives only page semantics, indices, roles, and supported operations; it never receives
coordinates, screenshots, raw XML, or ADB commands. Coordinates are computed only in the local executor
from the node observed immediately before the action.

The first version supports only `CLICK`, `SCROLL_UP`, `SCROLL_DOWN`, `BACK`, `WAIT`, `DONE`, and `BLOCKED`.
It does not type text; password nodes, hidden nodes, all switches and checkboxes, and obvious write
operations such as purchase, payment, subscribe, follow, delete, sign-in, save, and edit never enter the
action space.

Automatic execution requires both the operation and the target to reach a minimum probability of `0.55` by
default. `DONE` additionally requires the operation probability to reach that threshold and the completion
judgement to reach `0.85`. These are conservative initial values and should be tuned against real
navigation traces of the target app.

In real use, do not lower the thresholds or force a low-confidence action just to make a goal "succeed".
When the model picks the wrong target or the probability is too low, the expected result is `needs_review`
with no input sent; improve the goal text, use deterministic UIAutomator matching, or fall back to human
confirmation. `inspect` does not call the model, `suggest` only suggests, and only `run` with a step limit
executes actions.

## Verification

```bash
uv run --no-sync ruff check .
uv run --no-sync pytest -q
uv build
```

Unit tests cover action-space filtering, sensitive-data redaction, model-invisible coordinates, two-stage
target selection, probability gates, completion judgement, and screen freshness. Current device validation
results and unverified boundaries are in [docs/live-validation.md](docs/live-validation.md).
