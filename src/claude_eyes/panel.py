"""Panel window — groups all session indicators into one draggable container."""
from __future__ import annotations

import json
import tkinter as tk
from collections import OrderedDict
from datetime import datetime, timezone

from claude_eyes.config import (
    BLINK_INTERVAL,
    COLOR_MAP,
    GRAY,
    INDICATOR_SIZE,
    OFF,
    PANEL_CONFIG,
)
from claude_eyes import demo as _demo

LOCAL_TZ = datetime.now(timezone.utc).astimezone().tzinfo
DOT_SIZE = INDICATOR_SIZE - 2  # 18px dot in 20px frame

STATUS_LABEL: dict[str, str] = {
    "working": "working",
    "waiting": "waiting",
    "idle": "idle",
    "error": "error",
}


class Panel:
    """A borderless always-on-top container that holds session indicator entries."""

    def __init__(self, master: tk.Tk) -> None:
        self._master = master
        self._vertical = True
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._drag_x = 0
        self._drag_y = 0

        cfg = self._load_config()
        self._sort_descending = cfg.get("sort_descending", True)  # True=上新下旧
        self._position = cfg.get("position", "bottom-right")
        self._show_full_name = cfg.get("show_full_name", False)

        # --- window ---
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#0a0a0a")
        self.win.protocol("WM_DELETE_WINDOW", self.destroy)

        self._container = tk.Frame(self.win, bg="#0a0a0a")
        self._container.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self._user_dragged = False  # stop auto-positioning after user drags

        # --- drag bindings: toplevel catches clicks on child widgets ---
        self.win.bind("<ButtonPress-1>", self._on_drag_start)
        self.win.bind("<B1-Motion>", self._on_drag_move)
        self.win.bind("<Button-3>", self._on_right_click)
        self._container.bind("<ButtonPress-1>", self._on_drag_start)
        self._container.bind("<B1-Motion>", self._on_drag_move)

        # --- menu ---
        self._menu = tk.Menu(self.win, tearoff=0)

        # --- blink timer ---
        self._blink_on = True
        self._blink_job: str | None = None
        self._start_blink_timer()

        # --- initial position ---
        self.win.after(100, lambda: self._anchor_to(self._position))

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def upsert(self, sid: str, data: dict) -> None:
        was_empty = not self._entries
        is_new = sid not in self._entries
        if is_new:
            entry = _Entry(self._container, sid, data, self._show_full_name)
            self._bind_drag_to_widget(entry.frame)
            self._pack_entry(entry)
            self._entries[sid] = entry
        else:
            self._entries[sid].update(data)
        if was_empty:
            self._show()
        if is_new:
            self._repack_all()
        self._maybe_reposition()

    def remove(self, sid: str) -> None:
        entry = self._entries.pop(sid, None)
        if entry is not None:
            entry.frame.destroy()
        if not self._entries:
            self._hide()
        self._maybe_reposition()

    def clear(self) -> None:
        for entry in self._entries.values():
            entry.frame.destroy()
        self._entries.clear()
        self._hide()
        self._maybe_reposition()

    def destroy(self) -> None:
        self._cancel_blink()
        self._menu.destroy()
        self.win.destroy()
        self._master.destroy()

    # ------------------------------------------------------------------
    # blink timer (drives all dot blink states)
    # ------------------------------------------------------------------
    def _start_blink_timer(self) -> None:
        self._blink_on = not self._blink_on
        for entry in self._entries.values():
            entry.apply_blink(self._blink_on)
        self._blink_job = self.win.after(BLINK_INTERVAL, self._start_blink_timer)

    def _cancel_blink(self) -> None:
        if self._blink_job is not None:
            self.win.after_cancel(self._blink_job)
            self._blink_job = None

    # ------------------------------------------------------------------
    # show / hide
    # ------------------------------------------------------------------
    def _show(self) -> None:
        self.win.deiconify()

    def _hide(self) -> None:
        self.win.withdraw()

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _pack_entry(self, entry: _Entry) -> None:
        if self._vertical:
            entry.frame.pack(fill=tk.X, pady=1)
            entry.show_details()
        else:
            entry.frame.pack(side=tk.LEFT, padx=1)
            entry.hide_details()

    def _toggle_layout(self) -> None:
        self._vertical = not self._vertical
        for entry in self._entries.values():
            entry.frame.pack_forget()
        for entry in self._entries.values():
            self._pack_entry(entry)
        self._maybe_reposition()

    # ------------------------------------------------------------------
    # config persist
    # ------------------------------------------------------------------
    def _load_config(self) -> dict:
        try:
            return json.loads(PANEL_CONFIG.read_text())
        except Exception:
            PANEL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            return {}

    def _save_config(self) -> None:
        PANEL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        PANEL_CONFIG.write_text(json.dumps({
            "sort_descending": self._sort_descending,
            "position": self._position,
            "show_full_name": self._show_full_name,
        }, ensure_ascii=False))

    # ------------------------------------------------------------------
    # positioning
    # ------------------------------------------------------------------
    def _anchor_to(self, position: str) -> None:
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w = max(self.win.winfo_width(), self.win.winfo_reqwidth())
        h = max(self.win.winfo_height(), self.win.winfo_reqheight())
        x = 30 if "left" in position else sw - w - 30
        y = 30 if "top" in position else sh - h - 80
        self.win.geometry(f"+{x}+{y}")

    def _set_position(self, position: str) -> None:
        self._position = position
        self._user_dragged = False
        self._anchor_to(position)
        self._save_config()

    def _maybe_reposition(self) -> None:
        if not self._user_dragged:
            self.win.after(50, lambda: self._anchor_to(self._position))

    def _toggle_full_name(self) -> None:
        self._show_full_name = not self._show_full_name
        for entry in self._entries.values():
            entry.set_show_full(self._show_full_name)
        self._maybe_reposition()
        self._save_config()

    def _toggle_sort(self) -> None:
        self._sort_descending = not self._sort_descending
        self._repack_all()
        self._save_config()

    def _repack_all(self) -> None:
        items = list(self._entries.items())
        items.sort(
            key=lambda x: x[1]._prompt_time,
            reverse=self._sort_descending,
        )
        for _, entry in items:
            entry.frame.pack_forget()
        for _, entry in items:
            self._pack_entry(entry)

    # ------------------------------------------------------------------
    # drag
    # ------------------------------------------------------------------
    def _on_drag_start(self, event: tk.Event) -> None:
        self._user_dragged = True
        self._drag_x = event.x_root - self.win.winfo_x()
        self._drag_y = event.y_root - self.win.winfo_y()

    def _on_drag_move(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # right-click menu
    # ------------------------------------------------------------------
    def _on_right_click(self, event: tk.Event) -> None:
        self._menu.delete(0, "end")
        self._menu.add_command(
            label="切换为横排" if self._vertical else "切换为竖排",
            command=self._toggle_layout,
        )
        self._menu.add_command(
            label="切换为上旧下新" if self._sort_descending else "切换为上新下旧",
            command=self._toggle_sort,
        )
        # position submenu
        pos_menu = tk.Menu(self._menu, tearoff=0)
        for pos_value, pos_label in [
            ("bottom-right", "右下角"), ("top-right", "右上角"),
            ("bottom-left", "左下角"), ("top-left", "左上角"),
        ]:
            pos_menu.add_command(
                label=pos_label + (" ✓" if self._position == pos_value else ""),
                command=lambda p=pos_value: self._set_position(p),
            )
        self._menu.add_cascade(label="面板位置", menu=pos_menu)
        self._menu.add_command(
            label="显示全名" if not self._show_full_name else "截断名称",
            command=self._toggle_full_name,
        )
        # demo submenu
        demo_menu = tk.Menu(self._menu, tearoff=0)
        demo_menu.add_command(label="🟢 绿灯（工作中）", command=lambda: _demo.cmd_add(["demo-working", "working"]))
        demo_menu.add_command(label="🟡 黄灯（等待确认）", command=lambda: _demo.cmd_add(["demo-waiting", "waiting"]))
        demo_menu.add_command(label="⚪ 灰灯（空闲中）", command=lambda: _demo.cmd_add(["demo-idle", "idle"]))
        demo_menu.add_command(label="🔴 红灯（出错了）", command=lambda: _demo.cmd_add(["demo-error", "error"]))
        demo_menu.add_command(label="🎨 全部演示状态", command=_demo.cmd_demo)
        demo_menu.add_separator()
        demo_menu.add_command(label="清除所有演示灯", command=_demo.cmd_clear)
        self._menu.add_cascade(label="演示模式", menu=demo_menu)
        self._menu.add_separator()
        if self._entries:
            for sid, e in self._entries.items():
                self._menu.add_command(
                    label=f"关闭 {e.project_name}",
                    command=lambda s=sid: self.remove(s),
                )
        self._menu.add_separator()
        self._menu.add_command(label="全部关闭", command=self.destroy)
        self._menu.post(event.x_root, event.y_root)

    def _bind_drag_to_widget(self, w: tk.Widget) -> None:
        """Bind drag start + move to a widget and all its children."""
        w.bind("<ButtonPress-1>", self._on_drag_start)
        w.bind("<B1-Motion>", self._on_drag_move)
        for child in w.winfo_children():
            self._bind_drag_to_widget(child)


# ======================================================================
class _Entry:
    """One row: timestamp ← ● → project_name, dot centered."""

    def __init__(self, parent: tk.Frame, sid: str, data: dict, show_full: bool = False) -> None:
        self.sid = sid
        self.project_name = _project_name(data.get("cwd", ""))
        self._prompt_time = ""
        self._blinking = False
        self._color_rgb = GRAY
        self._ts_str = ""
        self._show_full = show_full

        self.frame = tk.Frame(parent, bg="#0a0a0a")

        self._inner = tk.Frame(self.frame, bg="#0a0a0a")
        self._inner.pack(expand=True, fill=tk.X)

        # Grid: col 0 = col 2 forced equal-width via uniform so the dot stays centered
        self._inner.grid_columnconfigure(0, weight=1, uniform="center")
        self._inner.grid_columnconfigure(1, weight=0)
        self._inner.grid_columnconfigure(2, weight=1, uniform="center")

        self._lbl_time = tk.Label(
            self._inner, text="",
            fg="#777777", bg="#0a0a0a", font=("Consolas", 7),
        )

        self._canvas = tk.Canvas(
            self._inner, width=DOT_SIZE + 2, height=DOT_SIZE + 2,
            bg="#0a0a0a", highlightthickness=0, bd=0,
        )
        self._dot = self._canvas.create_oval(
            1, 1, DOT_SIZE + 1, DOT_SIZE + 1,
            fill=self._rgb_hex(GRAY), outline="",
        )

        self._lbl_name = tk.Label(
            self._inner, text=self.project_name,
            fg="#999999", bg="#0a0a0a", font=("Consolas", 8),
        )

        self.update(data)

    # ------------------------------------------------------------------
    def update(self, data: dict) -> None:
        status = data.get("status", "idle")
        rgb = COLOR_MAP.get(status, GRAY)

        self._prompt_time = data.get("prompt_time", "")
        pt = _format_ts(data.get("prompt_time", ""))
        dt = _format_ts(data.get("done_time", ""))

        if status == "working" or not dt or dt == pt:
            self._ts_str = pt
        else:
            self._ts_str = f"{pt} | {dt}"

        raw = _project_name(data.get("cwd", ""))
        self.project_name = raw
        if self._show_full:
            self._lbl_name.configure(text=raw)
        else:
            self._lbl_name.configure(text=_truncate(raw, 12))
        self._lbl_time.configure(text=self._ts_str)

        self._color_rgb = rgb
        self._blinking = status in ("waiting", "error")
        if not self._blinking:
            self._canvas.itemconfig(self._dot, fill=self._rgb_hex(rgb))

    def set_show_full(self, flag: bool) -> None:
        self._show_full = flag
        if flag:
            self._lbl_name.configure(text=self.project_name)
        else:
            self._lbl_name.configure(text=_truncate(self.project_name, 12))

    def apply_blink(self, on: bool) -> None:
        if not self._blinking:
            return
        color = self._color_rgb if on else OFF
        self._canvas.itemconfig(self._dot, fill=self._rgb_hex(color))

    def show_details(self) -> None:
        self._hide_all()
        self._lbl_time.grid(row=0, column=0, sticky="e", padx=(0, 4))
        self._canvas.grid(row=0, column=1)
        self._lbl_name.grid(row=0, column=2, sticky="w", padx=(4, 0))

    def hide_details(self) -> None:
        self._hide_all()
        self._canvas.grid(row=0, column=1)

    def _hide_all(self) -> None:
        for w in (self._lbl_time, self._canvas, self._lbl_name):
            w.grid_forget()

    @staticmethod
    def _rgb_hex(rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _format_ts(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        utc_time = datetime.fromisoformat(iso_str)
        return utc_time.astimezone(LOCAL_TZ).strftime("%H:%M:%S")
    except Exception:
        return ""


def _project_name(cwd: str) -> str:
    if not cwd:
        return "?"
    return cwd.replace("\\", "/").rstrip("/").split("/")[-1] or cwd


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
