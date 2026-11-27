# ac-test-author: ayushkbhatia
"""CV-2 (TASK-9001; DEC-6003; SPEC-700 W1; ADR-344; C-02-T18, T19, T24, T25): the W1 posting path
end to end on the migrated Postgres, through the HTTP routes a person uses and the workflow's
activity, with the QuickBooks company in memory (`FakeQboTransport`).

Main CI measured `adjustments/posting.py` at 37% and `posting_recovery.py` at 30%: no test ran a
batch. These do:

- The four switches, each a person's act through its route: the firm switch (security admin,
  fresh MFA), the engagement's `posting_enabled` (partner), the client owner's write grant
  (POR-16), with the registry entry released for the test only.
- A dry run reads and writes nothing; a batch holds for ten seconds and undo voids it; a batch
  posts each entry once (48213, 48214), sets the closing date once, and a replay writes nothing.
- A provider failure leaves the entry `failed_post` with an issue; its retry re-posts it once.
- Each switch turned off refuses the next batch with its reason.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.storage import s3_client
from abacus.modules.adjustments import posting
from abacus.modules.evidence import records
from abacus.modules.integrations import capabilities, writes
from abacus.modules.integrations.api import FakeQboTransport, W1Refused

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

GRANT = {
    "capability_id": "ledger_post_journal_entries",
    "consent_copy_version": "por16.qbo.post_entries.v2",
}


@dataclass
class World:
    net: Net
    tenant: uuid.UUID
    partner: Person
    security: Person
    owner: Person
    site: Site
    item: uuid.UUID
    connection: uuid.UUID
    qbo: FakeQboTransport
    started: list[tuple[str, ...]]

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def post(self, path: str, who: Person | None = None, body: object = None):  # noqa: ANN201
        return await self.net.call(
            "POST",
            path,
            who or self.partner,
            body=cast(dict[str, object], body or {}),
            headers=self.net.keyed(),
        )


RECORDS = "cv2-w1-records"


@pytest.fixture(scope="module")
def record_store(s3_settings: dict[str, str]) -> Iterator[None]:
    """W1's request, response and read-back bodies are stored write-once (Object Lock)."""
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=RECORDS, ObjectLockEnabledForBucket=True)
    yield
    del client


@pytest.fixture(autouse=True)
def wired_records(record_store: None, s3_settings: dict[str, str]) -> Iterator[None]:
    del record_store
    records.configure_records(
        s3_client(
            endpoint_url=s3_settings["endpoint_url"],
            access_key=s3_settings["access_key"],
            secret_key=s3_settings["secret_key"],
            region=s3_settings["region"],
        ),
        RECORDS,
    )
    yield
    records.reset_records()


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """W1's registry entry is `enabled: false` until the write path is released (ADR-344 §10);
    the test releases it in-process only, so every other switch is exercised for real."""
    entry = capabilities.write_capability(writes.W1_CAPABILITY)
    assert entry is not None and not entry.enabled
    on = entry.model_copy(update={"enabled": True})

    def lookup(key: str) -> object:
        return on if key == writes.W1_CAPABILITY else capabilities.write_capability(key)

    for module in (
        "abacus.modules.integrations.writes",
        "abacus.modules.integrations.w1_switches",
    ):
        monkeypatch.setattr(f"{module}.write_capability", lookup)
    yield


