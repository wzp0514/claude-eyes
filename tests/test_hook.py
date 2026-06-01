"""Tests for hook event → status mapping."""
import json

from claude_eyes import hook


def test_all_mapped_events():
    assert hook.EVENT_STATUS["UserPromptSubmit"] == "working"
    assert hook.EVENT_STATUS["PostToolUse"] == "working"
    assert hook.EVENT_STATUS["PermissionRequest"] == "waiting"
    assert hook.EVENT_STATUS["Stop"] == "idle"
    assert hook.EVENT_STATUS["SessionStart"] == "idle"
    assert hook.EVENT_STATUS["SessionEnd"] == "closed"
    assert hook.EVENT_STATUS["PostToolUseFailure"] == "error"
    assert hook.EVENT_STATUS["PreToolUse"] == "working"
    assert hook.EVENT_STATUS["PreCompact"] == "working"
    assert hook.EVENT_STATUS["SubagentStop"] == "working"


def test_hook_writes_file(monkeypatch, tmp_path):
    status_dir = tmp_path / "status"
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(hook, "STATUS_DIR", status_dir)
    monkeypatch.setattr(hook, "LOG_DIR", logs_dir)

    result = hook.handle(json.dumps({
        "hook_event_name": "PostToolUse",
        "session_id": "sid-001",
        "tool_name": "Bash",
        "cwd": "/tmp",
    }))

    assert result["status"] == "working"
    assert result["session_id"] == "sid-001"
    assert "prompt_time" in result
    assert "done_time" in result
    assert (status_dir / "sid-001.json").exists()
    assert len((logs_dir / "history.jsonl").read_text().strip().split("\n")) == 1


def test_hook_empty_stdin_skipped(monkeypatch, tmp_path):
    status_dir = tmp_path / "status"
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(hook, "STATUS_DIR", status_dir)
    monkeypatch.setattr(hook, "LOG_DIR", logs_dir)

    result = hook.handle("")

    assert result["status"] == "skipped"
    assert not list(status_dir.glob("*.json"))


def test_hook_unknown_session_skipped(monkeypatch, tmp_path):
    status_dir = tmp_path / "status"
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(hook, "STATUS_DIR", status_dir)
    monkeypatch.setattr(hook, "LOG_DIR", logs_dir)

    result = hook.handle(json.dumps({
        "hook_event_name": "Stop",
        "session_id": "unknown",
    }))

    assert result["status"] == "skipped"
    assert not list(status_dir.glob("*.json"))


def test_hook_permission_request(monkeypatch, tmp_path):
    status_dir = tmp_path / "status"
    monkeypatch.setattr(hook, "STATUS_DIR", status_dir)
    monkeypatch.setattr(hook, "LOG_DIR", tmp_path / "logs")

    result = hook.handle(json.dumps({
        "hook_event_name": "PermissionRequest",
        "session_id": "sid-002",
        "tool_name": "Write",
    }))

    assert result["status"] == "waiting"


def test_hook_post_tool_use_failure(monkeypatch, tmp_path):
    status_dir = tmp_path / "status"
    monkeypatch.setattr(hook, "STATUS_DIR", status_dir)
    monkeypatch.setattr(hook, "LOG_DIR", tmp_path / "logs")

    result = hook.handle(json.dumps({
        "hook_event_name": "PostToolUseFailure",
        "session_id": "sid-003",
        "tool_name": "Bash",
    }))

    assert result["status"] == "error"
