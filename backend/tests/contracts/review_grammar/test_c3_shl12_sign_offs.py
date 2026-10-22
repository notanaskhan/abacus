"""C3 v1 consumer tests (P-04-T09), the SHL-12 a to h shapes: the sign-off modal reads the ladder,
the eligibility checks and the statement from stub 1, signs with the hash it saw, and reads review
notes without their sealed bodies. Each artboard's fields, with their types and classification
tags, and the §8 examples as the doc wrote them (Trial Balance v1, 14 of 14 cells cited)."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from abacus.kernel.classification import Classification
from abacus.kernel.listing import ListPage
from abacus.modules.review.contract import (
    BulkSignOffIn,
    BulkSignOffItemOut,
    BulkSignOffOut,
    CheckCode,
    EligibilityCheckOut,
    ExclusionCode,
    LadderLevelOut,
    Level,
    RaiseReviewNoteIn,
    ReviewNoteDetailOut,
    ReviewNoteEventIn,
    ReviewNoteEventOut,
    ReviewNoteItemOut,
    SignOffEligibilityOut,
    SignOffIn,
    SignOffKind,
    SignOffLadderOut,
    SignOffOut,
    SignOffStatementOut,
    SignOffTargetOut,
)

from ._c3 import conforms, dec, example, level, restricted_anywhere, wire

# artboard -> (model, field, classification) the frame reads. Removing or retagging one fails.
NEEDS: dict[str, list[tuple[type[BaseModel], str, Classification]]] = {
    "a": [
        (SignOffEligibilityOut, "target", "confidential"),
        (SignOffEligibilityOut, "levels_allowed", "internal"),
        (SignOffEligibilityOut, "ladder", "internal"),
        (SignOffEligibilityOut, "checks", "confidential"),
        (SignOffEligibilityOut, "eligible", "internal"),
        (SignOffEligibilityOut, "statement", "internal"),
        (SignOffTargetOut, "label", "confidential"),
        (SignOffTargetOut, "context_label", "confidential"),
        (SignOffTargetOut, "version_no", "internal"),
        (SignOffTargetOut, "content_hash", "internal"),
        (SignOffTargetOut, "cell_count", "internal"),
        (SignOffTargetOut, "citation_count", "internal"),
        (LadderLevelOut, "required", "internal"),
        (LadderLevelOut, "expected_signer_name", "internal"),
        (LadderLevelOut, "latest", "internal"),
        (SignOffOut, "adopted_run_number", "internal"),
        (EligibilityCheckOut, "code", "internal"),
        (EligibilityCheckOut, "result", "internal"),
        (EligibilityCheckOut, "facts", "confidential"),
        (EligibilityCheckOut, "refs", "internal"),
        (SignOffStatementOut, "text", "internal"),
        (SignOffStatementOut, "version", "internal"),
    ],
    "a_prime": [
        (SignOffIn, "seen_hash", "internal"),
        (SignOffIn, "statement_version", "internal"),
        (SignOffOut, "initials", "internal"),
        (SignOffOut, "signed_at", "internal"),
        (SignOffOut, "level", "internal"),
        (SignOffOut, "content_hash", "internal"),
    ],
    "b": [
        (ReviewNoteItemOut, "anchor", "confidential"),
        (ReviewNoteItemOut, "status", "internal"),
        (ReviewNoteItemOut, "raised_by_initials", "internal"),
        (ReviewNoteItemOut, "assignee_user_id", "internal"),
        (ReviewNoteItemOut, "allowed_actions", "internal"),
        # Sealed bodies are Restricted wherever they appear.
        (ReviewNoteDetailOut, "body", "restricted"),
        (ReviewNoteDetailOut, "events", "restricted"),
        (ReviewNoteEventOut, "body", "restricted"),
        (RaiseReviewNoteIn, "body", "restricted"),
        (ReviewNoteEventIn, "body", "restricted"),
    ],
    "c": [(EligibilityCheckOut, "facts", "confidential")],
    "d": [(EligibilityCheckOut, "result", "internal")],
    "e": [
        (SignOffOut, "stale", "internal"),
        (SignOffOut, "signer_name", "internal"),
        (SignOffLadderOut, "levels", "internal"),
        (SignOffLadderOut, "allowed_actions", "internal"),
    ],
    "f": [
        (BulkSignOffIn, "targets", "internal"),
        (BulkSignOffOut, "results", "internal"),
        (BulkSignOffOut, "signed", "internal"),
        (BulkSignOffOut, "excluded", "internal"),
        (BulkSignOffItemOut, "detail", "internal"),
        (BulkSignOffItemOut, "ok", "internal"),
    ],
    "g": [(SignOffEligibilityOut, "levels_allowed", "internal")],
    "h": [(SignOffOut, "kind", "internal"), (EligibilityCheckOut, "facts", "confidential")],
}
CASES = [(a, m, f, c) for a, rows in NEEDS.items() for m, f, c in rows]


@pytest.mark.parametrize(
    ("artboard", "model", "field", "classification"),
    CASES,
    ids=[f"SHL-12{a}-{m.__name__}.{f}" for a, m, f, _c in CASES],
)
def test_shl12_the_frame_reads_its_fields_with_their_tags(
    artboard: str, model: type[BaseModel], field: str, classification: Classification
) -> None:
    assert field in model.model_fields, f"SHL-12 {artboard} needs {model.__name__}.{field}"
    assert level(model, field) == classification


# --- a. Allowed: Trial Balance v1 at L2 ---------------------------------------------------------


def test_shl12a_the_eligibility_example_is_the_wire_shape() -> None:
    body = conforms(SignOffEligibilityOut, example("target", "levels_allowed", "checks"))
    assert body.level == "L2_reviewer" and body.eligible
    assert [c.code for c in body.checks] == [
        "open_review_notes",
        "independence",
        "segregation",
        "all_cited",
        "gate_g4",
    ]
    assert [lv.level for lv in body.ladder] == list(get_args(Level))


def test_shl12a_every_value_cited_14_of_14_cells() -> None:
    body = conforms(SignOffEligibilityOut, example("target", "levels_allowed", "checks"))
    assert body.target.cell_count == 14 and body.target.citation_count == 3
    cited = next(c for c in body.checks if c.code == "all_cited")
    assert cited.result == "pass" and cited.facts == {"cited": 14, "cells": 14}
    assert dec(str(cited.facts["cited"])) == dec(str(body.target.cell_count))
    g4 = next(c for c in body.checks if c.code == "gate_g4")
    assert g4.result == "warn" and [r.type for r in g4.refs] == ["decision_card"]


def test_shl12a_the_l1_is_agent_work_adopted_by_marcus() -> None:
    body = conforms(SignOffEligibilityOut, example("target", "levels_allowed", "checks"))
    l1 = body.ladder[0].latest
    assert l1 is not None and l1.adopted_run_number == 4127 and l1.initials == "MD"
    assert l1.signer_name == "Marcus Delaney" and not l1.stale


# --- a-prime. Signed ----------------------------------------------------------------------------


def test_shl12a_prime_sign_with_the_full_digest_the_signer_saw() -> None:
    request = example("seen_hash", "statement_version")
    # The doc writes the hash as SHL-12 shows it; on the wire it is the full 64-hex digest (§8).
    with pytest.raises(ValidationError):
        SignOffIn.model_validate(wire(request))
    full = {**request, "seen_hash": "sha256:" + "9f4c" + "0" * 56 + "e21a"}
    assert SignOffIn.model_validate(wire(full)).level == "L2_reviewer"


def test_shl12a_prime_the_201_is_one_insert_only_row() -> None:
    row = conforms(SignOffOut, example("signer_name", "stale", "statement_version"))
    assert (row.initials, row.level, row.stale) == ("HL", "L2_reviewer", False)
    l1 = conforms(SignOffEligibilityOut, example("target", "levels_allowed")).ladder[0].latest
    assert l1 is not None
    assert " ".join(f"✓ {s.initials}" for s in (l1, row)) == "✓ MD ✓ HL"


# --- b. Blocked: open notes --------------------------------------------------------------------


def test_shl12b_two_open_notes_and_no_body_in_the_list() -> None:
    page = conforms(ListPage[ReviewNoteItemOut], example("items", "counts", "total_capped"))
    assert page.total == 2 and page.counts == {"open": 2}
    assert [n.anchor.ref for n in page.items if n.anchor] == ["RA!C14", "RA!C22"]
    assert {n.status for n in page.items} == {"open"}
    assert restricted_anywhere(ReviewNoteItemOut) == []


def test_shl12b_c_d_the_blocking_codes() -> None:
    assert {"open_review_notes", "segregation", "independence"} <= set(get_args(CheckCode))
    assert {"open_review_notes", "segregation", "independence_pending"} <= set(
        get_args(ExclusionCode)
    )


# --- e. Stale after change ---------------------------------------------------------------------


def test_shl12e_staleness_is_computed_and_the_change_foots() -> None:
    # §8 SHL-12 e: contributions receivable of $48,600 were added, so net assets are $16,861,000.
    assert dec("16,812,400") + dec("48,600") == dec("16,861,000")
    assert SignOffOut.model_fields["stale"].annotation is bool
    assert (
        TypeAdapter(LadderLevelOut)
        .validate_python(
            {
                "level": "L2_reviewer",
                "required": True,
                "expected_signer_user_id": None,
                "expected_signer_name": None,
                "latest": None,
            }
        )
        .latest
        is None
    )


# --- f. Bulk -----------------------------------------------------------------------------------


def test_shl12f_six_selected_three_signed_three_excluded() -> None:
    targets = [
        {"target_type": "workpaper", "target_id": f"<wp-{n}>", "seen_hash": "sha256:" + "a" * 64}
        for n in range(6)
    ]
    BulkSignOffIn.model_validate(
        wire({"targets": targets, "level": "L2_reviewer", "statement_version": "<statement>"})
    )
    with pytest.raises(ValidationError):  # 1 to 50 targets
        BulkSignOffIn.model_validate(
            wire({"targets": targets * 9, "level": "L2_reviewer", "statement_version": "v"})
        )
    excluded: list[ExclusionCode] = ["incomplete", "open_review_notes", "segregation"]
    results = [
        {
            "target_type": "workpaper",
            "target_id": f"<wp-{n}>",
            "ok": n < 3,
            "sign_off_id": f"<so-{n}>" if n < 3 else None,
            "detail": None if n < 3 else excluded[n - 3],
        }
        for n in range(6)
    ]
    out = BulkSignOffOut.model_validate(wire({"results": results, "signed": 3, "excluded": 3}))
    assert out.signed + out.excluded == len(out.results) == 6


# --- g. EQR viewer; h. Tax final approval ------------------------------------------------------


def test_shl12g_the_eqr_sees_only_l5() -> None:
    assert TypeAdapter(list[Level]).validate_python(["L5_eqr"]) == ["L5_eqr"]
    assert get_args(Level)[-1] == "L5_eqr"


def test_shl12h_final_approval_blocked_by_11_open_issues() -> None:
    assert "final_approval" in get_args(SignOffKind)
    check = EligibilityCheckOut.model_validate(
        {"code": "open_issues", "result": "fail", "facts": {"count": 11}, "refs": []}
    )
    assert check.facts["count"] == 11