@pytest.fixture
async def world(
    net: Net, seed: Seeder, released: None, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[World]:
    del released
    tenant = await seed.firm()
    for flag in ("adjustments.posting", "closes.gl_console"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'CV-2')",
            tenant,
            flag,
        )
    partner = await seed.person(tenant)
    security = await seed.person(tenant, "security_admin")
    site = await seed.site(tenant, partner.user_id, "Copperleaf")
    await seed.member(site, partner, "engagement_partner")
    owner = await seed.client_contact(site)
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'close', "
            "'August 2026 close', '2026-08-01', '2026-08-31', $5) RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            partner.user_id,
        ),
    )
    connection = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO connections (tenant_id, client_entity_id, provider, status, created_by) "
            "VALUES ($1, $2, 'quickbooks_online', 'active', 'test-seed') RETURNING id",
            tenant,
            site.entity_id,
        ),
    )
    qbo = FakeQboTransport(accounts={"6100": True, "2100": True})
    saved = list(posting._transports)  # pyright: ignore[reportPrivateUsage] -- restored below
    posting.register_qbo_transport(lambda _t, c: qbo if c == connection else None)
    started: list[tuple[str, ...]] = []

    async def start_posting(tenant_id: uuid.UUID, batch_id: uuid.UUID) -> None:
        started.append(("batch", str(tenant_id), str(batch_id)))

    async def start_retry(tenant_id: uuid.UUID, retried: object) -> None:
        started.append(("retry", str(tenant_id), str(retried)))

    monkeypatch.setattr(posting, "start_posting", start_posting)
    monkeypatch.setattr(posting, "start_retry", start_retry)
    yield World(net, tenant, partner, security, owner, site, item, connection, qbo, started)
    posting._transports[:] = saved  # pyright: ignore[reportPrivateUsage] -- restore the slot


async def _entry(
    w: World, number: int, amount: str = "250.00", *, credit_account: str = "2100"
) -> uuid.UUID:
    entry = uuid.uuid4()
    await w.seed.run(
        "INSERT INTO proposed_entries (id, tenant_id, engagement_id, work_item_id, kind, number, "
        "ref, threshold_result, is_attest_client, status, amount, txn_date, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, $4, 'aje', $5, $6, 'within_threshold', false, "
        "'proposed', $7, '2026-08-31', 'human', $8)",
        entry,
        w.tenant,
        w.site.engagement_id,
        w.item,
        number,
        f"AJE-{number}",
        amount,
        str(w.partner.user_id),
    )
    await w.seed.run(  # both lines in one statement: the entry balances when it lands
        "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, entry_id, "
        "line_no, account_code, debit, credit) VALUES ($1, $2, $3, $4, 1, '6100', $5, 0), "
        "($1, $2, $3, $4, 2, $6, 0, $5)",
        w.tenant,
        w.site.engagement_id,
        w.item,
        entry,
        Decimal(amount),
        credit_account,
    )
    # Lines go in while the entry is proposed (an approved entry is locked); then a person's
    # approval, as A-06's decision service records it.
    await w.seed.run("UPDATE proposed_entries SET status = 'approved' WHERE id = $1", entry)
    return entry


async def _switches_on(w: World) -> None:
    on = await w.post(
        "/v1/write-capabilities/ledger_post_journal_entries:enable", w.security, {"reason": "CV-2"}
    )
    assert on.status_code == 200, on.text
    assert on.json()["enabled"] is True
    settings = await w.net.call(
        "PUT",
        f"/v1/engagements/{w.site.engagement_id}/ledger-settings",
        w.partner,
        body={"connection_id": str(w.connection), "posting_enabled": True},
    )
    assert settings.status_code == 200, settings.text
    grant = await w.post(f"/v1/portal/connections/{w.connection}/write-grants", w.owner, GRANT)
    assert grant.status_code == 201, grant.text


async def _versions(w: World, entries: list[uuid.UUID]) -> dict[str, int]:
    rows = await w.seed.rows(
        "SELECT id, version FROM proposed_entries WHERE id = ANY($1::uuid[])", entries
    )
    return {str(r["id"]): int(r["version"]) for r in rows}


async def _batch(w: World, entries: list[uuid.UUID], *, closing: bool = True) -> dict[str, object]:
    made = await w.post(
        f"/v1/work-items/{w.item}/posting-batches",
        body={
            "entry_ids": [str(e) for e in entries],
            "seen_versions": await _versions(w, entries),
            "set_closing_date": closing,
        },
    )
    assert made.status_code == 202, made.text
    return cast(dict[str, object], made.json())


def _tenant(w: World) -> TenantContext:
    return TenantContext(w.tenant, "human", str(w.partner.user_id))


