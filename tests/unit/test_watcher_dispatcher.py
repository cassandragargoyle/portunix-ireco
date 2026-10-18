"""Unit tests for :mod:`ptx_ireco.watcher.dispatcher`.

Covers:

- The three dispatch backends with mocked or fake dependencies.
- ``_resolve_worker_command`` rule (sys.executable + -m worker_main).
- :class:`PoolDispatcher` happy path, crash isolation, and clean shutdown.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from ptx_ireco.watcher import dispatcher as disp_mod
from ptx_ireco.watcher.config import WatchConfig
from ptx_ireco.watcher.dispatcher import (
    DispatchError,
    PoolDispatcher,
    _resolve_worker_command,
    _worker_execute,
    dispatch,
)


# ---------------------------------------------------------------------------
# Backend dispatch — local / cli / grpc
# ---------------------------------------------------------------------------


def _cfg_with_outdir(tmp_path: Path, backend: str = "local") -> WatchConfig:
    out = tmp_path / "out"
    return WatchConfig(output_dir=out, backend=backend)


def test_dispatch_grpc_raises(tmp_path: Path) -> None:
    cfg = _cfg_with_outdir(tmp_path, backend="grpc")
    with pytest.raises(DispatchError, match="reserved"):
        dispatch(tmp_path / "x.pdf", cfg)


def test_dispatch_unknown_backend_raises(tmp_path: Path) -> None:
    cfg = _cfg_with_outdir(tmp_path, backend="http")
    with pytest.raises(ValueError, match="Unknown dispatch backend"):
        dispatch(tmp_path / "x.pdf", cfg)


def test_dispatch_local_no_output_dir_raises(tmp_path: Path) -> None:
    cfg = WatchConfig(backend="local")  # no output_dir
    with pytest.raises(DispatchError, match="output_dir is required"):
        dispatch(tmp_path / "x.pdf", cfg)


def test_dispatch_local_calls_worker_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``local`` backend forwards into ``worker.api.pipeline.run``."""
    called: dict[str, Any] = {}

    class _FakeEntity:
        type = "buyer"

    class _FakeResult:
        entities = [_FakeEntity()]
        recipient_id = "fake-recipient"

    def _fake_run(pdf, out, *, models=None, options=None, verbose=False, ocr=None):
        called["pdf"] = Path(pdf)
        called["out"] = Path(out)
        called["models"] = models
        called["ocr"] = ocr
        return _FakeResult()

    from ptx_ireco.worker.api import pipeline as worker_pipeline

    monkeypatch.setattr(worker_pipeline, "run", _fake_run)

    cfg = _cfg_with_outdir(tmp_path, backend="local")
    result = dispatch(tmp_path / "scan.pdf", cfg)

    assert called["pdf"] == tmp_path / "scan.pdf"
    assert called["out"] == tmp_path / "out" / "scan.vim.json"
    assert (tmp_path / "out").is_dir()
    assert result["vim_path"].endswith("scan.vim.json")
    assert result["entities"] == ["buyer"]
    assert result["recipient_id"] == "fake-recipient"


def test_dispatch_local_wraps_extraction_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ptx_ireco.pipeline.extract import ExtractionError
    from ptx_ireco.worker.api import pipeline as worker_pipeline

    def _boom(*args, **kwargs):
        raise ExtractionError("no template found")

    monkeypatch.setattr(worker_pipeline, "run", _boom)
    cfg = _cfg_with_outdir(tmp_path, backend="local")
    with pytest.raises(DispatchError, match="no template found"):
        dispatch(tmp_path / "scan.pdf", cfg)


