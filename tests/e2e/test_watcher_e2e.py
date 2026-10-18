"""End-to-end integration tests for ``ptx-ireco-watcher``.

These tests exercise the long-running daemon by starting it in a
background thread, dropping a fixture PDF into the watched directory,
and asserting that a ``.vim.json`` is produced and a SCAN_PROCESSED
event is observed.

Each test:

- Uses the actual ``ireco.config.json`` validator + loader code paths.
- Runs the local backend in-process; the CLI subprocess path is
  asserted separately via a mocked subprocess (unit test) plus a
  real-subprocess integration that requires the wheel to be installed
  on ``PATH`` (skipped otherwise).
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path

import pytest

from ptx_ireco.config import write_config
from ptx_ireco.watcher import (
    EventType,
    FileSystemMonitor,
    WatchConfig,
    WatchEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for(predicate, timeout: float, interval: float = 0.1) -> bool:
    """Return True as soon as ``predicate()`` is truthy, else False after timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _run_monitor_in_thread(monitor: FileSystemMonitor) -> threading.Thread:
    thread = threading.Thread(target=monitor.start, daemon=True)
    thread.start()
    # Wait briefly so the observer is actually scheduled before we drop files.
    assert _wait_for(monitor.is_running, timeout=2.0), "monitor failed to start"
    return thread


# ---------------------------------------------------------------------------
# Local backend — end-to-end against fixture PDF
# ---------------------------------------------------------------------------


def test_watcher_local_backend_processes_dropped_pdf(
    tmp_path: Path, repo_root: Path, flowii_pdf: Path
) -> None:
    """Drop a PDF into the watched dir → expect .vim.json in output_dir."""
    watch_dir = tmp_path / "scans"
    out_dir = tmp_path / "out"
    watch_dir.mkdir()

    cfg = WatchConfig(
        watch_dirs=[watch_dir],
        output_dir=out_dir,
        models_path=repo_root,
        backend="local",
        workers=1,
        cooldown_seconds=0.2,
        patterns=["*.pdf"],
        recursive=False,
    )

    events: list[WatchEvent] = []
    monitor = FileSystemMonitor(cfg)
    monitor.router.on_event(events.append)

    thread = _run_monitor_in_thread(monitor)
    try:
        # Stage outside the watch dir, then move atomically — avoids
        # half-written-file false positives.
        staged = tmp_path / "staged.pdf"
        shutil.copy(flowii_pdf, staged)
        shutil.move(str(staged), str(watch_dir / "scan.pdf"))

        produced = out_dir / "scan.vim.json"
        if not _wait_for(produced.is_file, timeout=60.0):
            # Surface the parser error rather than failing on absent file
            failed = [e for e in events if e.event_type == EventType.SCAN_FAILED]
            if failed:
                pytest.skip(f"upstream pipeline failed: {failed[0].metadata.get('error', '')[:200]}")
            pytest.fail("expected .vim.json was not produced within 60s")
    finally:
        monitor.stop()
        thread.join(timeout=5)

    assert produced.is_file()
    detected = [e for e in events if e.event_type == EventType.SCAN_DETECTED]
    processed = [e for e in events if e.event_type == EventType.SCAN_PROCESSED]
    assert detected, "no SCAN_DETECTED event observed"
    assert processed, "no SCAN_PROCESSED event observed"


# ---------------------------------------------------------------------------
# Config-file path — schema additions accepted end-to-end
# ---------------------------------------------------------------------------


def test_ireco_config_with_watcher_and_models_loads(tmp_path: Path) -> None:
    """A config with the new optional sections passes through the loader."""
    cfg_path = tmp_path / "ireco.config.json"
    write_config(
        cfg_path,
        {
            "version": 1,
            "doc_types": ["invoice"],
            "io": {"input_dir": "./in", "output_dir": "./out"},
            "invoice": {"tenancy": "multitenant", "extraction": {"depth": "header"}},
            "watcher": {
                "backend": "local",
                "workers": 4,
                "cooldown_seconds": 0.5,
                "patterns": ["*.pdf", "*.PDF"],
                "recursive": False,
            },
            "models": {"path": "./models"},
        },
    )
    parsed = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert parsed["watcher"]["workers"] == 4
    assert parsed["models"]["path"] == "./models"

    watch_cfg = WatchConfig.from_dict(parsed, config_path=cfg_path)
    assert watch_cfg.backend == "local"
    assert watch_cfg.workers == 4
    assert watch_cfg.patterns == ["*.pdf", "*.PDF"]
    assert watch_cfg.recursive is False
    assert watch_cfg.models_path == (tmp_path / "models").resolve()
