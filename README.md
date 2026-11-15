# Ultrafast Android Assistant

这是一个可复用的 Android UI 导航助手。它通过 UIAutomator 读取当前页面，把可见、可操作的控件
转换成有编号的有限动作空间，再让远程 Jev 判断下一步操作和对应目标。
Jev 是唯一模型 provider；已移除本地模型接线和 failback。

设计采用“当前页面动作空间 + 两阶段 typed decision + 执行前 freshness 校验”的模式：

- 每一步都从当前页面重新生成动作空间；
- 第一次 System One 请求用 `Choice` 生成操作、用 `Noul` 判断完成状态；
- 如果操作需要目标，第二次请求只生成该操作的候选目标，避免无关目标分支扩大 token；
- 执行前重新观察页面，页面变化时拒绝输入。

它没有移植浏览器 DOM、selector 或 browser-harness。Android 侧使用 UIAutomator 作为可访问性树，
使用 ADB 执行经过代码校验的点击、滚动、返回和等待。

## 安装

需要 Python 3.12、`uv` 和 ADB：

```bash
uv sync
```

已有环境若还单独安装着本地模型程序，更新本项目时使用 `uv pip install --no-deps -e .`，
避免用会精确同步依赖的命令清除那些独立安装。无需卸载本地程序、删除模型或更改机器配置。

Jev 通过 `typesafe-sdk` 调用远程服务，需要 `TYPESAFE_API_KEY`。运行 `suggest` 或 `run` 会把
当前 UI 的语义内容发送到该服务。不要把密钥提交到仓库；运行 Android 命令前可以从权限为 `0600`
的本机文件加载：

```bash
source ~/.config/ultrafast/jev.env
```

含敏感内容的 UI tree 不得发送到远程 Jev，应使用本地确定性 UIAutomator/ADB 导航或人工确认。
任何数据授权都必须限定到准确的 UI tree 和接收方，并保留所有适用的 Skill 数据限制；
local-only 授权不允许远程传输，也不会恢复已移除的接线。`inspect` 不调用模型。

旧的本地模型 adapter、`UltrafastPolicy`、`DualPolicy`、`--primary-provider` 和
`--secondary-provider` 已删除。代码调用方应显式使用 `JevPolicy`。`--model` 和
`TYPESAFE_DEFAULT_MODEL` 只接受远程模型配置；Laya model ID 或本地路径会被拒绝。

为避免把旧的本地配置静默改为远程请求，以下设置会在请求前报错：

- `ULTRAFAST_PRIMARY_PROVIDER` 选择 `jev` 以外的 provider；
- `ULTRAFAST_SECONDARY_PROVIDER` 或兼容名称 `ULTRAFAST_FAILBACK_PROVIDER` 指定任何 provider；
- 任意非空的 `LAYA_MLX_*` 环境变量。

共享环境可以保留 `ULTRAFAST_PRIMARY_PROVIDER=jev` 以及 secondary/failback 为 `none`、`off`
或 `disabled` 的设置；它们只用于检查兼容配置，不再提供路由能力。确认允许远程处理后，才清除
当前进程中的旧配置。单独安装的 Laya 程序和模型可以保留；本项目不会导入、加载或卸载它们。
`ULTRAFAST_FALLBACK_THRESHOLD` 和 `ULTRAFAST_COMPLETION_THRESHOLD` 不再控制 provider 切换；
执行概率和完成概率仍由 `--min-probability`、`--completion-threshold` 控制。

ADB 默认从 `PATH` 查找。本机的 SDK ADB 路径是
`/Users/sj/Library/Android/sdk/platform-tools/adb`；如果 `adb` 不在 `PATH`，请设置
`ANDROID_ADB` 或在每条命令中传 `--adb /Users/sj/Library/Android/sdk/platform-tools/adb`。

使用同一环境运行：

```bash
uv run --no-sync ultrafast-android-assistant --serial emulator-5554 --package com.example.reader \
  suggest "打开今日榜单，看到榜单标题后停止"
```

每次运行必须显式提供允许操作的 Android package；助手发现前台应用不是这个 package 时会立即停止。

## 使用

先读取当前动作空间，不调用模型：

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  inspect
```

让远程 Jev 建议一步但不执行：

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  suggest '从当前页面打开今日榜单，看到榜单标题后停止'
```

