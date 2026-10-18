"""Unit tests for ptx_ireco.invoice.profile_resolver."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from ptx_ireco.invoice.profile_resolver import (
    ProfileNotFoundError,
    resolve_profile,
)


def _write_profile(dir_: Path, name: str, **payload) -> Path:  # type: ignore[no-untyped-def]
    p = dir_ / f"{name}.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_picks_active_profile(tmp_path: Path) -> None:
    cze = tmp_path / "cze"
    cze.mkdir()
    _write_profile(cze, "old", valid_from="2013-01-01", valid_to="2025-01-01")
    _write_profile(cze, "new", valid_from="2025-01-01", valid_to=None)
    res = resolve_profile("CZE", "2026-05-09", tmp_path)
    assert res.path.name == "new.json"
    assert res.valid_from == date(2025, 1, 1)
    assert res.valid_to is None


def test_picks_historical_profile(tmp_path: Path) -> None:
    cze = tmp_path / "cze"
    cze.mkdir()
    _write_profile(cze, "old", valid_from="2013-01-01", valid_to="2025-01-01")
    _write_profile(cze, "new", valid_from="2025-01-01", valid_to=None)
    res = resolve_profile("CZE", "2020-06-15", tmp_path)
    assert res.path.name == "old.json"


def test_inclusive_lower_exclusive_upper(tmp_path: Path) -> None:
    cze = tmp_path / "cze"
    cze.mkdir()
    _write_profile(cze, "old", valid_from="2013-01-01", valid_to="2025-01-01")
    _write_profile(cze, "new", valid_from="2025-01-01", valid_to=None)
    # 2025-01-01 should hit "new" (lower bound is inclusive).
    assert resolve_profile("CZE", "2025-01-01", tmp_path).path.name == "new.json"
    # 2024-12-31 is still in "old".
    assert resolve_profile("CZE", "2024-12-31", tmp_path).path.name == "old.json"


def test_unknown_country(tmp_path: Path) -> None:
    with pytest.raises(ProfileNotFoundError):
        resolve_profile("XYZ", "2026-05-09", tmp_path)


def test_no_profile_for_date(tmp_path: Path) -> None:
    cze = tmp_path / "cze"
    cze.mkdir()
    _write_profile(cze, "future", valid_from="2030-01-01", valid_to=None)
    with pytest.raises(ProfileNotFoundError):
        resolve_profile("CZE", "2026-05-09", tmp_path)


def test_resolve_against_real_repo(repo_root: Path) -> None:
    profiles = repo_root / "models" / "invoice" / "profiles"
    res = resolve_profile("CZE", date(2026, 5, 9), profiles)
    assert res.country == "CZE"
    assert res.path.name == "invoice-cze-2025-01-01.json"
