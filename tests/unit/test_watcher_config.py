"""Unit tests for :class:`ptx_ireco.watcher.config.WatchConfig`."""

from __future__ import annotations

from pathlib import Path

from ptx_ireco.config.schema import (
    WATCHER_DEFAULT_BACKEND,
    WATCHER_DEFAULT_COOLDOWN_SECONDS,
    WATCHER_DEFAULT_PATTERNS,
    WATCHER_DEFAULT_RECURSIVE,
    WATCHER_DEFAULT_WORKERS,
)
from ptx_ireco.watcher.config import WatchConfig


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_construction() -> None:
    cfg = WatchConfig()
    assert cfg.backend == WATCHER_DEFAULT_BACKEND
    assert cfg.workers == WATCHER_DEFAULT_WORKERS
    assert cfg.cooldown_seconds == WATCHER_DEFAULT_COOLDOWN_SECONDS
    assert cfg.patterns == list(WATCHER_DEFAULT_PATTERNS)
    assert cfg.recursive is WATCHER_DEFAULT_RECURSIVE
    assert cfg.watch_dirs == []
    assert cfg.output_dir is None
    assert cfg.models_path is None
    assert cfg.events_log is None


def test_from_dict_none_returns_defaults() -> None:
    cfg = WatchConfig.from_dict(None)
    assert cfg.backend == "local"
    assert cfg.workers == 1
    assert cfg.patterns == ["*.pdf"]


def test_from_dict_empty_returns_defaults() -> None:
    cfg = WatchConfig.from_dict({})
    assert cfg.watch_dirs == []
    assert cfg.output_dir is None


# ---------------------------------------------------------------------------
# from_dict — io + watcher + models
# ---------------------------------------------------------------------------


def test_from_dict_picks_io_paths() -> None:
    cfg = WatchConfig.from_dict(
        {
            "io": {"input_dir": "/scans", "output_dir": "/out"},
        }
    )
    assert cfg.watch_dirs == [Path("/scans")]
    assert cfg.output_dir == Path("/out")


def test_from_dict_picks_watcher_block() -> None:
    cfg = WatchConfig.from_dict(
        {
            "io": {"input_dir": "/scans", "output_dir": "/out"},
            "watcher": {
                "backend": "cli",
                "workers": 4,
                "cooldown_seconds": 0.5,
                "patterns": ["*.pdf", "*.PDF"],
                "recursive": False,
            },
        }
    )
    assert cfg.backend == "cli"
    assert cfg.workers == 4
    assert cfg.cooldown_seconds == 0.5
    assert cfg.patterns == ["*.pdf", "*.PDF"]
    assert cfg.recursive is False


def test_from_dict_models_absolute_path() -> None:
    cfg = WatchConfig.from_dict({"models": {"path": "/abs/models"}})
    assert cfg.models_path == Path("/abs/models")


def test_from_dict_models_relative_anchored_at_config(tmp_path: Path) -> None:
    """Relative ``models.path`` resolves against the config file directory."""
    cfg_path = tmp_path / "ireco.config.json"
    cfg = WatchConfig.from_dict({"models": {"path": "./m"}}, config_path=cfg_path)
    assert cfg.models_path == (tmp_path / "m").resolve()


def test_from_dict_models_relative_without_config_stays_relative() -> None:
    cfg = WatchConfig.from_dict({"models": {"path": "./m"}})
    assert cfg.models_path == Path("./m")


def test_from_dict_captures_invoice_snapshot() -> None:
    cfg = WatchConfig.from_dict(
        {
            "invoice": {
                "tenancy": "known",
                "recipients": [{"id": "x", "name": "X", "ico": "00000000"}],
            }
        }
    )
    assert cfg.invoice["tenancy"] == "known"
    assert cfg.invoice["recipients"][0]["id"] == "x"


# ---------------------------------------------------------------------------
# with_overrides
# ---------------------------------------------------------------------------


def test_with_overrides_replaces_listed_fields_only() -> None:
    base = WatchConfig(
        watch_dirs=[Path("/a")],
        output_dir=Path("/o"),
        backend="local",
        workers=1,
        patterns=["*.pdf"],
        recursive=True,
    )
    updated = base.with_overrides(workers=4, recursive=False, patterns=["*.PDF"])
    assert updated.workers == 4
    assert updated.recursive is False
    assert updated.patterns == ["*.PDF"]
    # untouched
    assert updated.watch_dirs == [Path("/a")]
    assert updated.output_dir == Path("/o")
    assert updated.backend == "local"


def test_with_overrides_none_means_keep() -> None:
    base = WatchConfig(workers=4, recursive=False)
    same = base.with_overrides()
    assert same.workers == 4
    assert same.recursive is False


# ---------------------------------------------------------------------------
# parse.ocr propagation (issue 007 / G1)
# ---------------------------------------------------------------------------


def test_from_dict_absent_parse_ocr_yields_none() -> None:
    cfg = WatchConfig.from_dict(
        {
            "io": {"input_dir": "./in", "output_dir": "./out"},
            "invoice": {"tenancy": "multitenant", "extraction": {"depth": "header"}},
        }
    )
    assert cfg.parse_ocr is None


def test_from_dict_loads_parse_ocr_block() -> None:
    from ptx_ireco.pipeline.parse import OcrOptions

    cfg = WatchConfig.from_dict(
        {
            "io": {"input_dir": "./in", "output_dir": "./out"},
            "parse": {
                "ocr": {
                    "enabled": True,
                    "language": "eng+ces",
                    "dpi": 400,
                    "min_ink_ratio": 0.02,
                }
            },
        }
    )
    assert cfg.parse_ocr == OcrOptions(
        enabled=True, language="eng+ces", dpi=400, min_ink_ratio=0.02, mode="printed"
    )


def test_with_overrides_preserves_parse_ocr_by_default() -> None:
    from ptx_ireco.pipeline.parse import OcrOptions

    base = WatchConfig(parse_ocr=OcrOptions(enabled=True, dpi=400))
    same = base.with_overrides(workers=2)
    assert same.parse_ocr == base.parse_ocr


def test_with_overrides_can_replace_parse_ocr() -> None:
    from ptx_ireco.pipeline.parse import OcrOptions

    base = WatchConfig(parse_ocr=OcrOptions(enabled=True, dpi=300))
    updated = base.with_overrides(parse_ocr=OcrOptions(enabled=True, dpi=600))
    assert updated.parse_ocr is not None and updated.parse_ocr.dpi == 600


def test_from_dict_models_absent_yields_none(tmp_path: Path) -> None:
    """Without ``models.path`` the watcher leaves the root to the worker (cwd)."""
    cfg = WatchConfig.from_dict({}, config_path=tmp_path / "ireco.config.json")
    assert cfg.models_path is None


def test_from_dict_models_relative_ignores_cwd(tmp_path: Path, monkeypatch) -> None:
    """Issue #8: anchoring does not depend on the directory the watcher runs from."""
    cfgdir = tmp_path / "cfgdir"
    other = tmp_path / "other"
    cfgdir.mkdir()
    other.mkdir()
    monkeypatch.chdir(other)
    cfg = WatchConfig.from_dict(
        {"models": {"path": "./m"}}, config_path=cfgdir / "ireco.config.json"
    )
    assert cfg.models_path == (cfgdir / "m").resolve()
