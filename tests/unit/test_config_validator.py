"""Unit tests for ``ireco.config.json`` schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptx_ireco.config.validator import ValidationError, validate_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _good_known() -> dict:
    return {
        "version": 1,
        "doc_types": ["invoice"],
        "io": {"input_dir": "./in", "output_dir": "./out"},
        "invoice": {
            "tenancy": "known",
            "recipients": [
                {
                    "id": "example-buyer",
                    "name": "PŘÍKLADOVÁ a.s.",
                    "ico": "00000019",
                    "dic": "CZ00000019",
                    "extraction": {
                        "depth": "items",
                        "orders": {"source": "local", "path": "./orders/*.json"},
                    },
                }
            ],
        },
    }


def _good_multitenant() -> dict:
    return {
        "version": 1,
        "doc_types": ["invoice"],
        "io": {"input_dir": "./in", "output_dir": "./out"},
        "invoice": {
            "tenancy": "multitenant",
            "extraction": {"depth": "header"},
        },
    }


def _expect_failure(data: dict, *, contains: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_config(data)
    msg = "\n".join(exc_info.value.errors)
    assert contains in msg, f"expected {contains!r} in errors, got:\n{msg}"


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_known_tenancy_passes() -> None:
    validate_config(_good_known())


def test_multitenant_tenancy_passes() -> None:
    validate_config(_good_multitenant())


def test_schema_keyword_is_allowed() -> None:
    data = _good_multitenant()
    data["$schema"] = "https://example/x.json"
    validate_config(data)


def test_example_in_issue_validates() -> None:
    """The example block in issue #002 / ADR-0004 must validate."""
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "ireco_config"
        / "known-3.json"
    )
    validate_config(json.loads(fixture.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def test_version_must_be_one() -> None:
    data = _good_multitenant()
    data["version"] = 2
    _expect_failure(data, contains="unsupported config version")


def test_version_required() -> None:
    data = _good_multitenant()
    del data["version"]
    _expect_failure(data, contains="version: required")


# ---------------------------------------------------------------------------
# doc_types
# ---------------------------------------------------------------------------


def test_doc_types_must_be_nonempty() -> None:
    data = _good_multitenant()
    data["doc_types"] = []
    _expect_failure(data, contains="doc_types")


def test_doc_types_unknown_value_rejected() -> None:
    data = _good_multitenant()
    data["doc_types"] = ["pizza"]
    _expect_failure(data, contains="doc_types[0]")


def test_doc_types_reserved_accepted() -> None:
    """Schema accepts reserved doc types; pipeline rejects them later."""
    data = _good_multitenant()
    data["doc_types"] = ["invoice", "receipt"]
    validate_config(data)


# ---------------------------------------------------------------------------
# io
# ---------------------------------------------------------------------------


def test_io_required() -> None:
    data = _good_multitenant()
    del data["io"]
    _expect_failure(data, contains="io: required")


def test_io_input_dir_required() -> None:
    data = _good_multitenant()
    del data["io"]["input_dir"]
    _expect_failure(data, contains="io.input_dir")


# ---------------------------------------------------------------------------
# invoice tenancy gating
# ---------------------------------------------------------------------------


def test_invoice_required_when_in_doc_types() -> None:
    data = _good_known()
    del data["invoice"]
    _expect_failure(data, contains="invoice: required")


def test_invoice_forbidden_when_not_in_doc_types() -> None:
    data = _good_multitenant()
    data["doc_types"] = ["receipt"]
    _expect_failure(data, contains="invoice")


def test_known_requires_recipients() -> None:
    data = _good_known()
    data["invoice"]["recipients"] = []
    _expect_failure(data, contains="invoice.recipients")


def test_known_forbids_top_level_extraction() -> None:
    data = _good_known()
    data["invoice"]["extraction"] = {"depth": "header"}
    _expect_failure(data, contains="invoice.extraction: forbidden")


def test_multitenant_requires_extraction() -> None:
    data = _good_multitenant()
    del data["invoice"]["extraction"]
    _expect_failure(data, contains="invoice.extraction: required")


def test_multitenant_rejects_recipients() -> None:
    data = _good_multitenant()
    data["invoice"]["recipients"] = [
        {
            "id": "x",
            "name": "X",
            "ico": "12345678",
            "extraction": {"depth": "header"},
        }
    ]
    _expect_failure(data, contains="invoice.recipients")


# ---------------------------------------------------------------------------
# recipient rules
# ---------------------------------------------------------------------------


def test_recipient_ico_must_be_eight_digits() -> None:
    data = _good_known()
    data["invoice"]["recipients"][0]["ico"] = "123"
    _expect_failure(data, contains="invoice.recipients[0].ico: must be 8 digits")


def test_recipient_dic_optional_but_validated() -> None:
    data = _good_known()
    data["invoice"]["recipients"][0]["dic"] = "lowercase"
    _expect_failure(data, contains="invoice.recipients[0].dic")


def test_recipient_id_must_be_kebab() -> None:
    data = _good_known()
    data["invoice"]["recipients"][0]["id"] = "Example_Buyer"
    _expect_failure(data, contains="invoice.recipients[0].id: must be kebab-case")


def test_recipient_id_unique() -> None:
    data = _good_known()
    data["invoice"]["recipients"].append(
        {
            "id": "example-buyer",
            "name": "dup",
            "ico": "11111111",
            "extraction": {"depth": "header"},
        }
    )
    _expect_failure(data, contains="duplicate value 'example-buyer'")


# ---------------------------------------------------------------------------
# extraction.orders rules
# ---------------------------------------------------------------------------


def test_orders_only_when_items() -> None:
    data = _good_known()
    data["invoice"]["recipients"][0]["extraction"] = {
        "depth": "header",
        "orders": {"source": "local", "path": "./orders/*.json"},
    }
    _expect_failure(
        data,
        contains="orders: only allowed when depth is 'items'",
    )


def test_orders_source_must_be_local() -> None:
    data = _good_known()
    data["invoice"]["recipients"][0]["extraction"]["orders"]["source"] = "http"
    _expect_failure(
        data,
        contains="invoice.recipients[0].extraction.orders.source",
    )


# ---------------------------------------------------------------------------
# watcher section (optional, issue #004)
# ---------------------------------------------------------------------------


def test_watcher_section_optional() -> None:
    """Configs without watcher block stay valid."""
    validate_config(_good_multitenant())


def test_watcher_section_defaults_accepted() -> None:
    data = _good_multitenant()
    data["watcher"] = {
        "backend": "local",
        "workers": 1,
        "cooldown_seconds": 1.0,
        "patterns": ["*.pdf"],
        "recursive": True,
    }
    validate_config(data)


def test_watcher_backend_invalid_value_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"backend": "http"}
    _expect_failure(data, contains="watcher.backend: must be one of")


def test_watcher_workers_zero_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"workers": 0}
    _expect_failure(data, contains="watcher.workers")


