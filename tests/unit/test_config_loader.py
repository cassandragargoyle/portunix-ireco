"""Unit tests for read/write helpers and ``--from-file`` flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ptx_ireco.config.loader import (
    CONFIG_FILENAME,
    ConfigNotFoundError,
    InvalidConfigError,
    UnsupportedVersionError,
    find_config,
    load_config_dict,
    load_config_file,
    write_config,
)


def _valid() -> dict[str, Any]:
    return {
        "version": 1,
        "doc_types": ["invoice"],
        "io": {"input_dir": "./in", "output_dir": "./out"},
        "invoice": {
            "tenancy": "multitenant",
            "extraction": {"depth": "header"},
        },
    }


def test_find_config_present(tmp_path: Path) -> None:
    target = tmp_path / CONFIG_FILENAME
    target.write_text(json.dumps(_valid()))
    assert find_config(tmp_path) == target


def test_find_config_absent(tmp_path: Path) -> None:
    assert find_config(tmp_path) is None


def test_load_config_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError):
        load_config_file(tmp_path / "missing.json")


def test_load_config_invalid_json(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    target.write_text("{not valid")
    with pytest.raises(InvalidConfigError):
        load_config_file(target)


def test_load_config_unsupported_version(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    bad = _valid()
    bad["version"] = 2
    target.write_text(json.dumps(bad))
    with pytest.raises(UnsupportedVersionError):
        load_config_file(target)


def test_load_config_dict_roundtrip() -> None:
    cfg = load_config_dict(_valid())
    assert cfg["version"] == 1


def test_write_config_atomic(tmp_path: Path) -> None:
    target = tmp_path / CONFIG_FILENAME
    write_config(target, _valid())
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == _valid()
    # No leftover tempfiles.
    leftovers = [p for p in tmp_path.iterdir() if p.name != CONFIG_FILENAME]
    assert leftovers == []


def test_write_config_rejects_invalid(tmp_path: Path) -> None:
    target = tmp_path / CONFIG_FILENAME
    bad = _valid()
    bad["version"] = 999
    with pytest.raises(UnsupportedVersionError):
        write_config(target, bad)
    assert not target.exists()


def test_write_config_overwrite_preserves_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulated crash mid-write must NOT leave a partial file."""
    target = tmp_path / CONFIG_FILENAME
    write_config(target, _valid())
    original_bytes = target.read_bytes()

    # Force os.replace to blow up to simulate a crash after temp write.
    import os as _os

    real_replace = _os.replace

    def boom(src: str | _os.PathLike, dst: str | _os.PathLike) -> None:
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(_os, "replace", boom)

    new_data = _valid()
    new_data["doc_types"] = ["invoice", "receipt"]
    with pytest.raises(RuntimeError):
        write_config(target, new_data)

    monkeypatch.setattr(_os, "replace", real_replace)

    # Original file still intact.
    assert target.read_bytes() == original_bytes
    # No stray tempfiles either.
    leftovers = [p for p in tmp_path.iterdir() if p.name != CONFIG_FILENAME]
    assert leftovers == []
