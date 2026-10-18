"""Unit tests for ``models.path`` resolution in ``ptx-ireco-worker`` (issue #8).

The worker and the watcher must resolve the same ``ireco.config.json``
to the same models root, whichever directory they are started from.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from ptx_ireco.cli.worker_main import _resolve_repo_root
from ptx_ireco.config import resolve_models_path
from ptx_ireco.pipeline.extract import ModelPaths
from ptx_ireco.watcher.config import WatchConfig


@pytest.fixture
def dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Return ``(cfg_path, other)`` with cwd set to ``other`` (not the config dir)."""
    cfgdir = tmp_path / "cfgdir"
    other = tmp_path / "other"
    cfgdir.mkdir()
    other.mkdir()
    monkeypatch.chdir(other)
    return cfgdir / "ireco.config.json", other


# ---------------------------------------------------------------------------
# resolve_models_path (shared rule)
# ---------------------------------------------------------------------------


def test_shared_rule_missing_returns_none(tmp_path: Path) -> None:
    assert resolve_models_path(None, tmp_path / "ireco.config.json") is None
    assert resolve_models_path("", tmp_path / "ireco.config.json") is None


def test_shared_rule_absolute_kept(tmp_path: Path) -> None:
    assert resolve_models_path("/abs/root", tmp_path / "ireco.config.json") == Path("/abs/root")


def test_shared_rule_relative_without_config_stays_relative() -> None:
    assert resolve_models_path("./m", None) == Path("./m")


# ---------------------------------------------------------------------------
# _resolve_repo_root (worker)
# ---------------------------------------------------------------------------


def test_worker_default_root_is_cwd(dirs: tuple[Path, Path]) -> None:
    cfg_path, other = dirs
    root = _resolve_repo_root(Namespace(models=None), {}, cfg_path)
    assert root == other
    assert ModelPaths.default(root).templates == other / "models" / "invoice" / "templates"


def test_worker_no_config_root_is_cwd(dirs: tuple[Path, Path]) -> None:
    _, other = dirs
    assert _resolve_repo_root(Namespace(models=None), None) == other


def test_worker_absolute_models_path(dirs: tuple[Path, Path], tmp_path: Path) -> None:
    cfg_path, _ = dirs
    absolute = tmp_path / "abs-root"
    root = _resolve_repo_root(
        Namespace(models=None), {"models": {"path": str(absolute)}}, cfg_path
    )
    assert root == absolute


def test_worker_relative_models_path_anchored_at_config(dirs: tuple[Path, Path]) -> None:
    cfg_path, _ = dirs
    root = _resolve_repo_root(Namespace(models=None), {"models": {"path": "./m"}}, cfg_path)
    assert root == (cfg_path.parent / "m").resolve()


def test_worker_models_flag_overrides_config_and_stays_cwd_relative(
    dirs: tuple[Path, Path],
) -> None:
    cfg_path, other = dirs
    root = _resolve_repo_root(
        Namespace(models="./flag-root"), {"models": {"path": "./m"}}, cfg_path
    )
    assert root == Path("./flag-root")
    assert root.resolve() == other / "flag-root"


# ---------------------------------------------------------------------------
# Worker / watcher parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["./m", "../shared/models-root", "nested/root"])
def test_worker_and_watcher_agree_on_relative_path(
    dirs: tuple[Path, Path], raw: str
) -> None:
    cfg_path, _ = dirs
    cfg = {"models": {"path": raw}}
    worker_root = _resolve_repo_root(Namespace(models=None), cfg, cfg_path)
    watcher_root = WatchConfig.from_dict(cfg, config_path=cfg_path).models_path
    assert worker_root == watcher_root


# ---------------------------------------------------------------------------
# CLI wiring — ``run`` and ``batch`` pass the config location through
# ---------------------------------------------------------------------------


def _write_config(cfg_path: Path, models_path: str) -> None:
    import json

    cfg_path.write_text(
        json.dumps(
            {
                "version": 1,
                "doc_types": ["invoice"],
                "io": {"input_dir": "./in", "output_dir": "./out"},
                "invoice": {"tenancy": "multitenant", "extraction": {"depth": "header"}},
                "models": {"path": models_path},
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def captured_models(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Replace the pipeline with a stub that records the ``models`` root."""
    from ptx_ireco.cli import worker_main
    from ptx_ireco.pipeline.extract import ExtractionError

    seen: list[Path] = []

    def fake_run(_pdf: Path, _out: Path, *, models: Path, **_kwargs: object) -> None:
        seen.append(Path(models))
        raise ExtractionError("stub")

    monkeypatch.setattr(worker_main.worker_pipeline, "run", fake_run)
    return seen


@pytest.mark.parametrize("verb", ["run", "batch"])
def test_cli_relative_models_path_anchored_at_config(
    dirs: tuple[Path, Path], captured_models: list[Path], verb: str
) -> None:
    from ptx_ireco.cli.worker_main import main

    cfg_path, other = dirs
    _write_config(cfg_path, "./m")
    (other / "a.pdf").write_bytes(b"%PDF-1.4\n")
    if verb == "run":
        argv = ["--config", str(cfg_path), "run", "--file", "a.pdf", "-o", "a.vim.json"]
    else:
        argv = ["--config", str(cfg_path), "batch", "--dir", ".", "-o", "out"]

    main(argv)

    assert captured_models == [(cfg_path.parent / "m").resolve()]
