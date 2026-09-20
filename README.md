# Jev Android Assistant

这是一个可复用的 Android UI 导航助手。它通过 UIAutomator 读取当前页面，把可见、可操作的控件
转换成有编号的有限动作空间，再让本地 `laya-mlx` 判断下一步操作和对应目标。

设计参考 `browser-use/jev-ultrafast` 的
[`1231850a`](https://github.com/browser-use/jev-ultrafast/tree/1231850a0bf1a0c0341fe408ef1668dbbfdfac46)：

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
export LAYA_MLX_MODEL=/absolute/path/to/laya-checkpoint

uv sync
uv pip install --python .venv/bin/python -e "$LAYA_MLX_PATH"
```

`LAYA_MLX_MODEL` 应指向本地 checkpoint 目录；如果暂时不设置，它会使用 `laya-mlx` 的默认模型
ID，并在第一次加载时下载权重。上述 `uv pip install` 只安装本地库和依赖，不调用远程决策 API。

使用同一环境运行：

```bash
uv run --no-sync jev-android-assistant --serial emulator-5554 --package com.example.reader \
  suggest "打开今日榜单，看到榜单标题后停止"
```

ADB 默认从 `PATH` 查找，也可以设置 `ANDROID_ADB` 或传 `--adb`。每次运行必须显式提供允许操作的
Android package；助手发现前台应用不是这个 package 时会立即停止。

## 使用

先读取当前动作空间，不调用模型：

```bash
uv run --no-sync jev-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  inspect
```

让本地 Laya 建议一步但不执行：

```bash
uv run --no-sync jev-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  suggest '从当前页面打开今日榜单，看到榜单标题后停止'
```

执行有步数上限的导航：

```bash
uv run --no-sync jev-android-assistant \
  --serial emulator-5554 \
  --package com.example.reader \
  run '从当前页面打开今日榜单，看到榜单标题后停止' \
  --max-steps 12
```

Kaipl 可以直接作为一个调用方，不需要把助手代码放进 Kaipl 仓库。下面是 6.0.10 的实测 package；
其它版本应先用 ADB 确认 package：

```bash
uv run --no-sync jev-android-assistant \
  --serial emulator-5554 \
  --package com.yzj.kaipanh \
  suggest '从当前首页进入市场情绪页面，看到页面标题后停止'
```

## 执行边界

模型只收到页面语义、编号、角色和支持的操作，不会收到坐标、截图、原始 XML 或 ADB 命令。
坐标只在本地执行器中从刚观察到的节点计算。

第一版只支持 `CLICK`、`SCROLL_UP`、`SCROLL_DOWN`、`BACK`、`WAIT`、`DONE` 和 `BLOCKED`。
它不会输入文本；密码节点、隐藏节点、所有开关/复选框以及购买、支付、订阅、关注、删除、登录、
保存、编辑等明确写操作不会进入动作空间。

自动执行默认要求操作和目标的最低概率都达到 `0.55`。`DONE` 同时要求操作概率达到该阈值，
并且完成判断达到 `0.85`。这些值是保守初值，应使用目标应用的真实导航轨迹评估后再调整。

## 验证

```bash
uv run --no-sync ruff check .
uv run --no-sync pytest -q
uv build
```

单元测试覆盖动作空间过滤、敏感信息脱敏、模型不可见坐标、单请求 speculative target、概率门槛、
完成判断和页面 freshness。当前实机验证结果和未验证边界见
[docs/live-validation.md](docs/live-validation.md)。
