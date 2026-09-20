from __future__ import annotations

from dataclasses import replace

import pytest

from jev_android_assistant.android import (
    AdbDevice,
    Bounds,
    Element,
    Snapshot,
    StaleScreen,
    UnsafeTarget,
    parse_snapshot,
)

APP_PACKAGE = "com.example.reader"

XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.example.reader" enabled="true" clickable="false" scrollable="false"
        password="false" bounds="[0,0][1080,2400]">
    <node index="0" text="市场情绪" resource-id="com.example.reader:id/market_mood"
          class="android.widget.Button" package="com.example.reader" enabled="true"
          clickable="true" scrollable="false" password="false" bounds="[100,200][400,320]" />
    <node index="1" text="立即开通" resource-id="com.example.reader:id/subscribe"
          class="android.widget.Button" package="com.example.reader" enabled="true"
          clickable="true" scrollable="false" password="false" bounds="[500,200][800,320]" />
    <node index="2" text="" resource-id="com.example.reader:id/list"
          class="androidx.recyclerview.widget.RecyclerView" package="com.example.reader" enabled="true"
          clickable="false" scrollable="true" password="false" bounds="[0,400][1080,2100]">
      <node index="0" text="涨停复盘" content-desc="只读列表" resource-id=""
            class="android.widget.TextView" package="com.example.reader" enabled="true"
            clickable="false" scrollable="false" password="false" bounds="[30,430][500,500]" />
    </node>
    <node index="3" text="13812345678" resource-id="com.example.reader:id/phone"
          class="android.widget.TextView" package="com.example.reader" enabled="true"
          clickable="false" scrollable="false" password="false" bounds="[0,2200][400,2300]" />
    <node index="4" text="secret-value" resource-id="com.example.reader:id/password"
          class="android.widget.EditText" package="com.example.reader" enabled="true"
          clickable="true" scrollable="false" password="true" bounds="[500,2200][900,2300]" />
    <node index="5" text="后台按钮" resource-id="com.example.reader:id/hidden"
          class="android.widget.Button" package="com.example.reader" enabled="true"
          visible-to-user="false" clickable="true" scrollable="false" password="false"
          bounds="[500,2100][900,2200]" />
    <node index="6" text="接收提醒" resource-id="com.example.reader:id/notification_switch"
          class="android.widget.Switch" package="com.example.reader" enabled="true"
          checkable="true" checked="false" clickable="true" scrollable="false" password="false"
          bounds="[500,2000][900,2100]" />
  </node>
</hierarchy>"""

FOCUS = "mCurrentFocus=Window{abcd u0 com.example.reader/.MainActivity}"


def test_snapshot_builds_redacted_read_only_action_space() -> None:
    snapshot = parse_snapshot(XML, FOCUS, package=APP_PACKAGE)

    assert snapshot.package == APP_PACKAGE
    assert snapshot.activity == "com.example.reader/.MainActivity"
    assert [(element.index, element.label, element.operations) for element in snapshot.elements] == [
        ("1", "市场情绪", ("CLICK",)),
        ("2", "涨停复盘 · 只读列表", ("SCROLL_DOWN", "SCROLL_UP")),
    ]
    assert "138****5678" in snapshot.text
    assert "secret-value" not in snapshot.text
    assert "立即开通" in snapshot.text


def test_model_state_has_semantics_but_no_coordinates() -> None:
    state = parse_snapshot(XML, FOCUS, package=APP_PACKAGE).model_state([])
    serialized = repr(state)

    assert "市场情绪" in serialized
    assert "bounds" not in serialized
    assert "left" not in serialized
    assert "1080" not in serialized


def test_snapshot_uses_single_xml_package_when_focus_is_unavailable() -> None:
    snapshot = parse_snapshot(XML, "", package=APP_PACKAGE)

    assert snapshot.package == APP_PACKAGE
    assert snapshot.activity == ""


class RecordingDevice(AdbDevice):
    def __init__(self, snapshots: list[Snapshot]):
        super().__init__(adb="adb", package=APP_PACKAGE)
        self.snapshots = snapshots
        self.commands: list[tuple[str, ...]] = []

    def observe(self) -> Snapshot:
        return self.snapshots.pop(0)

    def _command(self, *args: str, timeout: float | None = None):  # type: ignore[no-untyped-def]
        self.commands.append(args)
        return None


def test_execute_revalidates_snapshot_then_uses_observed_center(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = parse_snapshot(XML, FOCUS, package=APP_PACKAGE)
    device = RecordingDevice([snapshot])
    monkeypatch.setattr("jev_android_assistant.android.time.sleep", lambda _: None)

    device.execute(snapshot, operation="CLICK", target="1")

    assert device.commands == [("shell", "input", "tap", "250", "260")]


def test_execute_rejects_changed_screen_before_input() -> None:
    snapshot = parse_snapshot(XML, FOCUS, package=APP_PACKAGE)
    changed = replace(snapshot, fingerprint="changed")
    device = RecordingDevice([changed])

    with pytest.raises(StaleScreen):
        device.execute(snapshot, operation="CLICK", target="1")

    assert device.commands == []


def test_execute_rejects_target_outside_read_only_policy() -> None:
    unsafe = Element(
        index="1",
        role="button",
        label="立即开通",
        resource_id="subscribe",
        class_name="android.widget.Button",
        package=APP_PACKAGE,
        bounds=Bounds(0, 0, 100, 100),
        operations=("CLICK",),
    )
    snapshot = Snapshot("activity", APP_PACKAGE, "", (unsafe,), "same")
    device = RecordingDevice([snapshot])

    with pytest.raises(UnsafeTarget):
        device.execute(snapshot, operation="CLICK", target="1")

    assert device.commands == []


def test_resource_id_can_block_unlabelled_write_action() -> None:
    unsafe = Element(
        index="1",
        role="button",
        label="unnamed",
        resource_id="com.example.reader:id/add_watchlist_button",
        class_name="android.widget.Button",
        package=APP_PACKAGE,
        bounds=Bounds(0, 0, 100, 100),
        operations=("CLICK",),
    )
    snapshot = Snapshot("activity", APP_PACKAGE, "", (unsafe,), "same")
    device = RecordingDevice([snapshot])

    with pytest.raises(UnsafeTarget):
        device.execute(snapshot, operation="CLICK", target="1")

    assert device.commands == []


def test_english_write_label_is_not_exposed() -> None:
    xml = XML.replace("市场情绪", "Subscribe now")

    snapshot = parse_snapshot(xml, FOCUS, package=APP_PACKAGE)

    assert all(element.label != "Subscribe now" for element in snapshot.elements)


@pytest.mark.parametrize("label", ["同意", "暂不使用", "不同意", "Not now", "Decline"])
def test_consent_choices_are_not_exposed(label: str) -> None:
    xml = XML.replace("市场情绪", label)

    snapshot = parse_snapshot(xml, FOCUS, package=APP_PACKAGE)

    assert all(element.label != label for element in snapshot.elements)


def test_device_requires_specific_android_package() -> None:
    with pytest.raises(ValueError, match="Invalid Android package"):
        AdbDevice(adb="adb", package="")
