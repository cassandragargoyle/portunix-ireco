"""Unit tests for the watcher post-process plumbing (issue 006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ptx_ireco.watcher.config import WatchConfig
from ptx_ireco.watcher.post_process import (
    PostProcessError,
    is_valid_handler,
    run_post_process,
)


@pytest.fixture
def fixture_vim() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "export" / "isdoc" / "flowii-FA_26050001.vim.json"


def test_is_valid_handler_known():
    assert is_valid_handler("export-isdoc") is True


def test_is_valid_handler_unknown():
    assert is_valid_handler("export-xrechnung") is False


def test_run_post_process_unknown_handler(tmp_path: Path):
    with pytest.raises(PostProcessError):
        run_post_process(
            handler="export-bogus",
            vim_path=tmp_path / "x.vim.json",
            options={},
            models_path=None,
        )


def test_run_post_process_export_isdoc_succeeds(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    out = tmp_path / "out"
    out.mkdir()
    result = run_post_process(
        handler="export-isdoc",
        vim_path=fixture_vim,
        options={"output_dir": str(out), "profile": "standard", "allow_incomplete": True},
        models_path=repo_root,
    )
    assert any(p.endswith(".isdoc") for p in result["outputs"])


def test_watch_config_loads_post_process_section():
    cfg = WatchConfig.from_dict({
        "version": 1,
        "doc_types": ["invoice"],
        "io": {"input_dir": "/tmp/in", "output_dir": "/tmp/out"},
        "watcher": {
            "post_process": ["export-isdoc"],
            "post_process_options": {
                "export-isdoc": {"format": "isdocx", "profile": "minimal"}
            },
        },
    })
    assert cfg.post_process == ["export-isdoc"]
    assert cfg.post_process_options["export-isdoc"]["format"] == "isdocx"


def test_watch_config_with_overrides_post_process():
    cfg = WatchConfig(post_process=["export-isdoc"])
    overridden = cfg.with_overrides(post_process=[])
    assert overridden.post_process == []
