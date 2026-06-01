"""Daemon that monitors status/ dir and manages the indicator panel."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tkinter as tk
from datetime import datetime, timezone

from claude_eyes.config import (
    MANAGER_LOCK,
    POLL_INTERVAL,
    STALE_TIMEOUT,
    STATUS_DIR,
)
from claude_eyes.panel import Panel
from claude_eyes.start import _pid_exists, configure_hooks

HEARTBEAT_FILE = STATUS_DIR.parent / "manager.heartbeat"


def _another_manager_running() -> bool:
    """Check if a different manager process is already alive (defense in depth)."""
    if not HEARTBEAT_FILE.exists():
        return False
    try:
        content = HEARTBEAT_FILE.read_text().strip()
        parts = content.split("\n", 1)
        if len(parts) != 2:
            return False
        pid = int(parts[0])
        ts = float(parts[1])
        if pid == os.getpid():
            return False
        if time.time() - ts >= 5:
            return False
        return _pid_exists(pid)
    except Exception:
        return False


def _kill_old_manager() -> None:
    """Kill any previous manager process found in the heartbeat file."""
    if not HEARTBEAT_FILE.exists():
        return
    try:
        content = HEARTBEAT_FILE.read_text().strip()
        parts = content.split("\n", 1)
        if len(parts) != 2:
            return
        pid = int(parts[0])
        if pid == os.getpid():
            return
        if not _pid_exists(pid):
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.kill(pid, 9)
    except Exception:
        pass


class Manager:
    def __init__(self) -> None:
        # Kill any previous manager process before proceeding
        _kill_old_manager()

        # Guard: if another manager is still running, exit
        if _another_manager_running():
            sys.exit(0)

        # One-time hook registration on first manager start
        try:
            configure_hooks()
        except Exception:
            pass

        self._root = tk.Tk()
        self._root.withdraw()

        STATUS_DIR.mkdir(parents=True, exist_ok=True)

        self._panel = Panel(self._root)
        self._known: set[str] = set()

        self._heartbeat()
        self._poll()
        self._root.mainloop()
        try:
            HEARTBEAT_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        MANAGER_LOCK.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # heartbeat
    # ------------------------------------------------------------------
    def _heartbeat(self) -> None:
        HEARTBEAT_FILE.write_text(f"{os.getpid()}\n{time.time()}")
        MANAGER_LOCK.unlink(missing_ok=True)
        self._root.after(2000, self._heartbeat)

    # ------------------------------------------------------------------
    # poll
    # ------------------------------------------------------------------
    def _poll(self) -> None:
        try:
            self._scan()
        except Exception:
            pass
        self._root.after(POLL_INTERVAL, self._poll)

    def _scan(self) -> None:
        if not STATUS_DIR.exists():
            return

        now = datetime.now(timezone.utc)
        seen: set[str] = set()
        entries: list[tuple[str, dict]] = []

        for fp in sorted(STATUS_DIR.glob("*.json")):
            sid = fp.stem

            try:
                data = json.loads(fp.read_text())
            except Exception:
                continue

            status = data.get("status", "idle")

            # SessionEnd → remove immediately
            if status == "closed":
                self._panel.remove(sid)
                self._known.discard(sid)
                fp.unlink(missing_ok=True)
                continue

            # staleness — crash safety net (600 s)
            try:
                ts = datetime.fromisoformat(data.get("timestamp", ""))
                age = (now - ts).total_seconds()
            except Exception:
                age = 99999

            if age > STALE_TIMEOUT:
                self._panel.remove(sid)
                self._known.discard(sid)
                fp.unlink(missing_ok=True)
                continue

            seen.add(sid)
            entries.append((sid, data))

        # Sort by prompt_time DESC — newest packed first (at top), oldest at bottom
        entries.sort(key=lambda x: x[1].get("prompt_time", ""), reverse=True)

        for sid, data in entries:
            self._panel.upsert(sid, data)

        # clean up entries for files that disappeared
        gone = self._known - seen
        for sid in gone:
            self._panel.remove(sid)
        self._known = seen


def main() -> None:
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    Manager()


if __name__ == "__main__":
    main()
