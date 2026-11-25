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
        "Redeem code",
        "Claim reward",
        "Bind account",
        "Change password",
        "Send message",
        "Publish",
        "Upload",
        "Install",
        "Place order",
        "Book now",
        "Toggle favorite",
        "Checkout",
        "Agree",
        "Accept",
        "Allow",
        "Sign in",
    ],
)
def test_blocks_english_write_labels(label: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element(label)) is False


@pytest.mark.parametrize("label", ["Share", "Update", "Book", "Reserve", "Post", "Toggle", "Order"])
def test_blocks_english_write_labels_that_are_also_nouns(label: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element(label)) is False


@pytest.mark.parametrize(
    "label",
    [
        "分享",
        "预约",
        "预订",
        "绑定",
        "兑换",
        "领取",
        "开启通知",
        "关闭账户",
    ],
)
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
        "com.example.reader:id/sign_out_button",
        "com.example.reader:id/btn_signout",
        "com.example.reader:id/log_in_button",
        "com.example.reader:id/disable_sync",
    ],
)
def test_blocks_english_write_resource_ids(resource_id: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element("", resource_id)) is False


@pytest.mark.parametrize(
    "label",
    [
        "市场情绪",
        "打开",
        "Back",
        "Learn more",
        "Search",
        "Share price",
        "Market update",
        "Order book",
        "Toggle navigation",
        "已预约",
        "已分享",
        "已绑定",
        "已关闭",
    ],
)
def test_keeps_read_only_navigation(label: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element(label)) is True


@pytest.mark.parametrize(
    "resource_id",
    [
        "com.example.reader:id/market_mood",
        "com.example.reader:id/tv_market_share",
        "com.example.reader:id/price_chart",
    ],
)
def test_keeps_read_only_resource_ids(resource_id: str) -> None:
    assert ReadOnlySafetyPolicy(PACKAGE).allows(element("", resource_id)) is True


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