async def _past_the_hold(w: World, batch_id: object) -> None:
    """The ten-second hold, elapsed (the grant's `not_before` moved back, as time would; the
    grant's own trigger allows only use or void, so the move is made with triggers off)."""
    await w.seed.run_untriggered(
        "UPDATE approval_grants SET not_before = now() - interval '1 second' "
        "WHERE id = (SELECT approval_grant_id FROM posting_batches WHERE id = $1)",
        uuid.UUID(str(batch_id)),
    )


async def test_cv2_a_dry_run_checks_every_entry_and_writes_nothing(world: World) -> None:
    w = world
    await _switches_on(w)
    ok, unmapped = await _entry(w, 1), await _entry(w, 2, credit_account="9999")
    found = await w.post(
        f"/v1/work-items/{w.item}/posting-batches:dry-run",
        body={"entry_ids": [str(ok), str(unmapped)]},
    )
    assert found.status_code == 200, found.text
    body = found.json()
    assert (body["entry_count"], body["total_amount"], body["closing_date_target"]) == (
        2,
        "500.00",
        "2026-08-31",
    )
    assert body["ledger_label"] == "QuickBooks Online"
    assert body["client_entity_name"] == f"Entity {w.site.marker}"
    assert [(r["entry_id"], r["ok"], r["failed_check"]) for r in body["results"]] == [
        (str(ok), True, None),
        (str(unmapped), False, "active_accounts"),  # not in the company: inactive
    ]
    assert w.qbo.writes == []
    assert (
        await w.seed.value("SELECT count(*) FROM posting_batches WHERE tenant_id = $1", w.tenant)
        == 0
    )


async def test_cv2_a_batch_posts_each_entry_once_and_sets_the_closing_date_once(
    world: World,
) -> None:
    w = world
    await _switches_on(w)
    entries = [await _entry(w, 1), await _entry(w, 2, "125.50")]
    batch = await _batch(w, entries)
    assert (batch["batch_code"], batch["status"], batch["entry_count"]) == (
        "2026-08-A",
        "proposed",
        2,
    )
    assert batch["total_amount"] == "375.50" and batch["undo_until"] is not None
    assert w.started == [("batch", str(w.tenant), str(batch["batch_id"]))]

    # Inside the hold the single gate refuses to deliver (the dispatcher retries).
    from abacus.modules.identity.api import GrantNotYetDue

    with pytest.raises(GrantNotYetDue):
        await posting.run_batch(w.tenant, uuid.UUID(str(batch["batch_id"])))
    assert w.qbo.writes == []

    await _past_the_hold(w, batch["batch_id"])
    status = await posting.run_batch(w.tenant, uuid.UUID(str(batch["batch_id"])))
    assert status == "posted"
    assert w.qbo.writes == [
        ("POST JournalEntry", "AJE-1"),
        ("POST JournalEntry", "AJE-2"),
        ("POST Preferences.BookCloseDate", "2026-08-31"),
    ]
    rows = await w.seed.rows(
        "SELECT ref, status, external_txn_ref FROM proposed_entries WHERE id = ANY($1::uuid[]) "
        "ORDER BY number",
        entries,
    )
    assert [(r["ref"], r["status"], r["external_txn_ref"]) for r in rows] == [
        ("AJE-1", "posted", "48213"),
        ("AJE-2", "posted", "48214"),
    ]
    drawer = await w.net.call("GET", f"/v1/posting-batches/{batch['batch_id']}", w.partner)
    assert drawer.status_code == 200, drawer.text  # CLS-11 b2's drawer (ED-344: was a 500)
    got = drawer.json()
    assert (got["status"], got["first_external_ref"], got["last_external_ref"]) == (
        "posted",
        "48213",
        "48214",
    )
    assert (got["entry_count"], got["approved_count"], got["amount"]) == (2, 2, "375.50")
    view = await posting.batch_view(_tenant(w), uuid.UUID(str(batch["batch_id"])))
    assert view["undo_until"] is None and view["failure_count"] == 0
    closing = await w.seed.rows(
        "SELECT closing_date, source FROM closing_date_events WHERE posting_batch_id = $1",
        uuid.UUID(str(batch["batch_id"])),
    )
    assert [(str(r["closing_date"]), r["source"]) for r in closing] == [
        ("2026-08-31", "set_by_accrued")
    ]
    writes_logged = await w.seed.rows(
        "SELECT operation, status, external_ref FROM ledger_write_operations "
        "WHERE tenant_id = $1 ORDER BY started_at",
        w.tenant,
    )
    assert [(r["operation"], r["status"]) for r in writes_logged] == [
        ("create_journal_entry", "verified"),
        ("create_journal_entry", "verified"),
        ("set_closing_date", "verified"),
    ]

    # A replay of the finished batch writes nothing more.
    assert await posting.run_batch(w.tenant, uuid.UUID(str(batch["batch_id"]))) == "posted"
    assert len(w.qbo.writes) == 3

    log = await w.net.call(
        "GET", f"/v1/client-entities/{w.site.entity_id}/posting-batches", w.partner
    )
    assert log.status_code == 200, log.text  # CLS-11's log (ED-344: was a 500)
    assert [(r["batch_code"], r["status"]) for r in log.json()["items"]] == [
        ("2026-08-A", "posted")
    ]
    console = await w.net.call(
        "GET", f"/v1/client-entities/{w.site.entity_id}/ledger-console", w.partner
    )
    assert console.status_code == 200, console.text


