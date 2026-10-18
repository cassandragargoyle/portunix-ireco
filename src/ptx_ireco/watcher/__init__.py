"""File-system watcher daemon for ptx-ireco (ADR-0005, issue #004).

Monitors ``io.input_dir`` for new PDFs and dispatches each detected
file to ``ptx-ireco-worker`` via one of three backends:

- ``local`` — direct in-process call to
  :func:`ptx_ireco.worker.api.pipeline.run`.
- ``cli``   — spawn ``ptx-ireco-worker run --file <p> -o <o>``.
- ``grpc``  — reserved; raises :class:`DispatchError`.

Public API mirrors the structure of ``ptx_reco.watcher`` (sibling
project) so cross-project audits stay easy:

- :class:`WatchConfig` — typed configuration dataclass.
- :class:`WatchEvent`, :class:`EventType` — event records.
- :class:`EventRouter` — fan-out to registered callbacks plus optional
  JSONL events log.
- :func:`dispatch`, :class:`PoolDispatcher`, :class:`DispatchError` —
  backends and concurrent dispatch.
- :class:`FileSystemMonitor` — long-running daemon.
"""

from __future__ import annotations

from ptx_ireco.watcher.config import WatchConfig
from ptx_ireco.watcher.dispatcher import DispatchError, PoolDispatcher, dispatch
from ptx_ireco.watcher.events import EventType, WatchEvent
from ptx_ireco.watcher.monitor import FileSystemMonitor
from ptx_ireco.watcher.router import EventRouter

__all__ = [
    "DispatchError",
    "EventRouter",
    "EventType",
    "FileSystemMonitor",
    "PoolDispatcher",
    "WatchConfig",
    "WatchEvent",
    "dispatch",
]
