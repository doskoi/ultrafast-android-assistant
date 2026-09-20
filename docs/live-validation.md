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

The device observation, freshness guard, target mapping, probability gate, ADB click, and post-click navigation
therefore ran against a real emulator. A live Jev request was not run because `TYPESAFE_API_KEY` was unavailable
to the process. Unit tests cover the same one-request Jev composition with a typed fake response; the live Jev
request remains a separate verification item once a key is configured.
