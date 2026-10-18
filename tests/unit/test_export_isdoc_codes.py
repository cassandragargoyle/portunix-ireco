"""Unit tests for ptx_ireco.export.isdoc.codes."""

from __future__ import annotations

import pytest

from ptx_ireco.export.isdoc.codes import (
    country_alpha2,
    czech_dic,
    czech_ico,
    decimal2,
    decimal3,
    get_transform,
    iso_currency,
    iso_date,
    list_transforms,
)
from ptx_ireco.export.isdoc.errors import ExportError


class TestDecimal2:
    def test_pass_two_places(self):
        assert decimal2("1234.56") == "1234.56"

    def test_pass_cz_format(self):
        assert decimal2("1 234,56") == "1234.56"

    def test_pass_us_format(self):
        assert decimal2("1,234.56") == "1234.56"

    def test_pass_pads_zeros(self):
        assert decimal2("100") == "100.00"

    def test_fail_garbage(self):
        with pytest.raises(ExportError):
            decimal2("not-a-number")


class TestDecimal3:
    def test_pass_three_places(self):
        assert decimal3("1.5") == "1.500"

    def test_fail_none(self):
        with pytest.raises(ExportError):
            decimal3(None)


class TestIsoDate:
    def test_pass_cz(self):
        assert iso_date("12.05.2026") == "2026-05-12"

    def test_pass_iso(self):
        assert iso_date("2026-05-12") == "2026-05-12"

    def test_fail_garbage(self):
        with pytest.raises(ExportError):
            iso_date("12 May 2026")


class TestIsoCurrency:
    def test_pass_cz_kc(self):
        assert iso_currency("Kč") == "CZK"

    def test_pass_euro_sign(self):
        assert iso_currency("€") == "EUR"

    def test_pass_iso_alpha3(self):
        assert iso_currency("usd") == "USD"

    def test_fail_too_short(self):
        with pytest.raises(ExportError):
            iso_currency("US")


class TestCountryAlpha2:
    def test_pass_alpha2(self):
        assert country_alpha2("CZ") == "CZ"

    def test_pass_czech_name(self):
        assert country_alpha2("Česká republika") == "CZ"

    def test_pass_english(self):
        assert country_alpha2("Czech Republic") == "CZ"

    def test_fail_unknown(self):
        with pytest.raises(ExportError):
            country_alpha2("Atlantis")


class TestCzechIco:
    # 27074358 (Avast Software) — known-valid IČO in CSU registry.
    VALID = "27074358"

    def test_pass_valid_ico(self):
        assert czech_ico(self.VALID) == self.VALID

    def test_fail_wrong_length(self):
        with pytest.raises(ExportError):
            czech_ico("1234567")

    def test_fail_mod11_check(self):
        # 27074359 differs by 1 in the check digit → mod-11 fails.
        with pytest.raises(ExportError):
            czech_ico("27074359")


class TestCzechDic:
    def test_pass_valid(self):
        assert czech_dic("CZ27074358") == "CZ27074358"

    def test_fail_wrong_prefix(self):
        with pytest.raises(ExportError):
            czech_dic("SK27074358")

    def test_fail_short(self):
        with pytest.raises(ExportError):
            czech_dic("CZ123")


class TestRegistry:
    def test_get_transform_known(self):
        fn = get_transform("decimal2")
        assert fn("1") == "1.00"

    def test_get_transform_unknown(self):
        with pytest.raises(ExportError):
            get_transform("nonexistent")

    def test_list_transforms_includes_all(self):
        names = list_transforms()
        for n in (
            "decimal2",
            "decimal3",
            "iso_date",
            "iso_currency",
            "country_alpha2",
            "czech_ico",
            "czech_dic",
        ):
            assert n in names
