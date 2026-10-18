"""Unit tests for the OCR plumbing in :mod:`ptx_ireco.pipeline.parse`."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from ptx_ireco.pipeline.parse import (
    OcrOptions,
    _try_register_optional_extractors,
    count_pages_without_text,
)


# ---------------------------------------------------------------------------
# OcrOptions dataclass
# ---------------------------------------------------------------------------


def test_ocr_options_defaults_match_issue_007_spec() -> None:
    opts = OcrOptions()
    assert opts.enabled is False
    assert opts.language == "eng"
    assert opts.dpi == 300
    assert opts.min_ink_ratio == 0.005
    assert opts.mode == "printed"


def test_ocr_options_is_frozen() -> None:
    opts = OcrOptions()
    with pytest.raises(Exception):
        opts.enabled = True  # type: ignore[misc]


def test_ocr_options_replace_works() -> None:
    opts = replace(OcrOptions(), enabled=True, dpi=400)
    assert opts.enabled and opts.dpi == 400 and opts.language == "eng"


# ---------------------------------------------------------------------------
# OcrOptions.from_config_dict
# ---------------------------------------------------------------------------


def test_from_config_dict_none_when_no_cfg() -> None:
    assert OcrOptions.from_config_dict(None) is None
    assert OcrOptions.from_config_dict({}) is None


def test_from_config_dict_none_when_no_parse_section() -> None:
    cfg = {"version": 1, "doc_types": ["invoice"]}
    assert OcrOptions.from_config_dict(cfg) is None


def test_from_config_dict_none_when_no_ocr_section() -> None:
    cfg = {"parse": {}}
    assert OcrOptions.from_config_dict(cfg) is None


def test_from_config_dict_full_block() -> None:
    cfg = {
        "parse": {
            "ocr": {
                "enabled": True,
                "language": "eng+ces",
                "dpi": 400,
                "min_ink_ratio": 0.02,
                "mode": "printed",
            }
        }
    }
    opts = OcrOptions.from_config_dict(cfg)
    assert opts == OcrOptions(
        enabled=True, language="eng+ces", dpi=400, min_ink_ratio=0.02, mode="printed"
    )


def test_from_config_dict_partial_uses_defaults() -> None:
    cfg = {"parse": {"ocr": {"enabled": True}}}
    opts = OcrOptions.from_config_dict(cfg)
    assert opts is not None
    assert opts.enabled is True
    assert opts.language == "eng"
    assert opts.dpi == 300
    assert opts.min_ink_ratio == 0.005
    assert opts.mode == "printed"


# ---------------------------------------------------------------------------
# count_pages_without_text
# ---------------------------------------------------------------------------


def _doc(pages: int, block_pages: list[int]) -> dict[str, Any]:
    return {
        "layers": {
            "physical": {"pages": [{"index": i} for i in range(pages)]},
            "structural": {"blocks": [{"page": p} for p in block_pages]},
        }
    }


def test_count_pages_without_text_all_covered() -> None:
    doc = _doc(pages=3, block_pages=[1, 2, 3])
    assert count_pages_without_text(doc) == (0, 3)


def test_count_pages_without_text_partial_coverage() -> None:
    doc = _doc(pages=3, block_pages=[1, 3])
    assert count_pages_without_text(doc) == (1, 3)


def test_count_pages_without_text_zero_coverage() -> None:
    doc = _doc(pages=2, block_pages=[])
    assert count_pages_without_text(doc) == (2, 2)


def test_count_pages_without_text_no_pages() -> None:
    doc: dict[str, Any] = {"layers": {"physical": {"pages": []}}}
    assert count_pages_without_text(doc) == (0, 0)


def test_count_pages_without_text_missing_layers() -> None:
    assert count_pages_without_text({}) == (0, 0)


def test_count_pages_without_text_ignores_zero_page() -> None:
    """Block with page=0 should not be credited to page 1 et al."""
    doc = _doc(pages=2, block_pages=[0, 0])
    assert count_pages_without_text(doc) == (2, 2)


# ---------------------------------------------------------------------------
# _try_register_optional_extractors — OCR is opt-in
# ---------------------------------------------------------------------------


class _SpyRegistry:
    """Captures the type of every plugin registered."""

    def __init__(self) -> None:
        self.plugins: list[Any] = []

    def register_extractor(self, plugin: Any) -> None:
        self.plugins.append(plugin)


def _plugin_class_names(registry: _SpyRegistry) -> set[str]:
    return {p.__class__.__name__ for p in registry.plugins}


def test_register_optional_extractors_skips_ocr_when_no_options() -> None:
    registry = _SpyRegistry()
    _try_register_optional_extractors(registry, ocr=None)
    assert "OcrExtractorPlugin" not in _plugin_class_names(registry)


def test_register_optional_extractors_skips_ocr_when_disabled() -> None:
    registry = _SpyRegistry()
    _try_register_optional_extractors(registry, ocr=OcrOptions(enabled=False))
    assert "OcrExtractorPlugin" not in _plugin_class_names(registry)


def test_register_optional_extractors_includes_ocr_when_enabled() -> None:
    registry = _SpyRegistry()
    _try_register_optional_extractors(registry, ocr=OcrOptions(enabled=True))
    # OCR plugin should appear; other optional plugins may or may not
    # register depending on ptx_reco's availability, so we only assert
    # the OCR-specific delta.
    names = _plugin_class_names(registry)
    assert "OcrExtractorPlugin" in names, f"expected OcrExtractorPlugin in {names}"


def test_register_optional_extractors_propagates_options() -> None:
    """The registered OCR plugin must carry the values from OcrOptions."""
    registry = _SpyRegistry()
    opts = OcrOptions(enabled=True, language="eng+ces", dpi=450, min_ink_ratio=0.01)
    _try_register_optional_extractors(registry, ocr=opts)
    ocr_plugins = [p for p in registry.plugins if p.__class__.__name__ == "OcrExtractorPlugin"]
    assert len(ocr_plugins) == 1, "OCR plugin should register exactly once"
    plugin = ocr_plugins[0]
    # Access internal fields; INT-024 names them with a leading underscore.
    assert getattr(plugin, "_language") == "eng+ces"
    assert getattr(plugin, "_dpi") == 450
    assert getattr(plugin, "_min_ink_ratio") == 0.01
