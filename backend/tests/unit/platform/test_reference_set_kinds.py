"""K-02-T05 (TASK-2208; SPEC-500 AC-19, AC-20): the kind registry and the validators the operator
CLI runs before a draft, without a database."""

from __future__ import annotations

from typing import get_args

import pytest

from abacus.modules.platform import reference_sets
from abacus.modules.platform.reference_sets_contract import (
    ReferenceSetKind,
    StandardsSetRow,
    StandardsSetsPayload,
)


def _payload(*rows: tuple[str, str, str], refs: tuple[str, ...] = ()) -> StandardsSetsPayload:
    return StandardsSetsPayload(
        kind="standards_sets",
        rows=[
            StandardsSetRow(code=code, label=label, standard_refs=list(refs), family=family)  # type: ignore[arg-type] -- a family literal
            for code, label, family in rows
        ],
    )


def test_ac20_one_model_per_kind_and_none_missing() -> None:
    assert set(reference_sets.KINDS) == set(get_args(ReferenceSetKind))


def test_ac20_an_unknown_kind_or_a_mismatched_payload_is_refused() -> None:
    with pytest.raises(reference_sets.ReferenceKindUnknown):
        reference_sets.validate_payload("state_breach_matrix", {"kind": "state_breach_matrix"})
    with pytest.raises(reference_sets.ReferencePayloadInvalid):
        reference_sets.validate_payload("legal_holidays", {"kind": "retention_minimums"})
    with pytest.raises(reference_sets.ReferencePayloadInvalid) as invalid:
        reference_sets.validate_payload("legal_holidays", {"kind": "legal_holidays", "rows": []})
    assert invalid.value.facts["kind"] == "legal_holidays"


def test_ac19_nonissuer_sets_pass() -> None:
    draft = _payload(
        ("gaas-nonissuer", "GAAS for nonissuers", "gaas_nonissuer"),
        ("ssars", "SSARS (non-issuer engagements)", "ssars"),
        ("sqms-1", "SQMS 1", "sqms"),
        refs=("AU-C 230", "AR-C 70", "QM 10"),
    )
    assert reference_sets.validate_standards_sets(draft, {"sqms-1": "sqms"}) is draft


@pytest.mark.parametrize(
    ("code", "label", "refs"),
    [
        ("pcaob", "Auditing standards", ()),
        ("gaas-x", "PCAOB AS", ()),
        ("gaas-y", "Audits", ("AS 2201",)),
        ("gaas-z", "Audits", ("AS1105",)),
        ("issuers", "Audits", ()),
        ("gaas-w", "Issuer audits", ()),
        ("gaas_issuer", "Audits", ()),
    ],
)
def test_ac19_a_pcaob_or_issuer_row_is_refused(
    code: str, label: str, refs: tuple[str, ...]
) -> None:
    with pytest.raises(reference_sets.StandardsSetRefused) as refused:
        reference_sets.validate_standards_sets(
            _payload((code, label, "gaas_nonissuer"), refs=refs), {}
        )
    assert refused.value.facts == {"reason": "excluded_family", "code": code}


def test_ac19_a_dropped_or_moved_code_is_refused() -> None:
    draft = _payload(("ssars", "SSARS", "ssars"))
    with pytest.raises(reference_sets.StandardsSetRefused) as removed:
        reference_sets.validate_standards_sets(draft, {"ssars": "ssars", "sqms-1": "sqms"})
    assert removed.value.facts == {"reason": "code_removed", "code": "sqms-1"}
    with pytest.raises(reference_sets.StandardsSetRefused) as moved:
        reference_sets.validate_standards_sets(draft, {"ssars": "sqms"})
    assert moved.value.facts == {"reason": "family_changed", "code": "ssars"}
