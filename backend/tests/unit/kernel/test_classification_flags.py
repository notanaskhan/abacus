"""Q-02 AC-19, AC-20 (Q-02-T32; ADR-167 §1): the `tri`, `phi` and `pii_kind` flags beside
ADR-031's four levels, the path helpers and the one masking function.

Any flag forces Restricted: a flag on another level fails when the model is defined (at import).
The flags travel in the field's JSON schema next to the level, so the OpenAPI document carries
them. `tri_paths`, `phi_paths` and `pii_paths` find flagged fields through nested models and
containers. Expectations come from the spec, not the implementation.
"""

from __future__ import annotations

from typing import Annotated, get_args

import pytest
from pydantic import BaseModel, Field

from abacus.kernel.classification import (
    PII_KINDS,
    Classification,
    Flags,
    PiiKind,
    classified,
    flag_errors,
    flags_of,
    mask,
    phi_paths,
    pii_paths,
    tri_paths,
)

NOT_RESTRICTED: tuple[Classification, ...] = ("confidential", "internal", "public")


class _Inner(BaseModel):
    tin: Annotated[str, classified("restricted", pii_kind="tin")]
    note: Annotated[str, classified("internal")] = ""


class _Middle(BaseModel):
    inner: Annotated[_Inner, classified("restricted")]
    inners: Annotated[list[_Inner], classified("restricted")] = []
    by_name: Annotated[dict[str, _Inner | None], classified("restricted")] = {}


class _Outer(BaseModel):
    middle: Annotated[_Middle | None, classified("restricted")] = None
    agi: Annotated[str, classified("restricted", tri=True)] = ""
    diagnosis: Annotated[str, classified("restricted", phi=True)] = ""
    account: Annotated[str, classified("restricted", pii_kind="bank_account")] = ""
    born: Annotated[str, classified("restricted", tri=True, pii_kind="date_of_birth")] = ""


class _Node(BaseModel):
    """Refers to itself: the walk must terminate."""

    tin: Annotated[str, classified("restricted", pii_kind="tin")]
    children: Annotated[list[_Node], classified("restricted")] = []


# --- AC-19: the flags, the schema and import-time enforcement ------------------------------------


def test_ac19_the_initial_pii_kinds_are_tin_bank_account_date_of_birth_and_ip_pin() -> None:
    assert set(get_args(PiiKind)) == {"tin", "bank_account", "date_of_birth", "ip_pin"}
    assert set(PII_KINDS) == set(get_args(PiiKind))


def test_ac19_a_pii_kind_field_carries_the_flag_in_its_json_schema() -> None:
    class Probe(BaseModel):
        tin: Annotated[str, classified("restricted", pii_kind="tin")]

    schema = Probe.model_json_schema()["properties"]["tin"]
    assert schema["cls"] == "restricted"
    assert schema["x-pii-kind"] == "tin"
    assert "x-tri" not in schema and "x-phi" not in schema


def test_ac19_tri_and_phi_are_written_beside_the_level() -> None:
    props = _Outer.model_json_schema()["properties"]
    assert props["agi"]["x-tri"] is True and props["agi"]["cls"] == "restricted"
    assert props["diagnosis"]["x-phi"] is True
    assert props["born"]["x-tri"] is True and props["born"]["x-pii-kind"] == "date_of_birth"


def test_ac19_an_unflagged_field_keeps_adr_031s_tag_unchanged() -> None:
    assert classified("restricted").json_schema_extra == {"cls": "restricted"}


@pytest.mark.parametrize("level", NOT_RESTRICTED)
@pytest.mark.parametrize(
    "flag", [{"tri": True}, {"phi": True}, {"pii_kind": "tin"}, {"pii_kind": "ip_pin"}]
)
def test_ac19_any_flag_on_a_level_other_than_restricted_fails_at_import(
    level: Classification, flag: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="restricted"):

        class Bad(BaseModel):  # pyright: ignore[reportUnusedClass] -- defining it must fail
            x: Annotated[str, classified(level, **flag)]  # pyright: ignore[reportArgumentType] -- parametrised flags


