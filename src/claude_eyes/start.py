"""Called from SessionStart hook — ensures manager daemon is running."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from claude_eyes.config import BASE_DIR, LOCK_TIMEOUT, MANAGER_LOCK

HEARTBEAT_FILE = BASE_DIR / "manager.heartbeat"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
BACKUP_PATH = BASE_DIR / "settings_backup.json"

# Commands to inject into settings.json hooks
REQUIRED_HOOKS: dict[str, list[str]] = {
    "SessionStart": [
        "python -m claude_eyes.start",
        "python -m claude_eyes.hook",
    ],
    "UserPromptSubmit": ["python -m claude_eyes.hook"],
    "PermissionRequest": ["python -m claude_eyes.hook"],
    "PreToolUse": ["python -m claude_eyes.hook"],
    "PostToolUse": ["python -m claude_eyes.hook"],
    "PostToolUseFailure": ["python -m claude_eyes.hook"],
    "Stop": ["python -m claude_eyes.hook"],
    "SessionEnd": ["python -m claude_eyes.hook"],
}


def _is_ours(cmd: str) -> bool:
    return "claude_eyes.hook" in cmd or "claude_eyes.start" in cmd


def is_configured() -> bool:
    """Check if all required claude-eyes hooks are in settings.json."""
    if not SETTINGS_PATH.exists():
        return False
    try:
        config = json.loads(SETTINGS_PATH.read_text())
        hooks = config.get("hooks", {})
    except Exception:
        return False
    for event, cmds in REQUIRED_HOOKS.items():
        existing = hooks.get(event, [])
        for cmd in cmds:
            found = any(
                _is_ours(h.get("command", ""))
                for entry in existing
                for h in entry.get("hooks", [])
            )
            if not found:
                return False
    return True


def configure_hooks() -> bool:
    """Add claude-eyes hooks to settings.json. Returns True if changes made.

    Backs up the original config first. Idempotent — safe to call repeatedly.
    """
    if not SETTINGS_PATH.exists():
        return False
    if is_configured():
        return False

    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SETTINGS_PATH, BACKUP_PATH)

    config = json.loads(SETTINGS_PATH.read_text())
    hooks = config.get("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}

    for event, cmds in REQUIRED_HOOKS.items():
        existing = hooks.get(event, [])
        if not isinstance(existing, list):
            existing = []
        # Remove old entries to avoid duplicates
        cleaned = [e for e in existing if not any(
            _is_ours(h.get("command", "")) for h in e.get("hooks", [])
        )]
        for cmd in cmds:
            cleaned.append({
                "matcher": "",
                "hooks": [{"type": "command", "command": cmd}],
            })
        hooks[event] = cleaned

    config["hooks"] = hooks
    SETTINGS_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    return True


def _pid_exists(pid: int) -> bool:
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        )
        return str(pid) in result.stdout
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _manager_alive() -> bool:
    if not HEARTBEAT_FILE.exists():
        return False
    try:
        content = HEARTBEAT_FILE.read_text().strip()
        parts = content.split("\n", 1)
        if len(parts) == 2:
            pid = int(parts[0])
            ts = float(parts[1])
        else:
            # Legacy format: just a timestamp, no PID
            ts = float(parts[0])
            pid = None
        age = time.time() - ts
        if age >= 5:
            return False
        if pid is not None:
            return _pid_exists(pid)
        return True
    except Exception:
        return False


def acquire_startup_lock() -> bool:
    """Atomically acquire the manager startup lock. Returns True if caller
    should proceed to start the manager (either fresh lock acquired, or
    stale lock detected and the caller chooses to proceed).

    Uses O_CREAT|O_EXCL for atomic creation.  Falls back to replacing a
    stale lock file — the os.O_EXCL in the retry ensures at most one
    caller wins.
    """
    try:
        fd = os.open(MANAGER_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        pass
    except OSError:
        return False

    # Lock file exists — check freshness
    try:
        age = time.time() - MANAGER_LOCK.stat().st_mtime
    except OSError:
        return False

    if age < LOCK_TIMEOUT:
        return False  # fresh lock held by another process

    # Stale lock — try to steal it atomically
    try:
        MANAGER_LOCK.unlink(missing_ok=True)
        fd = os.open(MANAGER_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except (FileExistsError, OSError):
        return False


def main() -> None:
    # Self-healing: fix missing hooks on every SessionStart
    if configure_hooks():
        print("claude-eyes: hooks registered in settings.json")

    if _manager_alive():
        sys.exit(0)

    MANAGER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    if not acquire_startup_lock():
        sys.exit(0)

    try:
        if _manager_alive():
            sys.exit(0)
        manager_py = Path(__file__).resolve().parent / "manager.py"
        if sys.platform == "win32":
            subprocess.Popen(
                ["pythonw", str(manager_py)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.Popen(
                ["python3", str(manager_py)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
