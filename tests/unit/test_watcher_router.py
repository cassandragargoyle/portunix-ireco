"""Unit tests for :class:`ptx_ireco.watcher.router.EventRouter`."""

from __future__ import annotations

import json
from pathlib import Path

from ptx_ireco.watcher.events import EventType, WatchEvent
from ptx_ireco.watcher.router import EventRouter


def test_callback_invoked_once_per_event() -> None:
    router = EventRouter()
    seen: list[WatchEvent] = []
    router.on_event(seen.append)
    router.emit_detected(Path("/a.pdf"))
    router.emit_processed(Path("/a.pdf"), metadata={"result_keys": ["x"]})
    router.emit_failed(Path("/a.pdf"), "boom", error_code="WORKER_CRASH")
    assert [e.event_type for e in seen] == [
        EventType.SCAN_DETECTED,
        EventType.SCAN_PROCESSED,
        EventType.SCAN_FAILED,
    ]
    assert seen[2].metadata == {"error": "boom", "error.code": "WORKER_CRASH"}


def test_callback_exception_does_not_break_others() -> None:
    router = EventRouter()

    def _bad(e: WatchEvent) -> None:
        raise RuntimeError("nope")

    good: list[WatchEvent] = []
    router.on_event(_bad)
    router.on_event(good.append)
    router.emit_detected(Path("/x.pdf"))
    assert len(good) == 1


def test_events_log_writes_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    router = EventRouter(events_log=log_path)
    router.emit_detected(Path("/x.pdf"))
    router.emit_processed(Path("/x.pdf"), metadata={"result_keys": ["k"]})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    record0 = json.loads(lines[0])
    assert record0["event"] == "scan.detected"
    assert record0["source"] == "/x.pdf"
    assert record0["metadata"] == {}
    assert record0["ts"].endswith("Z")
    record1 = json.loads(lines[1])
    assert record1["event"] == "scan.processed"
    assert record1["metadata"] == {"result_keys": ["k"]}


def test_events_log_appends_not_truncates(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    log_path.write_text('{"event":"pre-existing","source":"/y.pdf","ts":"0","metadata":{}}\n')

    router = EventRouter(events_log=log_path)
    router.emit_detected(Path("/x.pdf"))

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "pre-existing"
    assert json.loads(lines[1])["event"] == "scan.detected"


def test_events_log_creates_parent_dirs(tmp_path: Path) -> None:
    log_path = tmp_path / "nested" / "deep" / "events.jsonl"
    router = EventRouter(events_log=log_path)
    router.emit_detected(Path("/x.pdf"))
    assert log_path.is_file()


def test_events_log_created_with_mode_0644(tmp_path: Path) -> None:
    """Criterion F: a freshly-created events log is mode 0644."""
    import os
    import stat
    import sys

    log_path = tmp_path / "events.jsonl"
    router = EventRouter(events_log=log_path)
    router.emit_detected(Path("/x.pdf"))
    if sys.platform == "win32":
        return  # POSIX modes don't apply
    mode = stat.S_IMODE(os.stat(log_path).st_mode)
    assert mode == 0o644, f"expected 0o644, got {oct(mode)}"
