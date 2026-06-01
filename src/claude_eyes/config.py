"""Configuration constants. Override via env vars for custom setups."""
import os
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("CLAUDE_TRAFFIC_LIGHT_DIR", Path.home() / ".claude" / "traffic-light")
)

STATUS_DIR = BASE_DIR / "status"
LOG_DIR = BASE_DIR / "logs"
PANEL_CONFIG = BASE_DIR / "panel_config.json"
MANAGER_LOCK = BASE_DIR / "manager.lock"

POLL_INTERVAL = 200       # ms, status file poll rate
BLINK_INTERVAL = 500      # ms, on/off toggle for blinking
STALE_TIMEOUT = 600       # seconds — crash safety net for sessions with no updates
LOCK_TIMEOUT = 10         # seconds — startup lock considered stale after this
INDICATOR_SIZE = 20       # pixels

GREEN = (0, 200, 0)
YELLOW = (255, 200, 0)
RED = (220, 30, 30)
GRAY = (140, 140, 140)
OFF = (60, 60, 60)

COLOR_MAP = {
    "working": GREEN,
    "waiting": YELLOW,
    "idle": GRAY,
    "error": RED,
}
