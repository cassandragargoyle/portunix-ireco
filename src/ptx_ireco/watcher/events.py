"""Event types emitted by the watcher (issue #004 §F)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(str, Enum):
    """Watcher event types."""

    SCAN_DETECTED = "scan.detected"
    SCAN_PROCESSED = "scan.processed"
    SCAN_FAILED = "scan.failed"
    POSTPROCESS_FAILED = "postprocess.failed"


@dataclass(frozen=True)
class WatchEvent:
    """An event produced by the watcher.

    Attributes:
        event_type: Type of the event.
        source_path: Path to the file that triggered the event.
        timestamp: UTC timestamp when the event occurred.
        metadata: Additional event-specific data
            (e.g. ``result_keys`` for SCAN_PROCESSED, ``error`` /
            ``error.code`` for SCAN_FAILED).
    """

    event_type: EventType
    source_path: Path
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
