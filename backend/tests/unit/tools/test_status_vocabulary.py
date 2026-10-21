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


# F-05-T12: every one of the handoff's 144 status words is mapped to a registry code or retired.
_ONE_OBJECT = (
    "objects: {x: {codes: {a: {label: A, variant: state, terminal: false, derived: false}}}}\n"
)


def _handoff(body: str) -> str:
    return _ONE_OBJECT + "handoff_words:\n  Thing:\n" + body


def test_t12_the_handoff_words_are_all_accounted_for() -> None:
    source = subject.SOURCE.read_text(encoding="utf-8")
    words = subject.parse_handoff(source, subject.parse(source))
    assert len(words) == subject.HANDOFF_OBJECT_COUNT
    assert sum(len(w) for w in words.values()) == subject.HANDOFF_WORD_COUNT
    retired = [w for entries in words.values() for w in entries.values() if "retired" in w]
    assert retired
    assert all(str(w["reason"]).strip() for w in retired)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("    W: {object: x, code: nope}\n", "is not in the registry"),
        ("    W: {object: nope, code: a}\n", "is not in the registry"),
        ("    W: {status: false}\n", "gives its reason"),
        ("    W: {status: false, reason: r, replacement: x.nope}\n", "is not a code"),
        ("    W: {object: x, code: a}\n", "expected 21 and 144"),
    ],
)
def test_t12_a_handoff_word_without_a_home_is_refused(body: str, message: str) -> None:
    source = _handoff(body)
    with pytest.raises(subject.RegistryError, match=message):
        subject.parse_handoff(source, subject.parse(source))


def test_t12_a_retired_code_names_its_replacements() -> None:
    source = _ONE_OBJECT + "retired:\n  x.old: {replacement: [x.a]}\n"
    assert subject.parse_retired(source) == {"x.old": {"replacement": ["x.a"]}}
    with pytest.raises(subject.RegistryError, match="is a list"):
        subject.parse_retired(_ONE_OBJECT + "retired:\n  x.old: {replacement: x.a}\n")
    assert len(subject.parse_retired(subject.SOURCE.read_text(encoding="utf-8"))) > 10