async def test_cv2_the_same_key_answers_the_same_batch_and_the_next_takes_b(world: World) -> None:
    w = world
    await _switches_on(w)
    first = [await _entry(w, 1)]
    body = {
        "entry_ids": [str(first[0])],
        "seen_versions": await _versions(w, first),
        "set_closing_date": False,
    }
    key = w.net.keyed()
    path = f"/v1/work-items/{w.item}/posting-batches"
    one = await w.net.call("POST", path, w.partner, body=body, headers=key)
    again = await w.net.call("POST", path, w.partner, body=body, headers=key)
    assert one.status_code == again.status_code == 202, (one.text, again.text)
    assert one.json()["batch_id"] == again.json()["batch_id"]
    assert len(w.started) == 1  # the workflow starts once
    second = await _batch(w, [await _entry(w, 2)], closing=False)
    assert second["batch_code"] == "2026-08-B"


async def test_cv2_undo_inside_the_hold_voids_the_grant_and_releases_the_entries(
    world: World,
) -> None:
    w = world
    await _switches_on(w)
    entries = [await _entry(w, 1)]
    batch = await _batch(w, entries)
    undone = await w.post(f"/v1/posting-batches/{batch['batch_id']}/undo")
    assert undone.status_code == 200, undone.text
    assert undone.json()["entries"] == []
    row = await w.seed.rows(
        "SELECT posting_batch_id, status FROM proposed_entries WHERE id = $1", entries[0]
    )
    assert (row[0]["posting_batch_id"], row[0]["status"]) == (None, "approved")
    # The voided grant never delivers, so the run writes nothing.
    await _past_the_hold(w, batch["batch_id"])
    from abacus.modules.adjustments.posting_errors import ApprovalGrantMismatch

    with pytest.raises(ApprovalGrantMismatch):
        await posting.run_batch(w.tenant, uuid.UUID(str(batch["batch_id"])))
    assert w.qbo.writes == []
    # A second undo has no grant left to void.
    twice = await w.post(f"/v1/posting-batches/{batch['batch_id']}/undo")
    assert twice.status_code == 409, twice.text