def test_ac19_an_unknown_pii_kind_fails_at_import() -> None:
    with pytest.raises(ValueError, match="pii_kind"):
        classified("restricted", pii_kind="passport")  # pyright: ignore[reportArgumentType] -- deliberately invalid


def test_ac19_flags_of_reads_the_flags_back() -> None:
    assert flags_of(_Outer.model_fields["born"]) == Flags(tri=True, pii_kind="date_of_birth")
    assert flags_of(_Outer.model_fields["middle"]) == Flags()
    assert not Flags()
    assert Flags(phi=True)


def test_ac19_pii_paths_finds_a_nested_flagged_field() -> None:
    assert pii_paths(_Inner, "tin") == ("tin",)
    assert pii_paths(_Outer, "tin") == (
        "middle.inner.tin",
        "middle.inners.tin",
        "middle.by_name.tin",
    )
    assert pii_paths(_Outer, "bank_account") == ("account",)
    assert pii_paths(_Outer, "date_of_birth") == ("born",)
    assert pii_paths(_Outer, "ip_pin") == ()


def test_ac19_tri_and_phi_paths_find_their_fields() -> None:
    assert tri_paths(_Outer) == ("agi", "born")
    assert phi_paths(_Outer) == ("diagnosis",)
    assert tri_paths(_Inner) == ()


def test_ac19_the_helpers_accept_an_instance_and_terminate_on_a_cycle() -> None:
    node = _Node(tin="x", children=[_Node(tin="y")])
    assert pii_paths(node, "tin") == ("tin", "children.tin")
    assert pii_paths(_Node, "tin") == ("tin", "children.tin")


def test_ac19_the_check_refuses_flags_set_around_classified() -> None:
    class Sneaky(BaseModel):
        a: str = Field(json_schema_extra={"cls": "internal", "x-pii-kind": "tin"})
        b: str = Field(json_schema_extra={"cls": "restricted", "x-pii-kind": "passport"})
        c: str = Field(json_schema_extra={"cls": "public", "x-tri": True})
        ok: Annotated[str, classified("restricted", pii_kind="tin")]

    assert sorted(flag_errors(Sneaky)) == ["a", "b", "c"]


# --- AC-20: mask(value, kind) --------------------------------------------------------------------


def test_ac20_a_tin_keeps_its_last_four_digits_only() -> None:
    assert mask("900-45-6789", "tin") == "•••-••-6789"
    assert mask("900456789", "tin") == "•••-••-6789"
    assert mask("90-0456789", "tin") == "•••-••-6789"


def test_ac20_a_tin_with_fewer_than_four_digits_masks_fully() -> None:
    assert mask("12", "tin") == "•••-••-••••"
    assert mask("", "tin") == "•••-••-••••"


def test_ac20_a_bank_number_keeps_its_last_four() -> None:
    assert mask("000000001234", "bank_account") == "••••1234"
    assert mask("12", "bank_account") == "••••"


@pytest.mark.parametrize("kind", ["ip_pin", "date_of_birth"])
@pytest.mark.parametrize("value", ["123456", "1990-01-31", "", "x"])
def test_ac20_ip_pin_and_date_of_birth_mask_fully(kind: PiiKind, value: str) -> None:
    masked = mask(value, kind)
    assert not any(ch.isdigit() for ch in masked)
    assert masked == mask("999999", kind)  # nothing of the value shows, not even its length


def test_ac20_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        mask("1", "passport")  # pyright: ignore[reportArgumentType] -- deliberately invalid


@pytest.mark.parametrize("kind", ["tin", "bank_account", "date_of_birth", "ip_pin"])
def test_ac20_every_kind_has_a_mask_that_hides_all_but_four_digits(kind: PiiKind) -> None:
    masked = mask("900-45-6789", kind)
    assert sum(ch.isdigit() for ch in masked) <= 4
    assert "900" not in masked