def test_dispatch_cli_invokes_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``cli`` backend spawns ``ptx-ireco-worker run --file ... -o ...``."""
    captured: dict[str, Any] = {}

    class _Result:
        stdout = json.dumps({"vim_path": "x.vim.json", "entities": []})
        stderr = ""
        returncode = 0

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Result()

    monkeypatch.setattr(disp_mod.subprocess, "run", _fake_run)

    cfg = _cfg_with_outdir(tmp_path, backend="cli")
    result = dispatch(tmp_path / "scan.pdf", cfg)

    cmd = captured["cmd"]
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "ptx_ireco.cli.worker_main"]
    assert "run" in cmd
    assert "--file" in cmd
    assert str(tmp_path / "scan.pdf") in cmd
    assert "-o" in cmd
    assert result["vim_path"] == "x.vim.json"


def test_dispatch_cli_nonzero_exit_becomes_dispatch_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    def _fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=2, cmd=cmd, stderr="boom\n"
        )

    monkeypatch.setattr(disp_mod.subprocess, "run", _fake_run)
    cfg = _cfg_with_outdir(tmp_path, backend="cli")
    with pytest.raises(DispatchError, match="rc=2"):
        dispatch(tmp_path / "scan.pdf", cfg)


def test_dispatch_cli_includes_models_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class _Result:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(disp_mod.subprocess, "run", _fake_run)
    cfg = WatchConfig(
        output_dir=tmp_path / "out",
        backend="cli",
        models_path=Path("/opt/m"),
    )
    dispatch(tmp_path / "scan.pdf", cfg)
    cmd = captured["cmd"]
    assert "--models" in cmd
    assert "/opt/m" in cmd
    # --models is a global flag on ptx-ireco-worker; it MUST precede the
    # subcommand or argparse will reject it as an unrecognized argument.
    assert cmd.index("--models") < cmd.index("run"), (
        f"--models must come before 'run': {cmd}"
    )


# ---------------------------------------------------------------------------
# OCR propagation (issue 007 / G1 + G2)
# ---------------------------------------------------------------------------


def test_dispatch_local_forwards_parse_ocr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``parse_ocr`` from the WatchConfig must reach ``worker.api.pipeline.run``."""
    from ptx_ireco.pipeline.parse import OcrOptions
    from ptx_ireco.worker.api import pipeline as worker_pipeline

    captured: dict[str, Any] = {}

    class _FakeResult:
        entities = []
        recipient_id = None

    def _fake_run(pdf, out, *, models=None, options=None, verbose=False, ocr=None):
        captured["ocr"] = ocr
        return _FakeResult()

    monkeypatch.setattr(worker_pipeline, "run", _fake_run)

    opts = OcrOptions(enabled=True, language="eng+ces", dpi=400)
    cfg = WatchConfig(output_dir=tmp_path / "out", backend="local", parse_ocr=opts)
    dispatch(tmp_path / "scan.pdf", cfg)
    assert captured["ocr"] == opts


def test_dispatch_local_ocr_none_when_config_has_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ptx_ireco.worker.api import pipeline as worker_pipeline

    captured: dict[str, Any] = {}

    class _FakeResult:
        entities = []
        recipient_id = None

    def _fake_run(pdf, out, *, models=None, options=None, verbose=False, ocr=None):
        captured["ocr"] = ocr
        return _FakeResult()

    monkeypatch.setattr(worker_pipeline, "run", _fake_run)
    cfg = WatchConfig(output_dir=tmp_path / "out", backend="local")
    dispatch(tmp_path / "scan.pdf", cfg)
    assert captured["ocr"] is None


def test_dispatch_cli_appends_ocr_flags_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ptx_ireco.pipeline.parse import OcrOptions

    captured: dict[str, Any] = {}

    class _Result:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(disp_mod.subprocess, "run", _fake_run)
    cfg = WatchConfig(
        output_dir=tmp_path / "out",
        backend="cli",
        parse_ocr=OcrOptions(
            enabled=True, language="eng+ces", dpi=450, min_ink_ratio=0.02
        ),
    )
    dispatch(tmp_path / "scan.pdf", cfg)
    cmd = captured["cmd"]
    # Flags are subparser-scoped → must appear after 'run'.
    run_idx = cmd.index("run")
    assert "--ocr" in cmd[run_idx:]
    assert "--ocr-language" in cmd and cmd[cmd.index("--ocr-language") + 1] == "eng+ces"
    assert "--ocr-dpi" in cmd and cmd[cmd.index("--ocr-dpi") + 1] == "450"
    assert "--ocr-min-ink-ratio" in cmd and cmd[cmd.index("--ocr-min-ink-ratio") + 1] == "0.02"
    assert "--ocr-mode" in cmd and cmd[cmd.index("--ocr-mode") + 1] == "printed"


