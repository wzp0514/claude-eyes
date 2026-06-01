# Claude Eyes（红绿灯 / Traffic Light）

[Claude Code](https://claude.ai) 跨平台悬浮指示灯面板。用红绿黄灰四色圆点实时显示每个 Claude Code 窗口的运行状态——开窗亮灯，关窗灭灯。

![screenshot](screenshots/1.png)

## 功能

**面板显示**
- 四态指示灯 — 绿（工作中）/ 黄闪烁（等你确认）/ 灰（空闲）/ 红闪烁（出错）
- 灯居中布局 — `时间戳 ← ● → 项目名`，所有灯垂直对齐
- 双时间戳 — `|` 分割，显示你说话时间 + Claude 完成时间
- 置顶悬浮 — 永远在最前，可任意拖动

**会话管理**
- 多会话聚合 — 每个 Claude Code 窗口一个灯，开窗亮灯、关窗灭灯
- 时间排序 — 默认新会话在上（新开的往上摞），右键可切换
- 横竖排列切换 — 竖排显示时间戳+项目名，横排只显示灯

**健壮性**
- 自启动+自恢复 — Claude Code 启动时自动拉起；守护进程崩溃后数秒内自动重启
- 优雅清理 — 窗口关闭即时灭灯，崩溃/强杀兜底 600 秒超时
- 偏好持久化 — 排序方向、面板位置、全名开关保存到本地配置文件

**其他**
- 演示模式 — 右键菜单一键添加任意状态灯，无需真实会话即可预览
- 零外部依赖 — Python 标准库 + tkinter，跨 Windows / macOS / Linux

## 快速开始

### 0. 检查 Python

打开终端，确认 Python 已安装：

```bash
python --version   # 应显示 3.9 或更高
```

如果提示命令不存在：
- **Windows**：去 [python.org](https://python.org) 下载安装包，安装时勾选 "Add Python to PATH"
- **macOS**：`brew install python3`
- **Linux**：`sudo apt install python3 python3-pip python3-tk`（Ubuntu）/ `sudo dnf install python3 python3-pip python3-tkinter`（Fedora）

### 1. 安装并初始化

```bash
# 一条命令：安装 + 自动配置 hook
pip install git+https://github.com/wzp0514/claude-eyes.git && python -m claude_eyes.setup

# 没装 git？下载 ZIP 解压后：
cd claude-eyes-main && pip install . && python -m claude_eyes.setup
```

### 2. 验证

```bash
python -m claude_eyes.demo   # 面板应显示 4 个彩色圆点
```

重启 Claude Code。面板出现在屏幕右下角，发条消息就能看到对应窗口的灯。

Hook 自带自愈合：每次 SessionStart 会自动检查并补全缺失的配置。

## Hook 手动注册（备选方案）

如果 `python -m claude_eyes.setup` 无法使用，手动将以下配置加入 `~/.claude/settings.json`：

```json
{
  "hooks": {
    "SessionStart": [
      {"matcher": "", "hooks": [
        {"type": "command", "command": "python -m claude_eyes.start"},
        {"type": "command", "command": "python -m claude_eyes.hook"}
      ]}
    ],
    "UserPromptSubmit": [
      {"matcher": "", "hooks": [
        {"type": "command", "command": "python -m claude_eyes.hook"}
      ]}
    ],
    "PermissionRequest": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python -m claude_eyes.hook"}]}
    ],
    "PreToolUse": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python -m claude_eyes.hook"}]}
    ],
    "PostToolUse": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python -m claude_eyes.hook"}]}
    ],
    "PostToolUseFailure": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python -m claude_eyes.hook"}]}
    ],
    "Stop": [
      {"matcher": "", "hooks": [
        {"type": "command", "command": "python -m claude_eyes.hook"}
      ]}
    ],
    "SessionEnd": [
      {"matcher": "", "hooks": [{"type": "command", "command": "python -m claude_eyes.hook"}]}
    ]
  }
}
```

## 状态映射

| 颜色 | 含义 | 触发事件 |
|------|------|----------|
| 🟢 绿 | 工作中 | `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `SubagentStop` |
| 🟡 黄闪烁 | 等你确认 | `PermissionRequest` |
| ⚪ 灰 | 空闲 | `Stop`, `SessionStart` |
| 🔴 红闪烁 | 出错 | `PostToolUseFailure` |
| （消失） | 窗口关闭 | `SessionEnd` |

## 右键菜单

| 选项 | 说明 |
|------|------|
| 切换为横排 / 切换为竖排 | 切换布局方向 |
| 切换为上旧下新 / 切换为上新下旧 | 切换时间排序方向 |
| 面板位置 | 选择屏幕角落：右下角 / 右上角 / 左下角 / 左上角 |
| 显示全名 / 截断名称 | 切换项目名称完整显示或截断 |
| 演示模式 | 一键添加指示灯：🟢绿 / 🟡黄 / ⚪灰 / 🔴红 / 全部 / 清除 |
| 关闭 `<项目名>` | 关闭指定窗口的灯 |
| 全部关闭 | 关闭所有灯 |

## 架构

```
settings.json hooks
       │
       ▼ (stdin JSON)
   hook.py ──► status/{session_id}.json
       │  │         │
       │  │         ▼ (轮询 200ms)
       │  │     manager.py ──► panel.py (tkinter)
       │  │                       ├── HH:MM:SS  ●  项目名
       │  │                       └── ...
       │  │
       │  └──► _ensure_manager() — 心跳超时自动重启守护进程
       │
       ▼ (追加写入)
  logs/history.jsonl
```

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CLAUDE_TRAFFIC_LIGHT_DIR` | `~/.claude/traffic-light/` | 状态文件和日志的存储目录 |

## 性能

资源占用极低，全天后台运行无感：

- **CPU** — tkinter `after()` 事件驱动轮询，非忙等，空闲时接近 0%。
- **内存** — tkinter 面板窗口约 10 MB。
- **Hook 开销** — 每次事件触发一个独立 Python 进程，读 stdin → 写 JSON → 退出，<50ms。
- **对 Claude Code 零影响** — hook 进程和守护进程与 Claude Code 主进程完全解耦。

## License

MIT
