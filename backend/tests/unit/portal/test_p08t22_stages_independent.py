# ac-test-author: ayushkbhatia
"""P-08-T22 (ADR-078), for P-08-T12: the client stage projection is exhaustive over the status
registry and never returns a firm status word.

Written from the T12 row's acceptance ("every registry code of the four work-item kinds maps to
one stage, the Feld 1040 projects to Review and Granite Peak to Statements review, and no firm
status word can be returned"), POR-02's stage trackers (a: 1040, d: close, g: audit, h: SOC 2),
the contract's pill and stage code sets (`docs/contracts/portal-identity.md` §3) and DEC-209's
table, through the module's one public function `client_view(kind, code)`. The registry is read
from `docs/product/status-vocabulary.yaml` itself, not from the generated enums the projection
imports, so a code added to the registry and not to the projection fails here. Derived chips,
never stored, are outside the projection (see `ALL`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
import yaml

from abacus.modules.portal.stages import client_view

REGISTRY: Final = Path(__file__).parents[4] / "docs" / "product" / "status-vocabulary.yaml"
# The four work-item objects (SOC 2 runs on the audit engagement's codes, DEC-209).
OBJECT_OF: Final = {
    "return_1040": "return",
    "return_entity": "return",
    "close": "close",
    "audit": "audit_engagement",
    "soc2": "audit_engagement",
}
# POR-02's trackers, in order (a, d, g, h); an entity return has no Form 8879 stage (DEC-209).
TRACKER: Final = {
    "return_1040": ("gather_documents", "prepare", "review", "sign_form_8879", "file"),
    "return_entity": ("gather_documents", "prepare", "review", "file"),
    "close": ("requests", "reconcile", "review", "statements"),
    "audit": ("planning", "fieldwork", "statements_review", "report"),
    "soc2": ("scoping", "system_description", "testing", "exceptions", "report"),
}
# Contract §3: the closed pill code set.
PILLS: Final = {
    "getting_started",
    "preparing_return",
    "reviewing_return",
    "reconciling_accounts",
    "filed_and_accepted",
    "finishing_audit",
    "testing_under_way",
}
# DEC-209: a done item has no card (it is an Earlier row).
DONE: Final = {
    "return": {"accepted"},
    "close": {"delivered", "locked"},
    "audit_engagement": {"released", "archiving", "archived"},
}
# DEC-209's table (and POR-02 a, b, d, e, g, h): code -> the current stage.
CURRENT: Final = {
    ("return_1040", "not_started"): "gather_documents",  # POR-02 b "We're getting started"
    ("return_1040", "gathering"): "gather_documents",
    ("return_1040", "preparing"): "prepare",  # POR-02 e "We're preparing your return"
    ("return_1040", "prepared"): "review",
    ("return_1040", "in_review"): "review",  # POR-02 a, the Feld 1040
    ("return_1040", "action_required"): "review",
    ("return_1040", "approved"): "sign_form_8879",
    ("return_1040", "awaiting_signature"): "sign_form_8879",
    ("return_1040", "filed"): "file",
    ("return_1040", "rejected"): "file",
    ("return_1040", "fixing"): "file",
    ("return_entity", "approved"): "file",
    ("return_entity", "awaiting_signature"): "file",
    ("return_entity", "in_review"): "review",
    ("close", "not_started"): "requests",
    ("close", "in_progress"): "reconcile",  # POR-02 d "We're reconciling your accounts"
    ("close", "in_review"): "review",
    ("close", "approved"): "statements",
    ("audit", "planning"): "planning",
    ("audit", "fieldwork"): "fieldwork",
    ("audit", "in_review"): "statements_review",
    ("audit", "completion"): "statements_review",  # POR-02 g, Granite Peak
    ("audit", "ready_to_release"): "report",
    ("soc2", "planning"): "scoping",
    ("soc2", "fieldwork"): "testing",  # POR-02 h "Testing is under way"
    ("soc2", "in_review"): "exceptions",
    ("soc2", "completion"): "exceptions",
    ("soc2", "ready_to_release"): "report",
}
PILL_AT: Final = {
    ("return_1040", "not_started"): "getting_started",
    ("return_1040", "preparing"): "preparing_return",
    ("return_1040", "in_review"): "reviewing_return",
    ("return_1040", "action_required"): "reviewing_return",  # never red (DEC-209)
    ("return_1040", "approved"): "reviewing_return",
    ("close", "in_progress"): "reconciling_accounts",
    ("audit", "completion"): "finishing_audit",
    ("soc2", "fieldwork"): "testing_under_way",
}


def _registry() -> dict[str, dict[str, dict[str, object]]]:
    objects = yaml.safe_load(REGISTRY.read_text())["objects"]
    return {name: objects[name]["codes"] for name in set(OBJECT_OF.values())}


def _codes(kind: str) -> list[str]:
    return list(_registry()[OBJECT_OF[kind]])


def _firm_words() -> set[str]:
    """Every firm status code and label of the five objects, case-folded."""
    words: set[str] = set()
    for codes in _registry().values():
        for code, entry in codes.items():
            words.add(code.casefold())
            words.add(str(entry["label"]).casefold())
    return words


# A derived chip (`derived: true`: `close.past_due`, `audit_engagement.processing`) is computed
# for display and never stored, so it is no work item's status and not the projection's input
# (spec gap: T12 says "every registry code"; read as every code a work item can hold).
ALL: Final = [
    (kind, code)
    for kind in OBJECT_OF
    for code in _codes(kind)
    if _registry()[OBJECT_OF[kind]][code].get("derived") is not True
]


@pytest.mark.parametrize(("kind", "code"), ALL)
def test_t12_every_registry_code_projects_to_one_current_stage_or_to_done(
    kind: str, code: str
) -> None:
    view = client_view(kind, code)  # type: ignore[arg-type]  # the registry's plain string
    if code in DONE[OBJECT_OF[kind]]:
        assert view is None, (kind, code)
        return
    assert view is not None, (kind, code)
    stages = [s.code for s in view.stages]
    assert tuple(stages) == TRACKER[kind], (kind, code)
    states = [s.state for s in view.stages]
    assert states.count("current") == 1, (kind, code, states)
    at = states.index("current")
    assert states[:at] == ["done"] * at and states[at + 1 :] == ["upcoming"] * (
        len(states) - at - 1
    )
    assert view.pill in PILLS, (kind, code, view.pill)
    assert view.variant in ("state", "success", "neutral"), (kind, code)


@pytest.mark.parametrize(("kind", "code"), sorted(CURRENT))
def test_t12_dec209_and_por02_place_each_code_on_its_stage(kind: str, code: str) -> None:
    view = client_view(kind, code)  # type: ignore[arg-type]  # the registry's plain string
    assert view is not None, (kind, code)
    current = next(s.code for s in view.stages if s.state == "current")
    assert current == CURRENT[(kind, code)]
    if (kind, code) in PILL_AT:
        assert view.pill == PILL_AT[(kind, code)]


def test_t12_the_feld_1040_reads_review_and_granite_peak_statements_review() -> None:
    feld = client_view("return_1040", "in_review")
    assert feld is not None
    assert [(s.code, s.state) for s in feld.stages] == [
        ("gather_documents", "done"),
        ("prepare", "done"),
        ("review", "current"),
        ("sign_form_8879", "upcoming"),
        ("file", "upcoming"),
    ]
    assert (feld.pill, feld.variant) == ("reviewing_return", "state")
    granite = client_view("audit", "completion")
    assert granite is not None
    assert [(s.code, s.state) for s in granite.stages] == [
        ("planning", "done"),
        ("fieldwork", "done"),
        ("statements_review", "current"),
        ("report", "upcoming"),
    ]


@pytest.mark.parametrize(("kind", "code"), ALL)
def test_t12_no_firm_status_word_can_be_returned(kind: str, code: str) -> None:
    view = client_view(kind, code)  # type: ignore[arg-type]  # the registry's plain string
    if view is None:
        return
    returned = {view.pill, view.variant, *(s.code for s in view.stages)}
    returned |= {s.state for s in view.stages}
    # A client stage may share a plain word with a firm code only where POR-02 draws it
    # ("Review", "Planning", "Fieldwork" are the trackers' own steps), never a firm status
    # phrase: "in_review", "Action required", "In review · Manager".
    allowed = {"review", "planning", "fieldwork", "statements", "report", "done"}
    leaked = {w for w in returned if w.casefold() in _firm_words()} - allowed
    assert leaked == set(), (kind, code, leaked)


def test_t12_an_unknown_code_is_refused_not_projected() -> None:
    for kind in OBJECT_OF:
        with pytest.raises(ValueError):
            client_view(kind, "in_review_manager")  # type: ignore[arg-type]  # the registry's plain string