async def test_cv2_a_provider_failure_is_failed_post_and_its_retry_posts_once(
    world: World,
) -> None:
    w = world
    await _switches_on(w)
    entries = [await _entry(w, 1), await _entry(w, 2)]
    w.qbo.script.append(None)  # AJE-1 posts
    w.qbo.script.append("rate_limited")  # AJE-2 is refused by QuickBooks (429)
    batch = await _batch(w, entries)
    await _past_the_hold(w, batch["batch_id"])
    batch_id = uuid.UUID(str(batch["batch_id"]))
    assert await posting.run_batch(w.tenant, batch_id) == "failed_post"
    assert w.qbo.writes == [("POST JournalEntry", "AJE-1")]  # no closing date after a failure
    rows = await w.seed.rows(
        "SELECT ref, status FROM proposed_entries WHERE id = ANY($1::uuid[]) ORDER BY number",
        entries,
    )
    assert [(r["ref"], r["status"]) for r in rows] == [
        ("AJE-1", "posted"),
        ("AJE-2", "failed_post"),
    ]
    view = await posting.batch_view(_tenant(w), batch_id)
    assert view["status"] == "failed_post" and view["failure_count"] == 1
    listed = cast(list[dict[str, object]], view["entries"])
    assert [(e["ref"], e["failure"]) for e in listed] == [
        ("AJE-1", None),
        ("AJE-2", "rate_limited"),
    ]

    retried = await w.post(f"/v1/posting-batches/{batch_id}/entries/{entries[1]}/retry")
    assert retried.status_code == 202, retried.text
    assert w.started[-1][0] == "retry"
    from abacus.modules.adjustments import posting_recovery

    grant = await w.seed.value(
        "SELECT id FROM approval_grants WHERE subject_id = $1 AND used_at IS NULL "
        "AND voided_at IS NULL ORDER BY created_at DESC LIMIT 1",
        batch_id,
    )
    await w.seed.run_untriggered(
        "UPDATE approval_grants SET not_before = now() - interval '1 second' WHERE id = $1", grant
    )
    status = await posting_recovery.run_retry(
        w.tenant, batch_id, entries[1], cast(uuid.UUID, grant)
    )
    assert status in ("posted", "failed_post")
    assert w.qbo.writes[1] == ("POST JournalEntry", "AJE-2")
    after = await w.seed.value("SELECT status FROM proposed_entries WHERE id = $1", entries[1])
    assert after == "posted"


@pytest.mark.parametrize(
    ("switch", "reason"),
    [
        ("firm", "write_capability_disabled"),
        ("engagement", "posting_not_enabled"),
        ("grant", "write_grant_missing"),
    ],
)
async def test_cv2_each_switch_off_refuses_the_next_batch(
    world: World, switch: str, reason: str
) -> None:
    w = world
    await _switches_on(w)
    if switch == "firm":
        off = await w.post(
            "/v1/write-capabilities/ledger_post_journal_entries:disable", w.security, {}
        )
        assert off.status_code == 200 and off.json()["enabled"] is False, off.text
    elif switch == "engagement":
        off = await w.net.call(
            "PUT",
            f"/v1/engagements/{w.site.engagement_id}/ledger-settings",
            w.partner,
            body={"connection_id": str(w.connection), "posting_enabled": False},
        )
        assert off.status_code == 200, off.text
    else:
        off = await w.net.call(
            "DELETE", f"/v1/portal/connections/{w.connection}/write-grants/current", w.owner
        )
        assert off.status_code == 200, off.text
    entries = [await _entry(w, 1)]
    # The batch is a person's approval and is still made; the switches are re-read on every
    # entry when it runs (ADR-344 §3), so the run is refused, audited, and writes nothing.
    batch = await _batch(w, entries)
    await _past_the_hold(w, batch["batch_id"])
    with pytest.raises(W1Refused) as refused:
        await posting.run_batch(w.tenant, uuid.UUID(str(batch["batch_id"])))
    assert refused.value.facts == {"reason": reason}
    assert w.qbo.writes == []
    assert (
        await w.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'write_capability.refused'",
            w.tenant,
        )
        == 1
    )
    assert (
        await w.seed.value("SELECT status FROM proposed_entries WHERE id = $1", entries[0])
        == "approved"
    )


