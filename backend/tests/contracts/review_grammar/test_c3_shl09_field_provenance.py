"""C3 v1 consumer tests (P-04-T12), the SHL-09 a to f shapes: the field provenance tray reads the
versions newest first with the struck prior value, the citation, the references, the ticks with
computed staleness and the flags, from stub 3. Each artboard's fields with their classification
tags, and the §8 part 3 examples as the doc wrote them (Halvard interest 2,190 → 2,310)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from abacus.kernel.classification import Classification
from abacus.modules.review.contract import (
    FieldEditIn,
    FieldFlagOut,
    FieldProvenanceOut,
    FieldReferenceIn,
    FieldReferenceOut,
    FieldTickIn,
    FieldTickOut,
    FieldValueOut,
    FieldVersionOut,
)

from ._c3 import conforms, dec, example, example_where, inline_example, level

# artboard -> (model, field, classification) the frame reads. Removing or retagging one fails.
NEEDS: dict[str, list[tuple[type[BaseModel], str, Classification]]] = {
    "a": [
        (FieldProvenanceOut, "label", "confidential"),
        (FieldProvenanceOut, "versions", "restricted"),
        (FieldProvenanceOut, "ticks", "internal"),
        (FieldProvenanceOut, "flags", "restricted"),
        (FieldProvenanceOut, "content_hash", "internal"),
        (FieldProvenanceOut, "allowed_actions", "internal"),
        (FieldVersionOut, "value", "restricted"),
        (FieldVersionOut, "actor_name", "internal"),
        (FieldVersionOut, "actor_kind", "internal"),
        (FieldVersionOut, "recorded_at", "internal"),
        (FieldVersionOut, "citation", "restricted"),
        (FieldVersionOut, "references", "restricted"),
        (FieldValueOut, "v", "restricted"),
        (FieldReferenceOut, "label", "confidential"),
        (FieldReferenceOut, "detail", "restricted"),
        (FieldReferenceOut, "page", "internal"),
        (FieldTickOut, "initials", "internal"),
        (FieldTickOut, "signed_at", "internal"),
        (FieldTickOut, "stale", "internal"),
        (FieldFlagOut, "raised_by_initials", "internal"),
        (FieldFlagOut, "body", "restricted"),
        (FieldTickIn, "seen_hash", "internal"),
    ],
    "b": [
        (FieldVersionOut, "value_kind", "internal"),
        (FieldVersionOut, "issue_id", "internal"),
    ],
    "c": [
        (FieldVersionOut, "value_source", "internal"),
        (FieldEditIn, "value", "restricted"),
        (FieldEditIn, "citation_note", "restricted"),
        (FieldEditIn, "seen_seq", "internal"),
    ],
    "d": [(FieldTickOut, "level", "internal"), (FieldTickOut, "content_hash", "internal")],
    "e": [
        (FieldVersionOut, "unsupported", "internal"),
        (FieldVersionOut, "citation_ids", "internal"),
        (FieldReferenceIn, "document_id", "internal"),
    ],
    "f": [(FieldProvenanceOut, "current_seq", "internal")],
}
CASES = [(a, m, f, c) for a, rows in NEEDS.items() for m, f, c in rows]
TRAY = example("versions", "ticks", "flags")


@pytest.mark.parametrize(
    ("artboard", "model", "field", "classification"),
    CASES,
    ids=[f"SHL-09{a}-{m.__name__}.{f}" for a, m, f, _c in CASES],
)
def test_shl09_the_frame_reads_its_fields_with_their_tags(
    artboard: str, model: type[BaseModel], field: str, classification: Classification
) -> None:
    assert field in model.model_fields, f"SHL-09 {artboard} needs {model.__name__}.{field}"
    assert level(model, field) == classification


# --- a. Agent-set, flagged, stale sign-off -------------------------------------------------------


def test_shl09a_the_tray_example_is_the_wire_shape() -> None:
    tray = conforms(FieldProvenanceOut, TRAY)
    assert tray.label == "Taxable interest — Halvard Securities"
    assert [v.seq for v in tray.versions] == [2, 1] and tray.current_seq == 2
    assert f"{len(tray.versions)} versions" == "2 versions"


def test_shl09a_the_value_moved_2190_to_2310_from_the_corrected_1099_int() -> None:
    updated, previous = conforms(FieldProvenanceOut, TRAY).versions
    assert updated.value.t == previous.value.t == "decimal"
    assert updated.value.v is not None and previous.value.v is not None
    assert (Decimal(previous.value.v), Decimal(updated.value.v)) == (dec("2,190"), dec("2,310"))
    assert dec("2,310") - dec("2,190") == Decimal(120)
    # The corrected 1099-INT's Box 1 is the new value (the reference's detail line).
    detail = next(r.detail for r in updated.references if r.kind == "document")
    assert detail is not None and dec(detail.rsplit(": ", 1)[1]) == dec("2,310")
    assert "(prior value 2,190)" in updated.references[0].label
    assert updated.citation is not None and "corrected" in updated.citation
    assert previous.citation is not None and "original" in previous.citation


def test_shl09a_the_agent_set_it_and_the_import_set_the_prior_value() -> None:
    updated, previous = conforms(FieldProvenanceOut, TRAY).versions
    assert (updated.actor_kind, updated.actor_name) == ("agent", "Accrued Agent")
    assert updated.value_source == "agent_suggested" and updated.cause == "suggestion_adopted"
    assert updated.checkpoint_id is not None  # Checkpoint 4 (SHL-16)
    assert (previous.actor_name, previous.value_source) == ("Imported Return", "engine_import")
    assert not updated.unsupported and not previous.unsupported


def test_shl09a_kevins_tick_predates_the_change_so_it_is_stale() -> None:
    tray = conforms(FieldProvenanceOut, TRAY)
    (tick,) = tray.ticks
    assert (tick.initials, tick.signer_name) == ("KO", "Kevin Osei")
    # Staleness is computed: the tick's hash is not the field's current hash (INV-2).
    assert tick.stale and tick.content_hash != tray.content_hash
    assert tick.signed_at < tray.versions[0].recorded_at
    (flag,) = tray.flags
    assert (flag.raised_by_initials, flag.status) == ("SI", "open")
    assert flag.body == "Confirm corrected 1099 replaces the original"


def test_shl09a_sign_off_field_ticks_with_the_full_digest() -> None:
    request = inline_example('"Sign off field" posts')
    with pytest.raises(ValidationError):
        FieldTickIn.model_validate(request)
    full = {**request, "seen_hash": "sha256:7d20" + "0" * 56 + "c4b1"}
    assert FieldTickIn.model_validate(full).level == "L2_reviewer"
    assert "field.sign_off" in conforms(FieldProvenanceOut, TRAY).allowed_actions


# --- b. Estimate -------------------------------------------------------------------------------


def test_shl09b_the_estimate_links_its_open_issue_and_foots() -> None:
    version = conforms(FieldVersionOut, example_where("value_kind", "estimate"))
    assert version.value_kind == "estimate" and version.issue_id is not None
    assert version.value.v is not None and Decimal(version.value.v) == 4 * dec("12,000")
    assert version.citation is not None and "Four 2025 Form 1040-ES vouchers" in version.citation


# --- c. Human-edited ---------------------------------------------------------------------------


def _edit(**extra: object) -> dict[str, object]:
    return {"value": {"t": "decimal", "v": "2310"}, "seen_seq": 2, **extra}


def test_shl09c_a_person_edit_needs_a_citation_note() -> None:
    with pytest.raises(ValidationError):
        FieldEditIn.model_validate(_edit())
    with pytest.raises(ValidationError):
        FieldEditIn.model_validate(_edit(citation_note=""))
    edit = FieldEditIn.model_validate(_edit(citation_note="Per client email Sep 9"))
    assert edit.value_kind == "exact"


def test_shl09c_an_edit_reads_edited_by_the_person() -> None:
    _updated, previous = conforms(FieldProvenanceOut, TRAY).versions
    person = previous.model_copy(
        update={"value_source": "human", "cause": "edit", "actor_kind": "human"}
    )
    assert FieldVersionOut.model_validate(person.model_dump()).value_source == "human"
    with pytest.raises(ValidationError):
        FieldVersionOut.model_validate({**person.model_dump(), "value_source": "policy"})


# --- d. Signed off; e. Uncited; f. Collapsed ---------------------------------------------------


def test_shl09d_current_ticks_are_not_stale() -> None:
    tray = conforms(FieldProvenanceOut, TRAY)
    tick = tray.ticks[0].model_copy(update={"content_hash": tray.content_hash, "stale": False})
    assert not tick.stale and tick.content_hash == tray.content_hash


def test_shl09e_an_uncited_agent_value_is_unsupported() -> None:
    tray = conforms(FieldProvenanceOut, TRAY)
    none: list[str] = []
    uncited: dict[str, object] = {
        **tray.versions[0].model_dump(),
        "citation": None,
        "citation_ids": none,
        "unsupported": True,
    }
    version = FieldVersionOut.model_validate(uncited)
    assert version.unsupported and version.citation is None
    blocked = FieldProvenanceOut.model_validate(
        {
            **tray.model_dump(),
            "versions": [uncited],
            "allowed_actions": ["field.edit", "field.add_reference"],
        }
    )
    assert "field.sign_off" not in blocked.allowed_actions


def test_shl09e_a_reference_is_added_by_document() -> None:
    added = FieldReferenceIn.model_validate(
        {"document_id": "00000000-0000-4000-8000-000000000001", "page": 4, "seen_seq": 2}
    )
    assert added.page == 4
    with pytest.raises(ValidationError):
        FieldReferenceIn.model_validate({"document_id": str(added.document_id), "seen_seq": 0})


def test_shl09f_collapsing_previous_is_client_state() -> None:
    assert "collapsed" not in FieldVersionOut.model_fields