def test_watcher_workers_negative_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"workers": -1}
    _expect_failure(data, contains="watcher.workers")


def test_watcher_workers_non_int_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"workers": "two"}
    _expect_failure(data, contains="watcher.workers")


def test_watcher_cooldown_negative_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"cooldown_seconds": -0.1}
    _expect_failure(data, contains="watcher.cooldown_seconds")


def test_watcher_patterns_empty_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"patterns": []}
    _expect_failure(data, contains="watcher.patterns")


def test_watcher_recursive_must_be_bool() -> None:
    data = _good_multitenant()
    data["watcher"] = {"recursive": "yes"}
    _expect_failure(data, contains="watcher.recursive")


def test_watcher_unknown_key_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"backend": "local", "extra": "bad"}
    _expect_failure(data, contains="watcher: unknown key 'extra'")


# ---------------------------------------------------------------------------
# watcher.post_process / post_process_options (issue #006)
# ---------------------------------------------------------------------------


def test_watcher_post_process_export_isdoc_accepted() -> None:
    data = _good_multitenant()
    data["watcher"] = {
        "post_process": ["export-isdoc"],
        "post_process_options": {
            "export-isdoc": {
                "format": "isdocx",
                "profile": "standard",
                "allow_incomplete": False,
            }
        },
    }
    validate_config(data)


