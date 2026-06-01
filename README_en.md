# Claude Eyes (Traffic Light)

A cross-platform floating indicator panel for [Claude Code](https://claude.ai) sessions. Shows real-time status dots so you always know what your Claude windows are doing — even when they're buried under other apps.

![screenshot](screenshots/1.png)

## Features

**Panel display**
- 4-state indicators — green (working), yellow blink (waiting), gray (idle), red blink (error)
- Dot-centered layout — `timestamp ← ● → project name`, all dots vertically aligned
- Dual timestamps — shows when you spoke + when Claude finished, separated by `|`
- Always-on-top — drag anywhere, never buried under other windows

**Session management**
- Multi-session — one light per Claude Code window, auto appear/disappear as windows open/close
- Time-sorted — newest on top by default, right-click to toggle
- Horizontal / vertical layout — vertical shows timestamps + names, horizontal shows dots only

**Reliability**
- Auto-start + auto-recovery — launches with Claude Code; restarts within seconds if daemon crashes
- Graceful cleanup — removes indicators on window close; 600 s staleness timeout for force-kill
- Preference persistence — sort order, position, full-name toggle saved to local config file

**Extras**
- Demo mode — right-click to preview any state instantly, no real session needed
- Zero external dependencies — Python stdlib + tkinter, runs on Windows / macOS / Linux

## Quick Start

### 0. Check Python

Open a terminal and verify Python is installed:

```bash
python --version   # or python3 --version on macOS/Linux
```

If not found:
- **Windows**: download from [python.org](https://python.org), check "Add Python to PATH" during install
- **macOS**: `brew install python3`
- **Linux**: `sudo apt install python3 python3-pip python3-tk` (Ubuntu) / `sudo dnf install python3 python3-pip python3-tkinter` (Fedora)

### 1. Install & Setup

```bash
# One command: install + auto-configure hooks
pip install git+https://github.com/wzp0514/claude-eyes.git && python -m claude_eyes.setup

# Or if you don't have git — download ZIP, then:
cd claude-eyes-main && pip install . && python -m claude_eyes.setup
```

### 2. Verify

```bash
python -m claude_eyes.demo   # should show 4 colored dots
```

Restart Claude Code. The panel appears in the bottom-right corner — send a message in any Claude window and its light will appear.

Hook registration is self-healing: every `SessionStart` re-checks and re-adds hooks if they were accidentally removed.

## Manual Hook Registration (alternative)

If `python -m claude_eyes.setup` doesn't work for you, manually add these to `~/.claude/settings.json`:

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

## Status Map

| Color | Status | Trigger Events |
|-------|--------|----------------|
| Green | Working | `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `SubagentStop` |
| Yellow (blink) | Waiting for approval | `PermissionRequest` |
| Gray | Idle | `Stop`, `SessionStart` |
| Red (blink) | Error | `PostToolUseFailure` |
| (removed) | Window closed | `SessionEnd` |

## Right-Click Menu

| Option | Description |
|--------|-------------|
| Switch horizontal / vertical | Toggle layout direction |
| Sort (newest-first / oldest-first) | Toggle time sort order |
| Panel position | Pick corner: bottom-right, top-right, bottom-left, top-left |
| Show full name / Truncate name | Toggle project name length |
| Demo mode | Add fake indicators: green / yellow / gray / red / all / clear |
| Close `<project>` | Remove a specific indicator |
| Close all | Remove all indicators |

## Architecture

```
settings.json hooks
       │
       ▼ (stdin JSON)
   hook.py ──► status/{session_id}.json
       │  │         │
       │  │         ▼ (poll 200ms)
       │  │     manager.py ──► panel.py (tkinter)
       │  │                       ├── HH:MM:SS  ●  project
       │  │                       └── ...
       │  │
       │  └──► _ensure_manager() — auto-restart daemon if heartbeat stale
       │
       ▼ (append)
  logs/history.jsonl
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_TRAFFIC_LIGHT_DIR` | `~/.claude/traffic-light/` | Base directory for status & logs |

## Development

```bash
pip install -e .
pytest tests/ -v
```

## Performance

Negligible resource footprint — safe to keep running at all times:

- **CPU** — `tkinter.after()` event-driven polling, not busy-wait. Reads a few tiny JSON files per cycle. Idle CPU ≈ 0%.
- **Memory** — ~10 MB for the tkinter panel window.
- **Hook overhead** — one-shot Python process per event: read stdin → write JSON → exit. <50 ms, no persistent work.
- **Zero impact on Claude Code** — hook processes and manager daemon are fully decoupled from Claude Code's main process.

## License

MIT
