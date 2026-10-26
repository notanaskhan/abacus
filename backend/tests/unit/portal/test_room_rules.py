"""R-01-T13 (DEC-387): the third-party room's pure rules: each row's sub-line and disc, and the
code-only "Which request is this for?" scoring on file names (ADR-050); and the matrix's
`delegated_only` cell, which allows only a request whose facts name the person among its
delegates and denies without them."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.evidence.api import PortalFile, SentBack
from abacus.modules.identity.api import RULES, AuthContext, ItemFacts, Resource
from abacus.modules.identity.authz import (
    _on_item,  # pyright: ignore[reportPrivateUsage] -- the cell rule itself
)
from abacus.modules.portal.rooms import row_state, suggest, tokens

ME = uuid.uuid4()
OTHER = uuid.uuid4()
ZONE = ZoneInfo("America/Chicago")
SEP_22 = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)
DUE = date(2026, 9, 25)


def _file(
    *,
    by: uuid.UUID | None = ME,
    accepted: bool = False,
    arrived: str = "client_upload",
    back: SentBack | None = None,
) -> PortalFile:
    return PortalFile(
        version_id=uuid.uuid4(),
        name="Keystone_Bridge_Letter.pdf",
        size_bytes=2048,
        arrived=arrived,
        uploader_user_id=by,
        created_at=SEP_22,
        withdrawable_kind=True,
        accepted=accepted,
        sent_back=back,
    )


def test_a_request_still_owed_reads_due_on_its_date_with_a_ring() -> None:
    assert row_state("requested", [], ME, DUE, ZONE) == ("due", DUE, "ring")


def test_the_callers_own_unaccepted_upload_is_in_review_and_done() -> None:
    assert row_state("uploaded", [_file()], ME, DUE, ZONE) == (
        "in_review",
        date(2026, 9, 22),
        "done",
    )


def test_someone_elses_or_an_accepted_file_reads_uploaded() -> None:
    assert row_state("uploaded", [_file(by=OTHER)], ME, DUE, ZONE)[0] == "uploaded"
    assert row_state("received", [_file(accepted=True)], ME, DUE, ZONE)[0] == "uploaded"
    assert row_state("uploaded", [_file(arrived="firm")], ME, DUE, ZONE)[0] == "uploaded"


def test_a_returned_request_reads_returned_on_the_send_back_date_with_a_ring() -> None:
    back = SentBack("wrong_period", "This letter covers Jan to Jun 2025.", OTHER, SEP_22)
    assert row_state("returned", [_file(back=back)], ME, DUE, ZONE) == (
        "returned",
        date(2026, 9, 22),
        "ring",
    )


def test_tokens_fold_case_accents_and_extensions_and_drop_numbers() -> None:
    assert tokens("Keystone_Bridge-Letter_Q4_2025.PDF") == frozenset(
        {"keystone", "bridge", "letter"}
    )
    assert tokens("Café 408(b)(2) Fee") == frozenset({"cafe", "fee"})


ROWS = (
    (uuid.UUID(int=1), "Bridge letter — Oct 1 to Dec 31, 2025"),
    (uuid.UUID(int=2), "ERISA 408(b)(2) fee disclosure"),
    (uuid.UUID(int=3), "Plan expense invoices paid from plan assets — 2025"),
)


@pytest.mark.parametrize(
    ("name", "want"),
    [
        ("Keystone_Bridge_Letter_Oct-Dec.pdf", uuid.UUID(int=1)),
        ("408b2 Fee Disclosure 2025.pdf", uuid.UUID(int=2)),
        ("plan_expense_invoices.xlsx", uuid.UUID(int=3)),
        ("Scan_0914.pdf", None),  # nothing shared: the person chooses
        ("plan letter.pdf", None),  # a tie (plan / letter): the person chooses
    ],
)
def test_suggest_picks_the_one_best_title_or_none(name: str, want: uuid.UUID | None) -> None:
    assert suggest(name, ROWS) == want


def test_suggest_never_offers_a_request_outside_the_rows_given() -> None:
    assert suggest("Census payroll register.xlsx", ROWS) is None
    assert suggest("anything.pdf", []) is None


# --- `delegated_only` ---------------------------------------------------------------------------


def _ctx() -> AuthContext:
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(ME)), ME, uuid.uuid4(), None, None, client=True
    )


def test_delegated_only_allows_a_request_delegated_to_the_person() -> None:
    facts = ItemFacts(True, None, delegated_to=frozenset({ME}))
    resource = _resource(facts)
    assert _on_item("delegated_only", _ctx(), resource) == "allow"


@pytest.mark.parametrize(
    "facts",
    [
        ItemFacts(True, None, delegated_to=frozenset({OTHER})),  # someone else's delegation
        ItemFacts(True, None, delegated_to=frozenset()),  # not delegated
        ItemFacts(True, None),  # the owner read no delegates: deny (fail closed)
        ItemFacts(False, None, delegated_to=frozenset({ME})),  # internal-only
        ItemFacts(True, ME),  # assigned is not delegated
    ],
)
def test_delegated_only_denies_anything_else(facts: ItemFacts) -> None:
    assert _on_item("delegated_only", _ctx(), _resource(facts)) is None


def test_no_resource_without_item_facts_passes_delegated_only() -> None:
    assert _on_item("delegated_only", _ctx(), _resource(None)) is None


def test_the_third_party_holds_delegated_only_cells_and_nothing_else() -> None:
    held = {
        action: rule.decisions["third_party"]
        for action, rule in RULES.items()
        if "third_party" in rule.decisions
    }
    assert held == {
        "portal_documents.read": "delegated_only",
        "request_item.read": "delegated_only",
        "evidence.upload": "delegated_only",
        "evidence.withdraw": "delegated_only",
        "comment.read": "delegated_only",
        "comment.create": "delegated_only",
    }


def _resource(facts: ItemFacts | None) -> Resource:
    return Resource.engagement(uuid.uuid4(), uuid.uuid4(), archived=False, item=facts)