async def test_cv2_a_stale_version_and_a_non_postable_entry_are_refused(world: World) -> None:
    w = world
    await _switches_on(w)
    entry = await _entry(w, 1)
    stale = await w.post(
        f"/v1/work-items/{w.item}/posting-batches",
        body={
            "entry_ids": [str(entry)],
            "seen_versions": {str(entry): 99},
            "set_closing_date": False,
        },
    )
    assert stale.status_code == 409, stale.text
    await w.seed.run("UPDATE proposed_entries SET status = 'proposed' WHERE id = $1", entry)
    locked = await w.post(
        f"/v1/work-items/{w.item}/posting-batches",
        body={
            "entry_ids": [str(entry)],
            "seen_versions": await _versions(w, [entry]),
            "set_closing_date": False,
        },
    )
    assert locked.status_code == 409, locked.text
    assert (
        await w.seed.value("SELECT count(*) FROM posting_batches WHERE tenant_id = $1", w.tenant)
        == 0
    )


async def _posted(w: World, entries: list[uuid.UUID]) -> uuid.UUID:
    batch = await _batch(w, entries)
    await _past_the_hold(w, batch["batch_id"])
    batch_id = uuid.UUID(str(batch["batch_id"]))
    await posting.run_batch(w.tenant, batch_id)
    return batch_id


async def test_cv2_a_closed_period_holds_the_entry_and_re_dating_releases_it(world: World) -> None:
    w = world
    await _switches_on(w)
    entry = await _entry(w, 1)
    w.qbo.closed_on = date(2026, 8, 31)
    w.qbo.script.append("closing_date_locked")
    batch_id = await _posted(w, [entry])
    conflicts = await w.seed.rows(
        "SELECT id, status FROM closing_date_conflicts WHERE posting_batch_id = $1", batch_id
    )
    assert [r["status"] for r in conflicts] == ["open"]
    conflict = conflicts[0]["id"]
    assert (
        await w.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'posting_batch.failed'",
            w.tenant,
        )
        == 0
    )  # a closing date is its own conflict, not a CLS-06 failure issue

    held = await w.post(f"/v1/posting-batches/{batch_id}/entries/{entry}/retry")
    assert held.status_code == 409 and "closing_date_conflict" in held.text, held.text

    redated = await w.post(
        f"/v1/closing-date-conflicts/{conflict}/redate",
        body={"new_date": "2026-09-01", "reason": "August is closed in QuickBooks"},
    )
    assert redated.status_code == 200, redated.text
    assert redated.json()["status"] == "redated"
    row = (
        await w.seed.rows(
            "SELECT txn_date, posting_batch_id, status FROM proposed_entries WHERE id = $1", entry
        )
    )[0]
    assert (str(row["txn_date"]), row["posting_batch_id"]) == ("2026-09-01", None)
    assert row["status"] not in ("approved", "client_approved")  # re-approved before it posts
    again = await w.post(
        f"/v1/closing-date-conflicts/{conflict}/redate",
        body={"new_date": "2026-09-02", "reason": "twice"},
    )
    assert again.status_code == 409, again.text


async def test_cv2_asking_the_client_to_lift_the_closing_date(world: World) -> None:
    w = world
    await _switches_on(w)
    entry = await _entry(w, 1)
    w.qbo.closed_on = date(2026, 8, 31)
    w.qbo.script.append("closing_date_locked")
    batch_id = await _posted(w, [entry])
    conflict = await w.seed.value(
        "SELECT id FROM closing_date_conflicts WHERE posting_batch_id = $1", batch_id
    )
    # With no approver of record on the engagement there is nobody to ask: 404, nothing sent,
    # and the conflict stays open for a re-date.
    asked = await w.post(f"/v1/closing-date-conflicts/{conflict}/ask-client")
    assert asked.status_code == 404, asked.text
    assert (
        await w.seed.value("SELECT status FROM closing_date_conflicts WHERE id = $1", conflict)
        == "open"
    )
    assert (
        await w.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'closing_date_conflict.client_asked'",
            w.tenant,
        )
        == 0
    )