def test_watcher_post_process_unknown_handler_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"post_process": ["export-xrechnung"]}
    _expect_failure(
        data, contains="watcher.post_process[0]: must be one of ['export-isdoc']"
    )


def test_watcher_post_process_non_string_entry_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {"post_process": [42]}
    _expect_failure(data, contains="watcher.post_process[0]: must be a string")


def test_watcher_post_process_options_invalid_format_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {
        "post_process_options": {"export-isdoc": {"format": "xml"}}
    }
    _expect_failure(
        data,
        contains="watcher.post_process_options.export-isdoc.format: must be one of",
    )


def test_watcher_post_process_options_unknown_handler_rejected() -> None:
    data = _good_multitenant()
    data["watcher"] = {
        "post_process_options": {"export-bogus": {"format": "isdoc"}}
    }
    _expect_failure(
        data,
        contains="watcher.post_process_options: unknown handler 'export-bogus'",
    )


def test_watcher_post_process_must_be_array() -> None:
    data = _good_multitenant()
    data["watcher"] = {"post_process": "export-isdoc"}
    _expect_failure(data, contains="watcher.post_process: must be an array")


# ---------------------------------------------------------------------------
# models section (optional, issue #004)
# ---------------------------------------------------------------------------


def test_models_section_optional() -> None:
    """Configs without models block stay valid."""
    validate_config(_good_multitenant())


def test_models_path_accepted() -> None:
    data = _good_multitenant()
    data["models"] = {"path": "./models"}
    validate_config(data)


def test_models_path_empty_rejected() -> None:
    data = _good_multitenant()
    data["models"] = {"path": ""}
    _expect_failure(data, contains="models.path")


def test_models_path_non_string_rejected() -> None:
    data = _good_multitenant()
    data["models"] = {"path": 42}
    _expect_failure(data, contains="models.path")


def test_models_unknown_key_rejected() -> None:
    data = _good_multitenant()
    data["models"] = {"path": "./m", "extra": "bad"}
    _expect_failure(data, contains="models: unknown key 'extra'")


# ---------------------------------------------------------------------------
# parse.ocr section (issue 007)
# ---------------------------------------------------------------------------


def test_parse_section_optional() -> None:
    validate_config(_good_multitenant())


def test_parse_ocr_minimal_block_accepted() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'enabled': True}}
    validate_config(data)


def test_parse_ocr_full_block_accepted() -> None:
    data = _good_multitenant()
    data['parse'] = {
        'ocr': {
            'enabled': True,
            'language': 'eng+ces',
            'dpi': 400,
            'min_ink_ratio': 0.02,
            'mode': 'printed',
        }
    }
    validate_config(data)


def test_parse_ocr_unknown_key_rejected() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'lang': 'eng'}}
    _expect_failure(data, contains="parse.ocr: unknown key 'lang'")


def test_parse_ocr_min_ink_ratio_out_of_range_rejected() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'min_ink_ratio': 1.5}}
    _expect_failure(data, contains='parse.ocr.min_ink_ratio')


def test_parse_ocr_min_ink_ratio_negative_rejected() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'min_ink_ratio': -0.1}}
    _expect_failure(data, contains='parse.ocr.min_ink_ratio')


def test_parse_ocr_dpi_too_low_rejected() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'dpi': 50}}
    _expect_failure(data, contains='parse.ocr.dpi')


def test_parse_ocr_mode_handwritten_rejected() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'mode': 'handwritten'}}
    _expect_failure(data, contains="parse.ocr.mode")


def test_parse_ocr_enabled_must_be_bool() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'enabled': 'yes'}}
    _expect_failure(data, contains='parse.ocr.enabled')


def test_parse_unknown_top_level_key_rejected() -> None:
    data = _good_multitenant()
    data['parse'] = {'ocr': {'enabled': True}, 'unknown': 1}
    _expect_failure(data, contains="parse: unknown key 'unknown'")

