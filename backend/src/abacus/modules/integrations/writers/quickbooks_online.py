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

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final, Literal, Protocol, cast

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

    async def book_close_date(self) -> date | None:
        """The ledger's closing date as QuickBooks has it now (C-02-T24's conflict row)."""
        return await self._t.book_close_date()

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


# --- C-02-T30: the live transport (Intuit's v3 API over the kernel's W1 write lane) ------------

_QBO_ID: Final = re.compile(r"[0-9]{1,20}")


def request_id_of(key: str) -> str:
    """Intuit's `requestid` for an idempotency key: 40 hex characters of its SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()[:40]


def journal_body(entry: JournalEntry) -> dict[str, object]:
    """The JournalEntry create body (golden-tested): DocNumber, TxnDate, the memo as PrivateNote
    (the posting marker), one JournalEntryLineDetail per line. Account refs are QuickBooks ids."""
    return {
        "DocNumber": entry.doc_number,
        "TxnDate": entry.txn_date.isoformat(),
        "PrivateNote": entry.memo,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": str(ln.amount),
                "Description": ln.description,
                "JournalEntryLineDetail": {
                    "PostingType": ln.posting_type,
                    "AccountRef": {"value": ln.account_ref},
                },
            }
            for ln in entry.lines
        ],
    }


def _code_of(status: int) -> WriteError:
    if status == 429:
        return "rate_limited"
    if status == 401:
        return "needs_reauth"
    return "inactive_account" if status == 400 else "rate_limited"


class HttpQboTransport:
    """QuickBooks Online over `EgressClient`: reads with `request` (GET), writes with `write` (the
    W1 lane only, so nothing writes until a released entry or the sandbox test opens the lane).
    Provider text never leaves: statuses map to `WriteError` codes."""

    def __init__(self, client: object, host: str, realm_id: str, access_token: str) -> None:
        from abacus.kernel.egress import EgressClient

        if not _QBO_ID.fullmatch(realm_id):
            raise ValueError("realm")
        self._c = cast(EgressClient, client)
        self._base = f"https://{host}/v3/company/{realm_id}"
        self._auth = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    async def _get(self, path: str) -> dict[str, object]:
        response = await self._c.request("GET", f"{self._base}{path}", headers=self._auth)
        if response.status_code != 200:
            raise QboError(_code_of(response.status_code))
        return cast(dict[str, object], json.loads(response.content))

    async def _post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        response = await self._c.write(
            f"{self._base}{path}",
            headers={**self._auth, "Content-Type": "application/json"},
            content=json.dumps(body, sort_keys=True).encode(),
        )
        if response.status_code != 200:
            raise QboError(_code_of(response.status_code))
        return cast(dict[str, object], json.loads(response.content))

    async def book_close_date(self) -> date | None:
        prefs = await self._get("/preferences?minorversion=75")
        accounting = cast(dict[str, object], cast(dict[str, object], prefs["Preferences"]).get(
            "AccountingInfoPrefs", {}
        ))  # fmt: skip
        raw = accounting.get("BookCloseDate")
        return date.fromisoformat(str(raw)) if raw else None

    async def accounts_active(self, refs: Sequence[str]) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for ref in refs:
            if not _QBO_ID.fullmatch(ref):
                out[ref] = False
                continue
            found = await self._get(f"/account/{ref}?minorversion=75")
            out[ref] = bool(cast(dict[str, object], found["Account"]).get("Active", False))
        return out

    async def create_journal_entry(self, entry: JournalEntry, request_id: str) -> str:
        # Intuit's `requestid` (≤ 50 characters) makes the create idempotent: a retry answers
        # the first entry. Ours is a digest of `{batch}:{entry}`, so it never collides.
        rid = request_id_of(request_id)
        created = await self._post(f"/journalentry?requestid={rid}&minorversion=75", journal_body(entry))
        return str(cast(dict[str, object], created["JournalEntry"])["Id"])

    async def read_journal_entry(self, external_ref: str) -> tuple[JournalLine, ...]:
        if not _QBO_ID.fullmatch(external_ref):
            raise ValueError("external_ref")
        found = cast(dict[str, object], (await self._get(f"/journalentry/{external_ref}?minorversion=75"))["JournalEntry"])
        lines: list[JournalLine] = []
        for raw in cast(list[dict[str, object]], found.get("Line", [])):
            detail = cast(dict[str, object], raw.get("JournalEntryLineDetail", {}))
            ref = cast(dict[str, object], detail.get("AccountRef", {})).get("value")
            lines.append(
                JournalLine(
                    None if ref is None else str(ref),
                    cast(PostingType, detail.get("PostingType")),
                    Decimal(str(raw.get("Amount"))),
                )
            )
        return tuple(lines)

    async def set_book_close_date(self, on: date, request_id: str) -> None:
        prefs = await self._get("/preferences?minorversion=75")
        token = cast(dict[str, object], prefs["Preferences"]).get("SyncToken")
        rid = request_id_of(request_id)
        await self._post(
            f"/preferences?requestid={rid}&minorversion=75",
            {"sparse": True, "SyncToken": token,
             "AccountingInfoPrefs": {"BookCloseDate": on.isoformat()}},
        )  # fmt: skip
