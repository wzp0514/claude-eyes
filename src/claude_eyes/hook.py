"""Claude Code hook entry point. Reads stdin JSON, writes status + history."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from claude_eyes.config import STATUS_DIR, LOG_DIR, MANAGER_LOCK
from claude_eyes.start import acquire_startup_lock, _manager_alive


def _ensure_manager() -> None:
    """Start manager daemon if heartbeat is stale or missing."""
    if _manager_alive():
        return

    MANAGER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    if not acquire_startup_lock():
        return

    try:
        if _manager_alive():
            return
        manager_py = Path(__file__).resolve().parent / "manager.py"
        if sys.platform == "win32":
            subprocess.Popen(["pythonw", str(manager_py)], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["python3", str(manager_py)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

EVENT_STATUS = {
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "PostToolUse": "working",
    "PreCompact": "working",
    "SubagentStop": "working",
    "PermissionRequest": "waiting",
    "Stop": "idle",
    "SessionStart": "idle",
    "SessionEnd": "closed",
    "PostToolUseFailure": "error",
}

# Events that count as "user spoke"
USER_EVENTS = {"UserPromptSubmit"}
# Events that count as "claude finished"
CLAUDE_EVENTS = {"Stop", "PostToolUse", "PostToolUseFailure"}


def handle(stdin_text: str = "") -> dict:
    """Process hook input and return the status payload written to disk."""
    if not stdin_text:
        try:
            stdin_text = sys.stdin.read()
        except Exception:
            pass

    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        data = {}

    event = data.get("hook_event_name", "")
    session_id = data.get("session_id", "")
    if not session_id or session_id == "unknown":
        return {"status": "skipped", "reason": "invalid session_id"}

    tool_name = data.get("tool_name", "")
    cwd = data.get("cwd", "")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    status = EVENT_STATUS.get(event, "working")

    # --- read existing file to preserve dual timestamps ---
    status_file = STATUS_DIR / f"{session_id}.json"
    prev: dict = {}
    try:
        prev = json.loads(status_file.read_text())
    except Exception:
        pass

    prompt_time = prev.get("prompt_time")
    done_time = prev.get("done_time")

    if event in USER_EVENTS:
        prompt_time = now_iso
    if event in CLAUDE_EVENTS:
        done_time = now_iso
    if event == "SessionStart":
        prompt_time = now_iso
        done_time = now_iso

    payload = {
        "status": status,
        "session_id": session_id,
        "tool_name": tool_name,
        "last_event": event,
        "cwd": cwd,
        "prompt_time": prompt_time or now_iso,
        "done_time": done_time or now_iso,
        "timestamp": now_iso,
    }

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "history.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return payload


def main() -> None:
    _ensure_manager()
    handle()
    sys.exit(0)


if __name__ == "__main__":
    main()