async def test_cv2_a_posted_entry_reverses_as_a_new_proposed_entry(world: World) -> None:
    w = world
    await _switches_on(w)
    entry = await _entry(w, 1)
    await _posted(w, [entry])
    reversed_ = await w.post(
        f"/v1/proposed-entries/{entry}/reverse", body={"reverse_on": "2026-09-01"}
    )
    assert reversed_.status_code in (200, 201), reversed_.text
    rows = await w.seed.rows(
        "SELECT e.id, e.status, e.txn_date, l.account_code, l.debit, l.credit "
        "FROM proposed_entries e JOIN proposed_entry_lines l ON l.entry_id = e.id "
        "WHERE e.reversal_of_id = $1 ORDER BY l.line_no",
        entry,
    )
    assert [(r["account_code"], str(r["debit"]), str(r["credit"])) for r in rows] == [
        ("6100", "0.00", "250.00"),
        ("2100", "250.00", "0.00"),
    ]
    # A reversal is a new entry for a person to review and approve (never auto-approved).
    assert {r["status"] for r in rows} == {"review_required"}
    assert str(rows[0]["txn_date"]) == "2026-09-01"
    assert (
        len(w.qbo.writes) == 2
    )  # nothing more written: the reversal posts only when a person does


async def test_cv2_export_instead_is_deterministic_and_recording_externally(world: World) -> None:
    w = world
    await _switches_on(w)
    one, two = await _entry(w, 1), await _entry(w, 2, "80.00")
    path = f"/v1/work-items/{w.item}/proposed-entries.xlsx"
    first = await w.net.call("GET", path, w.partner)
    second = await w.net.call("GET", path, w.partner)
    assert first.status_code == 200, first.text
    assert first.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert first.content == second.content and first.content[:2] == b"PK"
    unmatched = await w.post(
        f"/v1/proposed-entries/{one}/record-external", body={"match_ref": "QBO JE 9001"}
    )
    assert unmatched.status_code == 409 and "ledger_match_not_found" in unmatched.text
    recorded = await w.post(
        f"/v1/proposed-entries/{one}/record-external",
        body={"evidence_version_id": str(w.site.version_id)},
    )
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["status"] == "recorded_externally"
    assert (
        await w.seed.value(
            "SELECT recorded_externally_evidence_id FROM proposed_entries WHERE id = $1", one
        )
        == w.site.version_id
    )
    assert (
        await w.seed.value("SELECT status FROM proposed_entries WHERE id = $1", two) == "approved"
    )
    assert w.qbo.writes == []


async def test_cv2_the_firms_posting_settings_are_versioned(world: World) -> None:
    w = world
    path = "/v1/integrations/quickbooks_online/settings/gl-posting"
    first = await w.net.call("GET", path, w.security)
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["memo_prefix"], body["version"], body["human_approved_only"]) == (
        "Accrued",
        1,
        True,
    )
    assert body["post_as"].startswith("Firm ")  # the firm's own name until someone sets it
    put = await w.net.call(
        "PUT",
        path,
        w.security,
        body={
            "memo_prefix": " Hale CAS ",
            "post_as": "Brightwater Hale LLP",
            "expected_version": 1,
        },
    )
    assert put.status_code == 200, put.text
    assert (put.json()["memo_prefix"], put.json()["version"]) == ("Hale CAS", 1)
    again = await w.net.call(
        "PUT",
        path,
        w.security,
        body={"memo_prefix": "Hale", "post_as": "Brightwater Hale LLP", "expected_version": 1},
    )
    assert again.status_code == 200 and again.json()["version"] == 2, again.text
    stale = await w.net.call(
        "PUT",
        path,
        w.security,
        body={"memo_prefix": "Old", "post_as": "Brightwater Hale LLP", "expected_version": 1},
    )
    assert stale.status_code == 409 and "version_conflict" in stale.text, stale.text
    refused = await w.net.call(
        "PUT",
        path,
        w.partner,
        body={"memo_prefix": "X", "post_as": "Y", "expected_version": 2},
    )
    assert refused.status_code == 403, refused.text
    from abacus.modules.integrations.w1_switches import memo_prefix_of

    assert await memo_prefix_of(_tenant(w)) == "Hale"
    no_mfa = await w.net.call(
        "POST",
        "/v1/write-capabilities/ledger_post_journal_entries:enable",
        w.security,
        body={},
        mfa=False,
        headers=w.net.keyed(),
    )
    assert no_mfa.status_code in (401, 403, 409), no_mfa.text
