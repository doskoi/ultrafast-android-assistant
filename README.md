# Ultrafast Android Assistant

这是一个可复用的 Android UI 导航助手。它通过 UIAutomator 读取当前页面，把可见、可操作的控件
转换成有编号的有限动作空间，再让配置的 Laya/Jev provider 判断下一步操作和对应目标。
默认先用本地 Laya，必要时一次 failback 到 Jev。

设计采用“当前页面动作空间 + 一次 typed decision + 执行前 freshness 校验”的模式：

- 每一步都从当前页面重新生成动作空间；
- 一次 System One 请求同时生成操作、各操作的候选目标和完成判断；
- 代码只读取被选中操作对应的目标分支；
- 执行前重新观察页面，页面变化时拒绝输入。

它没有移植浏览器 DOM、selector 或 browser-harness。Android 侧使用 UIAutomator 作为可访问性树，
使用 ADB 执行经过代码校验的点击、滚动、返回和等待。

## 安装

需要 Python 3.12、`uv`、ADB，以及本机 checkout 的
[`laya-mlx`](https://github.com/mizorewww/laya-mlx)：

```bash
export LAYA_MLX_PATH=/Users/sj/projects/laya-mlx
# 可填本地 checkpoint 目录；也可填 Hugging Face model ID。
# 严格离线运行时必须填写已经下载好的本地目录。
export LAYA_MLX_MODEL=/absolute/path/to/laya-checkpoint

uv sync
uv pip install --python .venv/bin/python -e "$LAYA_MLX_PATH"
```

`LAYA_MLX_PATH` 是本地 checkout 的导入兜底；`uv pip install` 仍然是推荐的安装方式。`LAYA_MLX_MODEL`
可以是本地 checkpoint 目录或 model ID；如果省略，默认使用 `aac6fef/laya-multilingual-mlx`，首次加载
可能从 Hugging Face 下载权重。选择 Laya 时决策在本地完成；要做到完全离线，先下载权重并设置
`ULTRAFAST_SECONDARY_PROVIDER=none`。

## Dual provider

默认顺序是 `laya -> jev`。主 provider 不可用、返回 `BLOCKED`，或执行概率低于 `0.55` 时，
只尝试一次另一个 provider；如果 failback 也不可用，仍由本地概率门和调用方处理，不会强制执行动作。

```bash
export ULTRAFAST_PRIMARY_PROVIDER=laya
export ULTRAFAST_SECONDARY_PROVIDER=jev
# 切换成 Jev 主用、Laya failback：
# export ULTRAFAST_PRIMARY_PROVIDER=jev
# export ULTRAFAST_SECONDARY_PROVIDER=laya
```

`ULTRAFAST_SECONDARY_PROVIDER=none` 可关闭 failback，也接受兼容名称
`ULTRAFAST_FAILBACK_PROVIDER`。命令行可用 `--primary-provider laya|jev` 和
`--secondary-provider laya|jev|none` 临时覆盖 provider。`ULTRAFAST_FALLBACK_THRESHOLD` 和
`ULTRAFAST_COMPLETION_THRESHOLD` 控制弱操作与弱 DONE 结果何时切换。

Jev 是历史的 TypeSafe 远程 provider，需要 `TYPESAFE_API_KEY`。不要把密钥提交到仓库；运行 Android
命令前可以从权限为 `0600` 的本机文件加载：

```bash
source ~/.config/ultrafast/jev.env
```

不配置 Jev 时，Laya 仍可单独工作；含敏感内容的页面应保持
`ULTRAFAST_SECONDARY_PROVIDER=none`。

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

让本地 Laya 建议一步但不执行：

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

单元测试覆盖动作空间过滤、敏感信息脱敏、模型不可见坐标、单请求 speculative target、概率门槛、
完成判断和页面 freshness。当前实机验证结果和未验证边界见
[docs/live-validation.md](docs/live-validation.md)。
