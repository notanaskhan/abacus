"""F-03-T09 (C2): the status registry validates, and the generated files are current."""

from __future__ import annotations

import pytest

from abacus.kernel import _statuses
from abacus_tools.codegen import status_vocabulary as subject


def test_t09_generated_files_are_current() -> None:
    assert subject.main(["--check"]) == 0


def test_t09_derived_codes_are_never_stored() -> None:
    assert "overdue" not in {c.value for c in _statuses.RequestStatus}
    assert _statuses.CHECKS["request"] == (
        "('draft', 'requested', 'uploaded', 'received', 'returned', 'not_applicable')"
    )
    assert len(_statuses.EngagementStatus) == 8


@pytest.mark.parametrize(
    ("yaml_text", "message"),
    [
        (
            "objects: {x: {codes: {a: {label: A, variant: match, terminal: false, "
            "derived: false}}}}",
            "match is never a status",
        ),
        (
            "objects: {x: {codes: {a: {label: In Review, variant: state, terminal: false, "
            "derived: false}}}}",
            "sentence case",
        ),
        ("objects: {x: {codes: {a: {label: A, variant: state}}}}", "missing"),
        (
            "objects: {x: {codes: {A: {label: A, variant: state, terminal: false, "
            "derived: false}}}}",
            "snake_case",
        ),
    ],
)
def test_t09_an_invalid_registry_is_refused(yaml_text: str, message: str) -> None:
    with pytest.raises(subject.RegistryError, match=message):
        subject.parse(yaml_text)
