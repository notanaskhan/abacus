"""P-07-T10 (DEC-52, DEC-223): a TIN normalises to nine digits, masks to its last four and
fingerprints under a per-firm key; nothing schema-shaped carries a plain TIN but the reveal.
Only 9xx fake SSNs here (the repository is public)."""

from __future__ import annotations

import uuid

import pytest

from abacus.api import create_app
from abacus.modules.organisations.contract import MaskedTinOut, TinRevealOut
from abacus.modules.organisations.tin import (
    TinInvalid,
    fingerprint_tin,
    mask_tin,
    normalise_tin,
)

FAKE_SSN = "900-12-3456"


def test_normalise_keeps_nine_digits_and_refuses_anything_else() -> None:
    assert normalise_tin(FAKE_SSN) == "900123456"
    assert normalise_tin("90 0123456") == "900123456"
    for bad in ("90012345", "9001234567", "900-12-345x", "000-00-0000", ""):
        with pytest.raises(TinInvalid) as raised:
            normalise_tin(bad)
        assert bad not in str(raised.value) or bad == ""


def test_mask_shows_the_last_four_only() -> None:
    assert mask_tin("ssn", "3456") == "•••-••-3456"
    assert mask_tin("itin", "3456") == "•••-••-3456"
    assert mask_tin("ein", "0287") == "XX-XXX0287"


def test_fingerprint_is_stable_per_firm_and_differs_across_firms() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    one = fingerprint_tin(a, "900123456")
    assert len(one) == 32
    assert one == fingerprint_tin(a, "900123456")
    assert one != fingerprint_tin(b, "900123456")
    assert one != fingerprint_tin(a, "900123457")
    assert b"900123456" not in one


def test_only_the_reveal_schema_carries_a_plain_tin() -> None:
    """Every OpenAPI schema with a field that can hold nine digits of a TIN is the reveal's: the
    masked form is `^[0-9]{4}$` and Restricted, and no other schema names a TIN value."""
    schemas = create_app().openapi()["components"]["schemas"]
    masked = schemas[MaskedTinOut.__name__]["properties"]["last4"]
    assert masked["anyOf"][0]["pattern"] == "^[0-9]{4}$"
    assert masked["cls"] == "restricted"
    reveal = schemas[TinRevealOut.__name__]["properties"]["value"]
    assert reveal["cls"] == "restricted"
    suspicious = {"tin", "ssn", "ein", "itin", "taxpayer_id", "tin_value", "tin_sealed"}
    carriers = sorted(
        f"{name}.{field}"
        for name, schema in schemas.items()
        for field in schema.get("properties", {})
        if field in suspicious or (field == "value" and name == TinRevealOut.__name__)
    )
    # `tin` on the entity brief is the masked object, never a string.
    for carrier in carriers:
        name, field = carrier.split(".")
        prop = schemas[name]["properties"][field]
        if carrier == f"{TinRevealOut.__name__}.value":
            continue
        refs = [p.get("$ref", "") for p in prop.get("anyOf", [prop])]
        assert any(r.endswith(f"/{MaskedTinOut.__name__}") for r in refs), carrier
