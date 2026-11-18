"""The QuickBooks Online W1 writer (C-02-T13; ADR-344 = P-16 W1; ADR-150; SPEC-700; DEC-5623).
PROTECTED (red).

One declared capability, `qbo.post_journal_entry`, behind the `Writer` port. It is reachable
only through `integrations.writes.execute_write` (static rule WRITE-001 names this file as the
only implementation and `adjustments/posting.py` as its only caller); in S50 `execute_write`
still refuses every write, so nothing here runs against a client until C-02-T18/T19 turn the
path on behind `adjustments.posting` and the client's write grant.

- **Preflight** (`preflight`, reads only): the entry balances (debits = credits, code, ADR-050);
  its date is after the company's `BookCloseDate`; every line's account is mapped and active;
  the `DocNumber` is the entry's ref. A failed check names it and nothing is written.
- **Post** (`post`): one `JournalEntry` create with QuickBooks' `requestid` idempotency (the same
  request id answers the same entry, never a second one), then a **read-back** that must match
  line for line (account, posting type, amount), or the result is `verify_mismatch`.
- **Closing date** (`set_book_close_date`): sets `BookCloseDate` after a batch's last entry posts
  [verify against the live API before go-live: QuickBooks exposes it on `Preferences`].
- **Errors** map to codes: an inactive account `inactive_account`, a closed period
  `closing_date_locked`, 429 `rate_limited` (retry with backoff), 401 `needs_reauth`.

The transport is a port (`QboTransport`); `FakeQboTransport` scripts outcomes for tests and the
synthetic tenant, and records every non-GET call so the interception harness can prove nothing
else is written.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final, Literal, Protocol

CAPABILITY: Final = "qbo.post_journal_entry"
PostingType = Literal["Debit", "Credit"]
FailedCheck = Literal[
    "unbalanced", "closed_period", "unmapped_account", "inactive_account", "doc_number"
]
WriteError = Literal["inactive_account", "closing_date_locked", "rate_limited", "needs_reauth"]


@dataclass(frozen=True)
class JournalLine:
    account_ref: str | None  # the mapped QuickBooks account id; None: unmapped
    posting_type: PostingType
    amount: Decimal
    description: str = ""


@dataclass(frozen=True)
class JournalEntry:
    doc_number: str  # the entry's ref, AJE-01
    txn_date: date
    lines: tuple[JournalLine, ...]
    memo: str = ""


@dataclass(frozen=True)
class Preflight:
    ok: bool
    failed_check: FailedCheck | None = None
    account_ref: str | None = None


@dataclass(frozen=True)
class Posted:
    external_ref: str
    verified: bool
    error: WriteError | None = None


class QboError(Exception):
    """A QuickBooks answer mapped to a code (never the provider's text, ADR-031)."""

    def __init__(self, code: WriteError) -> None:
        super().__init__(code)
        self.code: WriteError = code


class QboTransport(Protocol):
    async def book_close_date(self) -> date | None: ...

    async def accounts_active(self, refs: Sequence[str]) -> dict[str, bool]: ...

    async def create_journal_entry(self, entry: JournalEntry, request_id: str) -> str: ...

    async def read_journal_entry(self, external_ref: str) -> tuple[JournalLine, ...]: ...

    async def set_book_close_date(self, on: date, request_id: str) -> None: ...


def balanced(lines: Sequence[JournalLine]) -> bool:
    debits = sum((ln.amount for ln in lines if ln.posting_type == "Debit"), Decimal("0"))
    credits = sum((ln.amount for ln in lines if ln.posting_type == "Credit"), Decimal("0"))
    return debits == credits and debits > 0


class QuickBooksOnlineWriter:
    """The W1 writer for one connection (its transport carries the connection's token)."""

    def __init__(self, transport: QboTransport) -> None:
        self._t = transport

    @property
    def capability(self) -> str:
        return CAPABILITY

    async def preflight(self, entry: JournalEntry) -> Preflight:
        if not entry.doc_number:
            return Preflight(False, "doc_number")
        if not balanced(entry.lines):
            return Preflight(False, "unbalanced")
        closed = await self._t.book_close_date()
        if closed is not None and entry.txn_date <= closed:
            return Preflight(False, "closed_period")
        for line in entry.lines:
            if line.account_ref is None:
                return Preflight(False, "unmapped_account")
        refs = sorted({ln.account_ref for ln in entry.lines if ln.account_ref is not None})
        active = await self._t.accounts_active(refs)
        for ref in refs:
            if not active.get(ref, False):
                return Preflight(False, "inactive_account", ref)
        return Preflight(True)

    async def post(self, entry: JournalEntry, request_id: str) -> Posted:
        """Preflight, one idempotent create, then the read-back (line for line)."""
        check = await self.preflight(entry)
        if not check.ok:
            code: WriteError = (
                "inactive_account"
                if check.failed_check == "inactive_account"
                else "closing_date_locked"
            )
            if check.failed_check not in ("inactive_account", "closed_period"):
                raise ValueError(f"preflight failed: {check.failed_check}")
            return Posted("", False, code)
        try:
            ref = await self._t.create_journal_entry(entry, request_id)
        except QboError as error:
            return Posted("", False, error.code)
        back = await self._t.read_journal_entry(ref)
        return Posted(ref, _same(entry.lines, back))

    async def set_book_close_date(self, on: date, request_id: str) -> WriteError | None:
        try:
            await self._t.set_book_close_date(on, request_id)
        except QboError as error:
            return error.code
        return None


def _key(ln: JournalLine) -> tuple[str, str, Decimal]:
    return (ln.account_ref or "", ln.posting_type, ln.amount)


def _same(sent: Sequence[JournalLine], back: Sequence[JournalLine]) -> bool:
    return sorted(map(_key, sent)) == sorted(map(_key, back))


# --- the scripted fake ---------------------------------------------------------------------------


@dataclass
class FakeQboTransport:
    """A QuickBooks company in memory: accounts with active flags, a book close date, and
    scripted create outcomes. `writes` records every non-GET call (method, what) in order."""

    accounts: dict[str, bool] = field(default_factory=dict[str, bool])
    closed_on: date | None = None
    script: list[WriteError | None] = field(default_factory=list[WriteError | None])
    writes: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    _entries: dict[str, tuple[JournalLine, ...]] = field(
        default_factory=dict[str, tuple[JournalLine, ...]]
    )
    _by_request: dict[str, str] = field(default_factory=dict[str, str])
    _next: int = 48213

    async def book_close_date(self) -> date | None:
        return self.closed_on

    async def accounts_active(self, refs: Sequence[str]) -> dict[str, bool]:
        return {r: self.accounts.get(r, False) for r in refs}

    async def create_journal_entry(self, entry: JournalEntry, request_id: str) -> str:
        if request_id in self._by_request:  # QuickBooks requestid: the same answer, no new entry
            return self._by_request[request_id]
        outcome = self.script.pop(0) if self.script else None
        if outcome is not None:
            raise QboError(outcome)
        ref = str(self._next)
        self._next += 1
        self._entries[ref] = entry.lines
        self._by_request[request_id] = ref
        self.writes.append(("POST JournalEntry", entry.doc_number))
        return ref

    async def read_journal_entry(self, external_ref: str) -> tuple[JournalLine, ...]:
        return self._entries[external_ref]

    async def set_book_close_date(self, on: date, request_id: str) -> None:
        self.closed_on = on
        self.writes.append(("POST Preferences.BookCloseDate", on.isoformat()))