def test_dispatch_cli_uses_no_ocr_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``parse_ocr.enabled=False`` must emit ``--no-ocr`` (explicit override)."""
    from ptx_ireco.pipeline.parse import OcrOptions

    captured: dict[str, Any] = {}

    class _Result:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(disp_mod.subprocess, "run", _fake_run)
    cfg = WatchConfig(
        output_dir=tmp_path / "out",
        backend="cli",
        parse_ocr=OcrOptions(enabled=False),
    )
    dispatch(tmp_path / "scan.pdf", cfg)
    assert "--no-ocr" in captured["cmd"]
    assert "--ocr" not in captured["cmd"]  # bare --ocr must not appear when disabled


def test_dispatch_cli_omits_ocr_flags_when_parse_ocr_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class _Result:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(disp_mod.subprocess, "run", _fake_run)
    cfg = WatchConfig(output_dir=tmp_path / "out", backend="cli", parse_ocr=None)
    dispatch(tmp_path / "scan.pdf", cfg)
    cmd = captured["cmd"]
    assert not any(c.startswith("--ocr") for c in cmd), f"expected no OCR flags in {cmd}"


# ---------------------------------------------------------------------------
# _resolve_worker_command
# ---------------------------------------------------------------------------


def test_resolve_worker_command_prefers_sys_executable() -> None:
    cmd = _resolve_worker_command()
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "ptx_ireco.cli.worker_main"]


# ---------------------------------------------------------------------------
# _worker_execute (module-level → pickleable)
# ---------------------------------------------------------------------------


def test_worker_execute_grpc_returns_error(tmp_path: Path) -> None:
    """``grpc`` backend returns status=error from the pool worker."""
    result = _worker_execute(
        str(tmp_path / "x.pdf"),
        backend="grpc",
        output_dir=str(tmp_path / "out"),
        models_path=None,
        invoice={},
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "DISPATCH_ERROR"


def test_worker_execute_unknown_backend_records_crash(tmp_path: Path) -> None:
    """An unknown backend raises ValueError → caught as WORKER_CRASH."""
    result = _worker_execute(
        str(tmp_path / "x.pdf"),
        backend="http",
        output_dir=str(tmp_path / "out"),
        models_path=None,
        invoice={},
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "WORKER_CRASH"


# ---------------------------------------------------------------------------
# PoolDispatcher — happy path, callbacks, shutdown
# ---------------------------------------------------------------------------


from concurrent.futures import Future


def _make_done_future(fn, args) -> Future:
    """Return a :class:`Future` already completed with ``fn(*args)`` or its exception."""
    fut: Future = Future()
    try:
        fut.set_result(fn(*args))
    except BaseException as exc:  # noqa: BLE001 — mirror real Future
        fut.set_exception(exc)
    return fut


class _InlineExecutor:
    """In-process replacement for :class:`ProcessPoolExecutor`.

    Submits run synchronously on the calling thread and produce real
    :class:`concurrent.futures.Future` instances so ``as_completed``
    works the same as it does in production.
    """

    def __init__(self, max_workers: int) -> None:
        self.max_workers = max_workers
        self.shutdown_called = False
        self.shutdown_wait = None

    def submit(self, fn, *args) -> Future:
        return _make_done_future(fn, args)

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_called = True
        self.shutdown_wait = wait


def test_pool_dispatcher_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pool submits one task per file and collects success results."""
    from ptx_ireco.worker.api import pipeline as worker_pipeline

    class _FakeEntity:
        type = "buyer"

    class _FakeResult:
        entities = [_FakeEntity()]
        recipient_id = None

    monkeypatch.setattr(worker_pipeline, "run", lambda *a, **kw: _FakeResult())

    cfg = WatchConfig(
        output_dir=tmp_path / "out",
        workers=2,
        backend="local",
    )
    results: list[dict] = []
    errors: list[dict] = []
    pool = PoolDispatcher(
        cfg,
        on_result=results.append,
        on_error=errors.append,
        executor_class=lambda max_workers: _InlineExecutor(max_workers),
    )
    pool.submit(tmp_path / "a.pdf")
    pool.submit(tmp_path / "b.pdf")
    pool.shutdown(wait=True)

    assert len(results) == 2
    assert errors == []
    assert all(r["status"] == "success" for r in results)


def test_pool_dispatcher_worker_crash_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A handler crash surfaces as WORKER_CRASH but doesn't kill the pool."""
    from ptx_ireco.worker.api import pipeline as worker_pipeline

    def _crash(*a, **kw):
        raise RuntimeError("simulated worker crash")

    monkeypatch.setattr(worker_pipeline, "run", _crash)

    cfg = WatchConfig(output_dir=tmp_path / "out", workers=2, backend="local")
    captured_errors: list[dict] = []
    pool = PoolDispatcher(
        cfg,
        on_error=captured_errors.append,
        executor_class=lambda max_workers: _InlineExecutor(max_workers),
    )
    pool.submit(tmp_path / "a.pdf")
    pool.submit(tmp_path / "b.pdf")
    pool.shutdown(wait=True)

    assert len(captured_errors) == 2
    assert all(e["status"] == "error" for e in captured_errors)
    # local backend wraps RuntimeError into DispatchError (DISPATCH_ERROR).
    # Either error code is acceptable; both surface as scan.failed downstream.
    assert all(
        e["error"]["code"] in ("DISPATCH_ERROR", "WORKER_CRASH")
        for e in captured_errors
    )


def test_pool_dispatcher_shutdown_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ptx_ireco.worker.api import pipeline as worker_pipeline

    class _R:
        entities = []
        recipient_id = None

    monkeypatch.setattr(worker_pipeline, "run", lambda *a, **kw: _R())

    cfg = WatchConfig(output_dir=tmp_path / "out", workers=2, backend="local")
    executor: list[_InlineExecutor] = []

    def factory(max_workers: int) -> _InlineExecutor:
        ex = _InlineExecutor(max_workers)
        executor.append(ex)
        return ex

    pool = PoolDispatcher(cfg, executor_class=factory)
    pool.submit(tmp_path / "a.pdf")
    pool.shutdown(wait=True)
    assert executor[0].shutdown_called is True
    assert executor[0].shutdown_wait is True
