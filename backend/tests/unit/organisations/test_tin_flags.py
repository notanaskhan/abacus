"""Q-02-T32 (ADR-167 §1; DEC-223): P-07-T10's TIN fields carry `pii_kind="tin"`, so the scrubbers
and the gateway find them through `pii_paths`, never through a list of field names."""

from __future__ import annotations

from abacus.kernel.classification import mask, pii_paths
from abacus.modules.organisations.api import mask_tin
from abacus.modules.organisations.contract import (
    ClientEntityBriefOut,
    MaskedTinOut,
    TinRevealOut,
)


def test_ac19_the_revealed_value_and_the_last_four_are_tagged_tin() -> None:
    assert pii_paths(TinRevealOut, "tin") == ("value",)
    assert pii_paths(MaskedTinOut, "tin") == ("last4",)


def test_ac19_a_nested_masked_tin_is_found_from_the_entity() -> None:
    assert pii_paths(ClientEntityBriefOut, "tin") == ("tin.last4",)


def test_ac19_the_schema_carries_the_flag() -> None:
    props = TinRevealOut.model_json_schema()["properties"]
    assert props["value"]["cls"] == "restricted"
    assert props["value"]["x-pii-kind"] == "tin"


def test_ac20_the_ssn_display_form_is_the_kernel_mask() -> None:
    assert mask_tin("ssn", "3456") == mask("3456", "tin") == "•••-••-3456"
