from __future__ import annotations

import pytest

from jev_android_assistant.android import Bounds, Element, ReadOnlySafetyPolicy

PACKAGE = "com.example.reader"


def element(label: str, resource_id: str = "") -> Element:
    return Element(
        index="1",
        role="button",
        label=label,
        resource_id=resource_id,
        class_name="android.widget.Button",
        package=PACKAGE,
        bounds=Bounds(0, 0, 10, 10),
        operations=("CLICK",),
    )


@pytest.mark.parametrize(
    "label",
    [
        "Buy now",
        "Unsubscribe",
        "Sign out",
        "Log out",
        "Enable notifications",
        "Disable notifications",
        "Toggle favorite",
        "Redeem code",
        "Claim reward",
        "Bind account",
        "Change password",
        "Share report",
        "Send message",
        "Publish",
        "Upload",
        "Install",
        "Update",
        "Book now",
        "Reserve",
        "Checkout",
        "Agree",
        "Accept",
        "Allow",
        "Sign in",
    ],
)
def test_blocks_english_write_labels(label: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element(label)) is False


@pytest.mark.parametrize("label", ["分享", "预约", "预订", "绑定", "兑换", "领取"])
def test_blocks_chinese_write_labels(label: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element(label)) is False


@pytest.mark.parametrize(
    "resource_id",
    [
        "com.example.reader:id/share_button",
        "com.example.reader:id/send_message",
        "com.example.reader:id/sign_in",
        "com.example.reader:id/log_out",
        "com.example.reader:id/unsubscribe_action",
    ],
)
def test_blocks_english_write_resource_ids(resource_id: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element("", resource_id)) is False


@pytest.mark.parametrize("label", ["市场情绪", "打开", "Back", "Learn more", "Search"])
def test_keeps_read_only_navigation(label: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element(label)) is True


def test_keeps_read_only_resource_ids() -> None:
    assert (
        ReadOnlySafetyPolicy(PACKAGE).allows(element("", "com.example.reader:id/market_mood"))
        is True
    )


def test_rejects_a_foreign_package() -> None:
    other = Element(
        index="1",
        role="button",
        label="Open",
        resource_id="",
        class_name="android.widget.Button",
        package="com.example.other",
        bounds=Bounds(0, 0, 10, 10),
        operations=("CLICK",),
    )
    assert ReadOnlySafetyPolicy(PACKAGE).allows(other) is False
