"""One-call Android observations and guarded execution through ADB."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

DEFAULT_ADB = os.environ.get("ANDROID_ADB", "adb")
SNAPSHOT_MARKER = "__ULTRAFAST_ANDROID_FOCUS__"
BOUNDS_RE = re.compile(r"\[(\d+),(\d+)]\[(\d+),(\d+)]")
FOCUS_RE = re.compile(r"(?:mCurrentFocus|mFocusedApp).*?\s([\w.]+/[\w.$]+)")
PACKAGE_RE = re.compile(r"(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*")
PHONE_RE = re.compile(r"(?<!\d)1\d{10}(?!\d)")
EMAIL_RE = re.compile(r"\b([\w.+-])[^@\s]*@([^\s.]+\.[^\s]+)\b")
TOKEN_RE = re.compile(r"\b(?=[A-Za-z0-9_-]{24,}\b)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_-]+\b")


def redact(value: str) -> str:
    value = PHONE_RE.sub(lambda match: f"{match.group(0)[:3]}****{match.group(0)[-4:]}", value)
    value = EMAIL_RE.sub(r"\1***@\2", value)
    return TOKEN_RE.sub("<redacted>", value)


def _truth(value: str | None) -> bool:
    return value == "true"


@dataclass(frozen=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


@dataclass(frozen=True)
class Element:
    index: str
    role: str
    label: str
    resource_id: str
    class_name: str
    package: str
    bounds: Bounds
    operations: tuple[str, ...]
    selected: bool | None = None

    def model_view(self) -> dict[str, object]:
        result: dict[str, object] = {
            "index": self.index,
            "role": self.role,
            "label": self.label,
            "operations": list(self.operations),
        }
        if self.resource_id:
            result["resource_id"] = self.resource_id.rsplit("/", 1)[-1]
        if self.selected is not None:
            result["selected"] = self.selected
        return result

    def guard(self) -> dict[str, object]:
        return {
            **self.model_view(),
            "class_name": self.class_name,
            "package": self.package,
            "bounds": asdict(self.bounds),
        }


@dataclass(frozen=True)
class Snapshot:
    activity: str
    package: str
    text: str
    elements: tuple[Element, ...]
    fingerprint: str

    def element(self, index: str) -> Element:
        return next(element for element in self.elements if element.index == index)

    def model_state(
        self,
        history: list[dict[str, object]],
        *,
        elements: tuple[Element, ...] | None = None,
    ) -> dict[str, object]:
        visible_elements = self.elements if elements is None else elements
        return {
            "screen": {"package": self.package, "activity": self.activity, "text": self.text},
            "elements": [element.model_view() for element in visible_elements],
            "recent_actions": history[-10:],
        }


class UnsafeTarget(ValueError):
    """The current screen or chosen target is outside the read-only policy."""


class StaleScreen(ValueError):
    """The UI changed after Ultrafast made its decision."""


class ReadOnlySafetyPolicy:
    """Keep the assistant away from clearly state-changing UI."""

    BLOCKED_TEXT = re.compile(
        r"购买|支付|开通|订阅|立即解锁|关注|取消关注|删除|注销|退出登录|"
        r"保存|添加|移除|设自选|兑换|领取|下单|交易|修改密码|绑定|"
        r"确定|确认|提交|登录|注册|发送验证码|授权|同意|不同意|暂不使用|拒绝|"
        r"稍后再说|编辑|立即体验|"
        r"\b(?:buy|pay|purchase|subscribe|follow|unfollow|delete|logout|save|favorite|"
        r"trade|order|redeem|claim|confirm|submit|login|register|authorize|decline|deny|"
        r"not now|edit)\b",
        re.IGNORECASE,
    )
    BLOCKED_RESOURCE_ID = re.compile(
        r"(?:^|[_/])(?:buy|pay|purchase|subscribe|follow|unfollow|delete|logout|save|"
        r"add[_-]?watchlist|remove[_-]?watchlist|add[_-]?favorite|remove[_-]?favorite|"
        r"trade|place[_-]?order|redeem|claim|change[_-]?password|confirm|submit|login|"
        r"register|authorize|enable|toggle|switch|edit)(?:$|[_-])",
        re.IGNORECASE,
    )

    def __init__(self, package: str):
        if not PACKAGE_RE.fullmatch(package):
            raise ValueError(f"Invalid Android package: {package!r}")
        self.package = package

    def allows(self, element: Element) -> bool:
        return (
            element.package == self.package
            and not self.BLOCKED_TEXT.search(element.label)
            and not self.BLOCKED_RESOURCE_ID.search(element.resource_id)
        )


def _bounds(value: str) -> Bounds | None:
    match = BOUNDS_RE.fullmatch(value)
    if not match:
        return None
    bounds = Bounds(*(int(part) for part in match.groups()))
    return bounds if bounds.width > 0 and bounds.height > 0 else None


def _role(class_name: str, scrollable: bool) -> str:
    short = class_name.rsplit(".", 1)[-1].lower()
    if scrollable:
        return "scrollable"
    if "button" in short:
        return "button"
    if "edittext" in short:
        return "textbox"
    if "tab" in short:
        return "tab"
    return "item"


def _descendant_label(node: ET.Element) -> str:
    values: list[str] = []
    for child in node.iter():
        for key in ("text", "content-desc"):
            value = redact(child.attrib.get(key, "").strip())
            if value and value not in values:
                values.append(value)
        if len(values) >= 4:
            break
    return " · ".join(values)


def parse_snapshot(xml: str, focus: str, *, package: str) -> Snapshot:
    root = ET.fromstring(xml)
    focus_match = FOCUS_RE.search(focus)
    activity = focus_match.group(1) if focus_match else ""
    focused_package = activity.split("/", 1)[0] if activity else ""
    page_values: list[str] = []
    candidates: list[Element] = []
    safety = ReadOnlySafetyPolicy(package)

    if not focused_package:
        packages = [
            node.attrib.get("package", "")
            for node in root.iter("node")
            if node.attrib.get("package", "")
        ]
        if packages and len(set(packages)) == 1:
            focused_package = packages[0]

    for node in root.iter("node"):
        attrs = node.attrib
        if (
            _truth(attrs.get("password"))
            or _truth(attrs.get("checkable"))
            or not _truth(attrs.get("enabled", "true"))
            or attrs.get("visible-to-user") == "false"
        ):
            continue
        node_package = attrs.get("package", "")
        text = redact(attrs.get("text", "").strip())
        description = redact(attrs.get("content-desc", "").strip())
        for value in (text, description):
            if value and value not in page_values:
                page_values.append(value)
        clickable = _truth(attrs.get("clickable"))
        scrollable = _truth(attrs.get("scrollable"))
        if not (clickable or scrollable):
            continue
        bounds = _bounds(attrs.get("bounds", ""))
        if not bounds:
            continue
        label = text or description or _descendant_label(node)
        resource_id = attrs.get("resource-id", "")
        if clickable and not label and not resource_id:
            continue
        if not label:
            label = resource_id.rsplit("/", 1)[-1] or attrs.get("class", "").rsplit(".", 1)[-1] or "unnamed"
        operations: list[str] = []
        if clickable:
            operations.append("CLICK")
        if scrollable:
            operations.extend(("SCROLL_DOWN", "SCROLL_UP"))
        selected = _truth(attrs.get("selected")) if "selected" in attrs else None
        element = Element(
            index=str(len(candidates) + 1),
            role=_role(attrs.get("class", ""), scrollable),
            label=label[:240],
            resource_id=resource_id,
            class_name=attrs.get("class", ""),
            package=node_package,
            bounds=bounds,
            operations=tuple(operations),
            selected=selected,
        )
        if safety.allows(element):
            candidates.append(element)

    semantics = {
        "activity": activity,
        "package": focused_package,
        "text": page_values[:120],
        "elements": [element.guard() for element in candidates],
    }
    fingerprint = hashlib.sha256(json.dumps(semantics, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return Snapshot(
        activity=activity,
        package=focused_package,
        text="\n".join(page_values)[:6000],
        elements=tuple(candidates),
        fingerprint=fingerprint,
    )


class AdbDevice:
    def __init__(
        self,
        *,
        package: str,
        adb: str = DEFAULT_ADB,
        serial: str | None = None,
        timeout: float = 20,
    ):
        ReadOnlySafetyPolicy(package)
        self.adb = adb
        self.serial = serial
        self.package = package
        self.timeout = timeout

    def _command(self, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
        command = [self.adb]
        if self.serial:
            command.extend(("-s", self.serial))
        command.extend(args)
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout or self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"ADB command failed before completion: {type(exc).__name__}") from None
        if result.returncode:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise RuntimeError(f"ADB command failed ({result.returncode}): {message[:300]}")
        return result

    def observe(self) -> Snapshot:
        script = (
            "uiautomator dump /sdcard/ultrafast-android-assistant-window.xml >/dev/null 2>&1 && "
            "cat /sdcard/ultrafast-android-assistant-window.xml && "
            "rm -f /sdcard/ultrafast-android-assistant-window.xml && "
            f"printf '\\n{SNAPSHOT_MARKER}\\n' && "
            "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -2"
        )
        output = self._command("exec-out", "sh", "-c", script).stdout.decode("utf-8", "replace")
        if SNAPSHOT_MARKER not in output or "<?xml" not in output:
            raise RuntimeError("UIAutomator did not return a complete snapshot")
        before, focus = output.split(SNAPSHOT_MARKER, 1)
        xml = before[before.index("<?xml") :].strip()
        snapshot = parse_snapshot(xml, focus, package=self.package)
        if snapshot.package != self.package:
            raise UnsafeTarget(f"Focused package is {snapshot.package or 'unknown'}, expected {self.package}")
        return snapshot

    def execute(self, snapshot: Snapshot, *, operation: str, target: str | None = None) -> None:
        current = self.observe()
        if current.fingerprint != snapshot.fingerprint:
            raise StaleScreen("The Android screen changed after the decision; no input was sent")
        if operation == "WAIT":
            time.sleep(0.2)
            return
        if operation == "BACK":
            self._command("shell", "input", "keyevent", "KEYCODE_BACK", timeout=5)
            return
        if target is None:
            raise ValueError(f"{operation} requires an observed target")
        element = current.element(target)
        if operation not in element.operations:
            raise UnsafeTarget(f"Element {target} does not support {operation}")
        if not ReadOnlySafetyPolicy(self.package).allows(element):
            raise UnsafeTarget(f"Element {target} is blocked by the read-only policy")
        x, y = element.bounds.center
        if operation == "CLICK":
            self._command("shell", "input", "tap", str(x), str(y), timeout=5)
        elif operation in {"SCROLL_DOWN", "SCROLL_UP"}:
            top = element.bounds.top + max(8, element.bounds.height // 4)
            bottom = element.bounds.bottom - max(8, element.bounds.height // 4)
            start_y, end_y = (bottom, top) if operation == "SCROLL_DOWN" else (top, bottom)
            self._command(
                "shell", "input", "swipe", str(x), str(start_y), str(x), str(end_y), "180", timeout=5
            )
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        time.sleep(0.1)
