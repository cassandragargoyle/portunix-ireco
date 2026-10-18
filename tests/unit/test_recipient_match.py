"""Unit tests for the recipient matcher (DIC > IČO > name)."""

from __future__ import annotations

from ptx_ireco.config.recipient_match import match_recipient

_RECIPIENTS = [
    {
        "id": "example-buyer",
        "name": "PŘÍKLADOVÁ a.s.",
        "ico": "00000019",
        "dic": "CZ00000019",
    },
    {
        "id": "acme-cz",
        "name": "ACME CZ s.r.o.",
        "ico": "12345678",
    },
]


def test_match_by_dic_first() -> None:
    buyer = {"vat_id": "CZ00000019", "tax_id": "00000019", "name": "PŘÍKLADOVÁ a.s."}
    m = match_recipient(buyer, _RECIPIENTS)
    assert m is not None
    assert m.recipient_id == "example-buyer"
    assert m.matched_on == "dic"


def test_match_falls_back_to_ico() -> None:
    buyer = {"tax_id": "12345678"}
    m = match_recipient(buyer, _RECIPIENTS)
    assert m is not None
    assert m.recipient_id == "acme-cz"
    assert m.matched_on == "ico"


def test_match_falls_back_to_name_case_insensitive() -> None:
    buyer = {"name": "příkladová a.s."}
    m = match_recipient(buyer, _RECIPIENTS)
    assert m is not None
    assert m.recipient_id == "example-buyer"
    assert m.matched_on == "name"


def test_no_match_returns_none() -> None:
    buyer = {"vat_id": "CZ99999999"}
    assert match_recipient(buyer, _RECIPIENTS) is None


def test_empty_inputs_return_none() -> None:
    assert match_recipient(None, _RECIPIENTS) is None
    assert match_recipient({}, _RECIPIENTS) is None
    assert match_recipient({"vat_id": "X"}, []) is None
