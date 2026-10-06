"""AC-4: pure API rules of the unit of work (no database)."""

from __future__ import annotations

import uuid
from typing import Annotated, ClassVar

import pytest
from pydantic import BaseModel

from abacus.kernel.classification import classified, restricted_fields, unclassified_fields
from abacus.kernel.uow import DomainEvent, MissingAuditEvent, Ref, Target

HEX = "ab" * 32


class Happened(DomainEvent):
    event_type: ClassVar[str] = "probe.happened"
    probe_id: Annotated[uuid.UUID, classified("internal")]
    label: Annotated[str, classified("public")]


def test_ac4_target_holds_a_type_and_a_string_or_uuid_id() -> None:
    uid = uuid.uuid4()
    assert Target("request_item", uid).type == "request_item"
    assert str(Target("request_item", uid).id) == str(uid)
    assert str(Target("request_item", "123").id) == "123"


def test_ac4_ref_accepts_string_int_and_uuid_fields() -> None:
    assert Ref(version=3, fingerprint=uuid.uuid4(), content_hash=HEX) is not None


def test_ac4_missing_audit_event_is_an_exception() -> None:
    assert issubclass(MissingAuditEvent, Exception)


def test_ac4_domain_event_is_a_pydantic_model() -> None:
    assert issubclass(DomainEvent, BaseModel)


def test_ac4_event_type_is_a_class_variable_not_a_field() -> None:
    assert Happened.event_type == "probe.happened"
    assert "event_type" not in Happened.model_fields
    assert "event_type" not in Happened(probe_id=uuid.uuid4(), label="x").model_dump()


def test_ac4_a_subclass_without_event_type_is_rejected() -> None:
    with pytest.raises((TypeError, AttributeError, ValueError)):

        class NoType(DomainEvent):
            label: Annotated[str, classified("public")]

        NoType(label="x").event_type  # noqa: B018  (the access itself may be what raises)


def test_ac4_event_id_is_a_generated_uuid() -> None:
    event = Happened(probe_id=uuid.uuid4(), label="x")
    assert isinstance(event.event_id, uuid.UUID)


def test_ac4_event_ids_are_unique_per_event_even_for_equal_content() -> None:
    probe_id = uuid.uuid4()
    ids = {Happened(probe_id=probe_id, label="x").event_id for _ in range(50)}
    assert len(ids) == 50


def test_ac4_the_base_event_and_a_proper_subclass_have_only_classified_non_restricted_fields() -> (
    None
):
    for model in (DomainEvent, Happened):
        assert unclassified_fields(model) == []
        assert restricted_fields(model) == []


# --- Target and Ref validation (contract revision 1) ----------------------------------------


@pytest.mark.parametrize("type_", ["request_item", "a", "x_y_z"])
def test_ac4_target_accepts_snake_case_types(type_: str) -> None:
    assert Target(type_, 1).type == type_


@pytest.mark.parametrize("type_", ["", "Request", "1item", "a-b", "a.b", "a b", "_a", "a\n"])
def test_ac4_target_rejects_a_type_that_is_not_lower_snake_case(type_: str) -> None:
    with pytest.raises(ValueError):
        Target(type_, 1)


@pytest.mark.parametrize(
    "id_", [uuid.uuid4(), 7, 0, "12345", "007", str(uuid.uuid4()), str(uuid.uuid4()).upper()]
)
def test_ac4_target_accepts_uuid_int_digit_and_uuid_string_ids(id_: uuid.UUID | int | str) -> None:
    Target("probe", id_)


@pytest.mark.parametrize(
    "id_", ["", "abc", "12a", "1 2", "-1", "p-1", "Acme Ltd", "x" * 40, "\x00"]
)
def test_ac4_target_rejects_ids_that_are_not_uuids_or_digits(id_: str) -> None:
    with pytest.raises(ValueError):
        Target("probe", id_)


@pytest.mark.parametrize("key", ["version", "a", "content_hash", "x" * 40])
def test_ac4_ref_accepts_snake_case_keys(key: str) -> None:
    Ref(**{key: 1})


@pytest.mark.parametrize("key", ["", "Version", "1a", "a-b", "a.b", "a b", "_a", "x" * 41])
def test_ac4_ref_rejects_keys_that_are_not_lower_snake_case_up_to_40_characters(key: str) -> None:
    with pytest.raises(ValueError):
        Ref(**{key: 1})


@pytest.mark.parametrize("value", [3, 0, uuid.uuid4(), HEX])
def test_ac4_ref_accepts_ints_uuids_and_sha256_fingerprints(value: int | uuid.UUID | str) -> None:
    Ref(field=value)


@pytest.mark.parametrize(
    "value",
    [
        "free text",
        "Acme Corp",
        "",
        "received",
        HEX.upper(),
        HEX[:-1],
        HEX + "a",
        "g" * 64,
        1.5,
        None,
        [1],
        {"a": 1},
        True,
    ],
    ids=lambda v: repr(v)[:20],
)
def test_ac4_ref_rejects_free_text_and_other_value_types(value: object) -> None:
    with pytest.raises(ValueError):
        Ref(field=value)  # pyright: ignore[reportArgumentType] -- deliberately invalid values
