"""EventRouter — fan-out watcher events to callbacks + optional JSONL log."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from ptx_ireco.watcher.events import EventType, WatchEvent

logger = logging.getLogger(__name__)

EventCallback = Callable[[WatchEvent], None]


class EventRouter:
    """Route :class:`WatchEvent` instances to registered callbacks.

    When ``events_log`` is configured, each emitted event is also
    written as one JSON line (UTF-8, appended). The file is created
    with default permissions and is **not** truncated on restart.

    Attributes:
        events_log: Optional path receiving JSON-lines event records.
    """

    def __init__(self, events_log: Path | None = None) -> None:
        self.events_log = Path(events_log) if events_log else None
        self._callbacks: list[EventCallback] = []

    def on_event(self, callback: EventCallback) -> None:
        """Register a callback invoked for every emitted event."""
        self._callbacks.append(callback)

    def emit(self, event: WatchEvent) -> None:
        """Broadcast ``event`` to all callbacks and write the JSONL line."""
        logger.debug("Event: %s %s", event.event_type.value, event.source_path)
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                logger.exception("Callback error for %s", event.event_type.value)
        if self.events_log is not None:
            self._write_jsonl(event)

    def emit_detected(self, source_path: Path) -> None:
        """Emit a :attr:`EventType.SCAN_DETECTED` event."""
        self.emit(WatchEvent(event_type=EventType.SCAN_DETECTED, source_path=source_path))

    def emit_processed(
        self, source_path: Path, metadata: dict[str, Any] | None = None
    ) -> None:
        """Emit a :attr:`EventType.SCAN_PROCESSED` event."""
        self.emit(
            WatchEvent(
                event_type=EventType.SCAN_PROCESSED,
                source_path=source_path,
                metadata=dict(metadata) if metadata else {},
            )
        )

    def emit_failed(
        self,
        source_path: Path,
        error: str,
        *,
        error_code: str | None = None,
    ) -> None:
        """Emit a :attr:`EventType.SCAN_FAILED` event."""
        metadata: dict[str, Any] = {"error": error}
        if error_code:
            metadata["error.code"] = error_code
        self.emit(
            WatchEvent(
                event_type=EventType.SCAN_FAILED,
                source_path=source_path,
                metadata=metadata,
            )
        )

    def emit_postprocess_failed(
        self,
        source_path: Path,
        handler: str,
        error: str,
        *,
        error_code: str | None = None,
    ) -> None:
        """Emit :attr:`EventType.POSTPROCESS_FAILED` (issue 006)."""
        metadata: dict[str, Any] = {"handler": handler, "error": error}
        if error_code:
            metadata["error.code"] = error_code
        self.emit(
            WatchEvent(
                event_type=EventType.POSTPROCESS_FAILED,
                source_path=source_path,
                metadata=metadata,
            )
        )

    def _write_jsonl(self, event: WatchEvent) -> None:
        """Append ``event`` to :attr:`events_log` as a JSON line."""
        try:
            target: Path = self.events_log  # type: ignore[assignment]
            target.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(
                {
                    "event": event.event_type.value,
                    "source": str(event.source_path),
                    "ts": event.timestamp.isoformat().replace("+00:00", "Z"),
                    "metadata": event.metadata,
                },
                ensure_ascii=False,
            )
            # Per issue #004 criterion F: file created with mode 0644. open()
            # alone would honor umask (often 0664); enforce 0644 explicitly.
            new_file = not target.exists()
            with open(target, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            if new_file:
                try:
                    os.chmod(target, 0o644)
                except OSError:
                    # Best-effort — Windows / unusual filesystems may ignore.
                    pass
        except OSError:
            logger.exception("Failed to append to events log %s", self.events_log)
