# Live validation

## 2026-09-20 · Android 15 emulator

Environment:

- AVD: `jev_android_api35`
- device: `emulator-5554`
- system image: Android 35 Google APIs ARM64
- assistant package: `jev-android-assistant 0.1.0`

Verified on a real emulator:

1. Installed Kaipl 6.0.10 and launched its resolved activity under package `com.yzj.kaipanh`.
2. `inspect` read the real UIAutomator tree and identified the first-run agreement screen.
3. Both agreement choices, `同意` and `暂不使用`, were excluded from the action space after the live test exposed
   that declining consent is also a persisted choice.
4. Opened Android Settings and observed its indexed action space.
5. A deterministic test policy selected the observed `Battery` element. The normal assistant execution path
   re-observed the full page, matched the fingerprint, mapped the selected index to its local bounds, tapped it,
   and reached `com.android.settings/.SubSettings` with visible `Battery` content.
6. The historical validation below predates local Laya and is not the current runtime path.
7. A current local Laya validation must load a local checkpoint, record the selected operation/target and
   probabilities, then verify the same bounded run on the emulator.
8. On Kaipl's first-run agreement screen, the code exposed no consent action and the historical model selected
   `BLOCKED` with probability `0.87`; no input was sent.

The device observation, freshness guard, target mapping, probability gate, ADB click, and post-click navigation
therefore ran against a real emulator with the historical model decisions. The first click decision in the
bounded run took about 3.5 seconds; the completion request took about 29.5 seconds. Those figures do not prove
the latency of local Laya and should not be reused for the new runtime.
