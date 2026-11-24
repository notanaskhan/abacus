"""C-02-T32 (TASK-8907; C-02 F4 US-4.1; ADR P-13; red): the attest CAS path.

Row acceptance: "The attest client's entries reach POR-08, become Client approved and then
Recorded by the client, and no posting batch can include them." Here: an attest send goes to the
approver of record only (resolved when omitted, refused when someone else is named); an attest
entry is recorded only after the client approved it; a sync match is one code finds (every entry
account for the same amount in one ledger transaction); posting refuses an attest client at the
registry; the routes call the path.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.adjustments import attest_path
from abacus.modules.adjustments.attest_path import EntryLine, RegisterHit, matching_txns

SRC = Path(attest_path.__file__).parent


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(tenant=SimpleNamespace(tenant_id=uuid4()), user_id=uuid4())


# --- the sync match is code's ----------------------------------------------------------------


def test_a_journal_matches_when_it_carries_every_account_and_amount() -> None:
    lines = [EntryLine("6120", Decimal("1250.00")), EntryLine("2100", Decimal("1250.00"))]
    hits = [
        RegisterHit("148", "6120", Decimal("1250.00")),
        RegisterHit("148", "2100", Decimal("-1250.00")),  # the register's natural sign
        RegisterHit("151", "6120", Decimal("1250.00")),  # one side only
        RegisterHit("152", "6120", Decimal("1200.00")),
        RegisterHit("152", "2100", Decimal("1200.00")),  # another amount
    ]
    assert matching_txns(lines, hits) == ["148"]


def test_a_split_entry_needs_each_line_matched_once() -> None:
    lines = [
        EntryLine("6120", Decimal("100.00")),
        EntryLine("6120", Decimal("100.00")),
        EntryLine("2100", Decimal("200.00")),
    ]
    once = [RegisterHit("9", "6120", Decimal("100.00")), RegisterHit("9", "2100", Decimal("200"))]
    twice = [*once, RegisterHit("9", "6120", Decimal("100.00"))]
    assert matching_txns(lines, once) == []
    assert matching_txns(lines, twice) == ["9"]


def test_the_next_month_is_looked_at_too() -> None:
    from datetime import date

    assert attest_path._periods(date(2026, 12, 31)) == ("2026-12", "2027-01")  # pyright: ignore[reportPrivateUsage]
    assert attest_path._periods(date(2026, 8, 31)) == ("2026-08", "2026-09")  # pyright: ignore[reportPrivateUsage]


# --- the send goes to the approver of record -------------------------------------------------


@pytest.fixture
def attest(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    from abacus.modules.adjustments import entries
    from abacus.modules.engagements import api as engagements

    state = SimpleNamespace(attest=True, approver=uuid4())

    async def engagement_of(*_: object) -> object:
        return uuid4()

    async def attest_of(*_: object) -> object:
        return state.attest

    async def approver(*_: object) -> object:
        if state.approver is None:
            raise attest_path.ApproverOfRecordMissing
        return state.approver

    monkeypatch.setattr(entries, "engagement_of", engagement_of)
    monkeypatch.setattr(engagements, "attest_of", attest_of)
    monkeypatch.setattr(attest_path, "approver_of_record", approver)
    return state


async def test_an_attest_send_goes_to_the_approver_of_record(attest: SimpleNamespace) -> None:
    recipient, is_attest = await attest_path.recipient_for(_ctx(), uuid4(), None)  # type: ignore[arg-type]
    assert (recipient, is_attest) == (attest.approver, True)
    same, _ = await attest_path.recipient_for(_ctx(), uuid4(), attest.approver)  # type: ignore[arg-type]
    assert same == attest.approver


async def test_an_attest_send_to_anyone_else_is_refused(attest: SimpleNamespace) -> None:
    with pytest.raises(attest_path.NotApproverOfRecord):
        await attest_path.recipient_for(_ctx(), uuid4(), uuid4())  # type: ignore[arg-type]


async def test_no_approver_of_record_refuses(attest: SimpleNamespace) -> None:
    attest.approver = None
    with pytest.raises(attest_path.ApproverOfRecordMissing):
        await attest_path.recipient_for(_ctx(), uuid4(), None)  # type: ignore[arg-type]


async def test_unknown_attest_reads_attest(attest: SimpleNamespace) -> None:
    attest.attest = None  # fail closed
    recipient, is_attest = await attest_path.recipient_for(_ctx(), uuid4(), None)  # type: ignore[arg-type]
    assert is_attest and recipient == attest.approver


async def test_a_non_attest_send_keeps_its_named_contact(attest: SimpleNamespace) -> None:
    attest.attest = False
    named = uuid4()
    assert await attest_path.recipient_for(_ctx(), uuid4(), named) == (named, False)  # type: ignore[arg-type]


# --- recorded by the client only after the client approved ------------------------------------


def _session(row: object) -> object:
    class _S:
        async def __aenter__(self) -> _S:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def execute(self, *_: object) -> object:
            return SimpleNamespace(first=lambda: row)

    return _S()


async def test_an_attest_entry_is_recorded_only_once_client_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = SimpleNamespace(status="approved", is_attest_client=True)
    monkeypatch.setattr(attest_path, "tenant_session", lambda _t: _session(row))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    with pytest.raises(attest_path.ClientApprovalRequired):
        await attest_path.check_record(_ctx(), uuid4(), match_ref=None)  # type: ignore[arg-type]


async def test_a_match_code_cannot_find_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    row = SimpleNamespace(status="client_approved", is_attest_client=True)

    async def matches(*_: object) -> list[str]:
        return ["qbo:148"]

    monkeypatch.setattr(attest_path, "tenant_session", lambda _t: _session(row))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(attest_path, "ledger_matches", matches)
    with pytest.raises(attest_path.LedgerMatchNotFound):
        await attest_path.check_record(_ctx(), uuid4(), match_ref="qbo:999")  # type: ignore[arg-type]
    await attest_path.check_record(_ctx(), uuid4(), match_ref="qbo:148")  # type: ignore[arg-type]
    await attest_path.check_record(_ctx(), uuid4(), match_ref=None)  # type: ignore[arg-type]  # evidence path


def test_the_row_word_names_the_client_for_an_attest_entry() -> None:
    assert attest_path.recorded_label(True, "Larkspur Health") == "Recorded by Larkspur Health"
    assert attest_path.recorded_label(False, "Copperleaf") == "Recorded in ledger"


# --- no posting batch can include them --------------------------------------------------------


def test_posting_refuses_an_attest_client_at_the_registry() -> None:
    from abacus.modules.integrations.capabilities import ATTEST_REFUSED_SHAPES, policy_refusal
    from abacus.modules.integrations.ports import WriteCapabilityEntry

    shape = sorted(ATTEST_REFUSED_SHAPES)[0]
    fields = WriteCapabilityEntry.model_fields
    entry = SimpleNamespace(shape=shape, **{k: None for k in fields if k != "shape"})
    assert policy_refusal(entry, attest_client=True) == "attest_client"  # type: ignore[arg-type]


def test_the_batch_refuses_attest_entries_before_anything_is_written() -> None:
    posting = (SRC / "posting.py").read_text(encoding="utf-8")
    assert "if any(e.is_attest_client for e in entries):" in posting
    assert "AttestClientPostingRefused" in posting


def test_the_routes_use_the_attest_path() -> None:
    contract = (SRC / "contract.py").read_text(encoding="utf-8")
    assert "attest_path.recipient_for(ctx, work_item_id, body.recipient_contact_id)" in contract
    recovery = (SRC / "posting_recovery.py").read_text(encoding="utf-8")
    assert "await check_record(ctx, entry_id, match_ref=match_ref)" in recovery
    posting = (SRC / "posting_contract.py").read_text(encoding="utf-8")
    assert '"/proposed-entries/{entry_id}/ledger-matches"' in posting
