"""CV-2 (TASK-9001; DEC-6003; C-02-T30; ADR-344): the live QuickBooks Online transport, over a
scripted egress client. Main CI measured `writers/quickbooks_online.py` at 68%: the transport that
makes the one write to a client's books had no test of its requests or its error mapping.

Held here by exact values: every URL (realm, minor version, `requestid` digest), every body sent,
reads only through `request` (GET) and writes only through `write` (the W1 lane), statuses mapped
to `WriteError` codes with no provider text, and refusals of a malformed realm or id."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D

import pytest

from abacus.modules.integrations.writers import quickbooks_online as q

pytestmark = pytest.mark.asyncio
BASE = "https://quickbooks.api.intuit.com/v3/company/9130"


@dataclass
class Response:
    status_code: int
    content: bytes


@dataclass
class Egress:
    """GETs answered from `reads` by URL; writes answered in order from `writes`."""

    reads: dict[str, Response] = field(default_factory=dict[str, Response])
    writes: list[Response] = field(default_factory=list[Response])
    sent: list[tuple[str, str, dict[str, str], bytes | None]] = field(
        default_factory=list[tuple[str, str, dict[str, str], bytes | None]]
    )

    async def request(self, method: str, url: str, *, headers: dict[str, str]) -> Response:
        self.sent.append((method, url, headers, None))
        return self.reads[url]

    async def write(self, url: str, *, headers: dict[str, str], content: bytes) -> Response:
        self.sent.append(("WRITE", url, headers, content))
        return self.writes.pop(0)


def ok(body: object) -> Response:
    return Response(200, json.dumps(body).encode())


ENTRY = q.JournalEntry(
    "AJE-1",
    date(2026, 8, 31),
    (
        q.JournalLine("61", "Debit", D("250.00"), "Accrued rent"),
        q.JournalLine("21", "Credit", D("250.00")),
    ),
    memo="Accrued · batch 2026-08-A",
)


def _transport(egress: Egress) -> q.HttpQboTransport:
    return q.HttpQboTransport(egress, "quickbooks.api.intuit.com", "9130", "token-abc")


def test_the_request_id_is_forty_hex_of_the_keys_digest() -> None:
    rid = q.request_id_of("batch:entry")
    assert len(rid) == 40 and int(rid, 16) >= 0
    assert rid == q.request_id_of("batch:entry") != q.request_id_of("batch:other")


def test_the_journal_body_is_exact() -> None:
    assert q.journal_body(ENTRY) == {
        "DocNumber": "AJE-1",
        "TxnDate": "2026-08-31",
        "PrivateNote": "Accrued · batch 2026-08-A",
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": "250.00",
                "Description": "Accrued rent",
                "JournalEntryLineDetail": {"PostingType": "Debit", "AccountRef": {"value": "61"}},
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": "250.00",
                "Description": "",
                "JournalEntryLineDetail": {"PostingType": "Credit", "AccountRef": {"value": "21"}},
            },
        ],
    }


@pytest.mark.parametrize("realm", ["", "abc", "91 30", "1" * 21, "9130/../1"])
def test_a_malformed_realm_is_refused(realm: str) -> None:
    with pytest.raises(ValueError, match="realm"):
        q.HttpQboTransport(Egress(), "quickbooks.api.intuit.com", realm, "t")


async def test_the_closing_date_is_read_from_the_accounting_preferences() -> None:
    url = f"{BASE}/preferences?minorversion=75"
    egress = Egress(
        reads={url: ok({"Preferences": {"AccountingInfoPrefs": {"BookCloseDate": "2026-07-31"}}})}
    )
    assert await _transport(egress).book_close_date() == date(2026, 7, 31)
    method, sent_url, headers, body = egress.sent[0]
    assert (method, sent_url, body) == ("GET", url, None)
    assert headers == {"Authorization": "Bearer token-abc", "Accept": "application/json"}
    unset: tuple[dict[str, object], ...] = (
        {"Preferences": {}},
        {"Preferences": {"AccountingInfoPrefs": {"BookCloseDate": ""}}},
    )
    for prefs in unset:
        assert await _transport(Egress(reads={url: ok(prefs)})).book_close_date() is None


async def test_accounts_are_read_one_by_one_and_a_non_id_is_inactive_unread() -> None:
    egress = Egress(
        reads={
            f"{BASE}/account/61?minorversion=75": ok({"Account": {"Active": True}}),
            f"{BASE}/account/21?minorversion=75": ok({"Account": {"Active": False}}),
            f"{BASE}/account/7?minorversion=75": ok({"Account": {}}),
        }
    )
    got = await _transport(egress).accounts_active(["61", "21", "7", "../x"])
    assert got == {"61": True, "21": False, "7": False, "../x": False}
    assert [u for _, u, _, _ in egress.sent] == [
        f"{BASE}/account/61?minorversion=75",
        f"{BASE}/account/21?minorversion=75",
        f"{BASE}/account/7?minorversion=75",
    ]


async def test_a_journal_entry_is_written_once_through_the_write_lane() -> None:
    egress = Egress(writes=[ok({"JournalEntry": {"Id": "48213"}})])
    ref = await _transport(egress).create_journal_entry(ENTRY, "b1:e1")
    assert ref == "48213"
    method, url, headers, body = egress.sent[0]
    assert method == "WRITE"
    assert url == f"{BASE}/journalentry?requestid={q.request_id_of('b1:e1')}&minorversion=75"
    assert headers["Content-Type"] == "application/json"
    assert body == json.dumps(q.journal_body(ENTRY), sort_keys=True).encode()


async def test_the_read_back_returns_the_lines_as_quickbooks_holds_them() -> None:
    url = f"{BASE}/journalentry/48213?minorversion=75"
    egress = Egress(
        reads={
            url: ok(
                {
                    "JournalEntry": {
                        "Line": [
                            {
                                "Amount": 250.0,
                                "JournalEntryLineDetail": {
                                    "PostingType": "Debit",
                                    "AccountRef": {"value": "61"},
                                },
                            },
                            {
                                "Amount": "250.00",
                                "JournalEntryLineDetail": {"PostingType": "Credit"},
                            },
                        ]
                    }
                }
            )
        }
    )
    got = await _transport(egress).read_journal_entry("48213")
    assert got == (
        q.JournalLine("61", "Debit", D("250.0")),
        q.JournalLine(None, "Credit", D("250.00")),
    )
    with pytest.raises(ValueError, match="external_ref"):
        await _transport(egress).read_journal_entry("48213; DROP")
    empty = Egress(reads={url: ok({"JournalEntry": {}})})
    assert await _transport(empty).read_journal_entry("48213") == ()


async def test_the_closing_date_is_set_sparse_with_the_sync_token() -> None:
    prefs = f"{BASE}/preferences?minorversion=75"
    egress = Egress(reads={prefs: ok({"Preferences": {"SyncToken": "7"}})}, writes=[ok({})])
    await _transport(egress).set_book_close_date(date(2026, 8, 31), "b1:closing")
    _, url, _, body = egress.sent[1]
    assert url == f"{BASE}/preferences?requestid={q.request_id_of('b1:closing')}&minorversion=75"
    assert json.loads(body or b"") == {
        "sparse": True,
        "SyncToken": "7",
        "AccountingInfoPrefs": {"BookCloseDate": "2026-08-31"},
    }


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (429, "rate_limited"),
        (401, "needs_reauth"),
        (400, "inactive_account"),
        (500, "rate_limited"),
        (503, "rate_limited"),
    ],
)
async def test_a_status_maps_to_its_code_with_no_provider_text(status: int, code: str) -> None:
    secret = b'{"Fault": {"Error": [{"Message": "Account 61 is inactive for Copperleaf"}]}}'
    reads = Egress(reads={f"{BASE}/preferences?minorversion=75": Response(status, secret)})
    with pytest.raises(q.QboError) as refused:
        await _transport(reads).book_close_date()
    assert refused.value.code == code
    assert "Copperleaf" not in str(refused.value) and "inactive for" not in repr(refused.value)
    writes = Egress(writes=[Response(status, secret)])
    with pytest.raises(q.QboError) as refused_write:
        await _transport(writes).create_journal_entry(ENTRY, "b1:e1")
    assert refused_write.value.code == code


async def test_the_writer_over_the_transport_posts_and_verifies_line_for_line() -> None:
    """The writer's whole post on the live transport: preflight reads, one write, the read-back."""
    egress = Egress(
        reads={
            f"{BASE}/preferences?minorversion=75": ok(
                {"Preferences": {"AccountingInfoPrefs": {}}}
            ),
            f"{BASE}/account/21?minorversion=75": ok({"Account": {"Active": True}}),
            f"{BASE}/account/61?minorversion=75": ok({"Account": {"Active": True}}),
            f"{BASE}/journalentry/48213?minorversion=75": ok(
                {
                    "JournalEntry": {
                        "Line": [
                            {
                                "Amount": "250.00",
                                "JournalEntryLineDetail": {
                                    "PostingType": "Credit",
                                    "AccountRef": {"value": "21"},
                                },
                            },
                            {
                                "Amount": "250.00",
                                "JournalEntryLineDetail": {
                                    "PostingType": "Debit",
                                    "AccountRef": {"value": "61"},
                                },
                            },
                        ]
                    }
                }
            ),
        },
        writes=[ok({"JournalEntry": {"Id": "48213"}})],
    )
    posted = await q.QuickBooksOnlineWriter(_transport(egress)).post(ENTRY, "b1:e1")
    assert posted == q.Posted("48213", True)
    assert [m for m, _, _, _ in egress.sent].count("WRITE") == 1