执行有步数上限的导航：

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  run '从当前页面打开今日榜单，看到榜单标题后停止' \
  --max-steps 12
```

Kaipl 可以直接作为一个调用方，不需要把助手代码放进 Kaipl 仓库。下面是 6.0.10 的实测 package；
其它版本应先用 ADB 确认 package：

```bash
uv run --no-sync ultrafast-android-assistant \
  --serial emulator-5554 \
  --package com.yzj.kaipanh \
  suggest '从当前首页进入市场情绪页面，看到页面标题后停止'
```

## 推荐的操作策略：确定性优先，Ultrafast 兜底

Ultrafast 是导航判断器，不是所有 Android 操作的必经步骤。为了提高批量调查和版本对比的效率，按下面的
优先级选择路径：

1. **静态 APK 对比不启动模拟器，也不调用 Ultrafast。** 直接比较 JADX/DEX、资源、Manifest、字符串、
   网络入口和已经记录的 API 证据。
2. **已知页面和稳定控件不调用 Ultrafast。** 由本地代码读取 UIAutomator 树，用稳定的
   `resource-id`、文本、content description 或控件角色匹配目标，然后通过经过校验的 ADB 执行点击、
   滚动、返回和等待。每次输入前仍须重新观察页面并检查 fingerprint，不能复用过期坐标或旧节点。
3. **只有页面结构变化、入口不确定或多个控件语义相近时调用 Ultrafast。** Ultrafast 只返回当前观察结果中的
   操作和目标编号；本地代码从同一份刚观察的 UI 树取得 bounds，再交给 ADB 执行。模型不得生成坐标、
   selector、shell 命令或输入内容。
4. **操作完成后优先做本地验证。** 先用 UIAutomator、页面 fingerprint、前台 Activity、日志或网络
   观察确认状态变化；不要为了验证每一步再次调用模型。

典型的高效链路是：

```text
静态 APK 扫描
  -> 本地规则匹配已知控件
  -> ADB 执行并等待页面变化
  -> 本地验证
  -> 只有匹配失败或语义不确定时，调用一次 Ultrafast
```

对新页面，`inspect` 用于读取动作空间；`suggest` 适合在第一次确认路径时只取一步建议。确认轨迹
是只读导航后，直接使用有步数上限的 `run`，不要对同一步骤先执行一次 `suggest`，再让 `run` 重复
判断，否则会产生重复模型请求。代码调用方也可以直接使用 `AndroidAssistant.step(..., execute=True)`，
由一次 Ultrafast 判断接一次本地 ADB 执行。

因此，功能 Gap 扫描应先按“静态证据 -> 已知流程的确定性回归 -> 仅对未知分支使用 Ultrafast”的顺序进行。
Ultrafast 的点击日志只能证明导航到了某个页面，不能单独证明 API 请求、字段含义、分页或 Gateway 合同。

## 执行边界

模型只收到页面语义、编号、角色和支持的操作，不会收到坐标、截图、原始 XML 或 ADB 命令。
坐标只在本地执行器中从刚观察到的节点计算。

第一版只支持 `CLICK`、`SCROLL_UP`、`SCROLL_DOWN`、`BACK`、`WAIT`、`DONE` 和 `BLOCKED`。
它不会输入文本；密码节点、隐藏节点、所有开关/复选框以及购买、支付、订阅、关注、删除、登录、
保存、编辑等明确写操作不会进入动作空间。

自动执行默认要求操作和目标的最低概率都达到 `0.55`。`DONE` 同时要求操作概率达到该阈值，
并且完成判断达到 `0.85`。这些值是保守初值，应使用目标应用的真实导航轨迹评估后再调整。

真实使用时不要为了让某个目标“成功”而降低阈值或强制执行低置信度动作。模型选错目标或概率不足时，
预期结果是 `needs_review`，不发送输入；应改进目标描述、使用确定性 UIAutomator 匹配，或回退到本地
人工确认。`inspect` 不调用模型，`suggest` 只建议不执行，只有有步数上限的 `run` 才会执行动作。

## 验证

```bash
uv run --no-sync ruff check .
uv run --no-sync pytest -q
uv build
```

单元测试覆盖动作空间过滤、敏感信息脱敏、模型不可见坐标、两阶段目标选择、概率门槛、
完成判断和页面 freshness。当前实机验证结果和未验证边界见
[docs/live-validation.md](docs/live-validation.md)。
