"""AC-4: pure API rules of the unit of work (no database)."""

from __future__ import annotations

import uuid
from typing import Annotated, ClassVar

import pytest
from pydantic import BaseModel

from abacus.kernel.classification import classified, restricted_fields, unclassified_fields
from abacus.kernel.uow import DomainEvent, MissingAuditEvent, Ref, Target


class Happened(DomainEvent):
    event_type: ClassVar[str] = "probe.happened"
    probe_id: Annotated[uuid.UUID, classified("internal")]
    label: Annotated[str, classified("public")]


def test_ac4_target_holds_a_type_and_a_string_or_uuid_id() -> None:
    uid = uuid.uuid4()
    assert Target("request_item", uid).type == "request_item"
    assert str(Target("request_item", uid).id) == str(uid)
    assert str(Target("request_item", "abc").id) == "abc"


def test_ac4_ref_accepts_string_int_and_uuid_fields() -> None:
    assert Ref(version=3, fingerprint=uuid.uuid4(), state="received") is not None


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
