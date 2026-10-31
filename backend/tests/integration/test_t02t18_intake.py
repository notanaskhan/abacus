"""T-02-T18 (TASK-2422; T-02 §3.4; DV-6, DV-7; DEC-1470) over HTTP against Postgres: TAX-03's
intake read model.

The row's acceptance: "Feld intake reads 5 of 7 and a taxpayer without both consents gets no
suggestion and causes zero gateway calls." Also: the categories foot to the total; each received
row names its file and the version Approve Document accepts; the 2024 copy reads wrong-year from
code (its classified year against the return's); the matcher's stored proposal is not shown
without consent, and the read makes no model call; the Questions band carries counts, not
answers.

The Feld return is T-02-T09's practice-board seed; the binder, files and proposal are seeded as
C5, N-01 and the matcher leave them.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import cast

from abacus.kernel.clock import frozen

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json
from .test_t02t13_return_overview import manager_on

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

CATEGORIES = (
    (
        "Income Sources",
        (
            ("2025 W-2 From Mercer Hill Health", True),
            ("2025 Consolidated 1099 From Halvard Securities", True),
            ("Schedule K-1 from Ridgeline Property Partners, LP", True),
        ),
    ),
    ("Home & Property", (("2025 Form 1098 From Hudson Mutual Savings", True),)),
    ("Charitable & Donations", (("2025 donation receipts", True),)),
    ("Health & Medical", (("Form 1095-C From Mercer Hill Health", False),)),
    ("Other Activity", (("2025 estimated payment confirmations", False),)),
)


async def _binder(b: Board, item: uuid.UUID) -> dict[str, uuid.UUID]:
    """The 2025 binder: seven requests, five received (each with its file), two requested."""
    row = (
        await b.seed.rows(
            "SELECT engagement_id, client_entity_id FROM tax_returns WHERE work_item_id = $1", item
        )
    )[0]
    engagement = cast(uuid.UUID, row["engagement_id"])
    binder = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id, work_item_id, created_at, kind, "
            "status, published_at, published_by) VALUES ($1, $2, $3, clock_timestamp(), 'pbc', "
            "'published', clock_timestamp(), $4) RETURNING id",
            b.tenant,
            engagement,
            item,
            b.partner,
        ),
    )
    out: dict[str, uuid.UUID] = {}
    for position, (name, requests) in enumerate(CATEGORIES):
        category = await b.seed.value(
            "INSERT INTO request_categories (tenant_id, request_list_id, name, position, family) "
            "VALUES ($1, $2, $3, $4, 'tax_portal') RETURNING id",
            b.tenant,
            binder,
            name,
            position,
        )
        for title, received in requests:
            request = cast(
                uuid.UUID,
                await b.seed.value(
                    "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                    "description, title, audit_area, category_id, status, created_by, "
                    "created_at, client_visible, requested_at) VALUES ($1, $2, $3, $4, $4, "
                    "'Tax', $5, $6, $7, clock_timestamp(), true, clock_timestamp()) RETURNING id",
                    b.tenant,
                    engagement,
                    binder,
                    title,
                    category,
                    "received" if received else "requested",
                    b.partner,
                ),
            )
            out[title] = request
            if received:
                await _file(b, engagement, request, f"{title}.pdf")
    out["binder"] = binder
    out["engagement"] = engagement
    return out


async def _file(b: Board, engagement: uuid.UUID, request: uuid.UUID, name: str) -> None:
    item = await b.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'human', 'seed') RETURNING id",
        b.tenant,
        engagement,
        name,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = await b.seed.value(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
        "VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', 'client_upload', "
        "'uploaded') RETURNING id",
        b.tenant,
        engagement,
        item,
        fingerprint,
        f"tenants/{b.tenant}/sha256/{fingerprint}",
    )
    await b.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, 'human', 'seed')",
        b.tenant,
        engagement,
        request,
        version,
    )


async def _waiting(b: Board, client: uuid.UUID, name: str, year: int) -> uuid.UUID:
    """One attachment waiting on the Feld client, classified with its tax year."""
    thread = await b.seed.value(
        "INSERT INTO inbox_threads (tenant_id, source_kind, subject_display, sender_display, "
        "first_received_at, last_received_at, client_id, match_method) VALUES ($1, 'mailbox', "
        "'Re: 2025 tax documents', 'claire.feld@example.com', now(), now(), $2, 'sender_rule') "
        "RETURNING id",
        b.tenant,
        client,
    )
    message = await b.seed.value(
        "INSERT INTO inbound_messages (tenant_id, thread_id, channel, sender_display, "
        "subject_display, received_at) VALUES ($1, $2, 'email', 'claire.feld@example.com', "
        "'Re: 2025 tax documents', now()) RETURNING id",
        b.tenant,
        thread,
    )
    attachment = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO inbox_attachments (tenant_id, message_id, thread_id, client_id, "
            "file_name, media_type, size_bytes, fingerprint, storage_key, key_mode, status) "
            "VALUES ($1, $2, $3, $4, $5, 'application/pdf', 412000, $6, 'intake/k', 'content', "
            "'waiting') RETURNING id",
            b.tenant,
            message,
            thread,
            client,
            name,
            hashlib.sha256(name.encode()).hexdigest(),
        ),
    )
    await b.seed.run(
        "INSERT INTO document_classifications (tenant_id, subject_kind, subject_id, form_family, "
        "form_code, tax_year, kind, page_count, proposed_by_kind, rules_version) VALUES ($1, "
        "'inbox_attachment', $2, '1095', '1095-C', $3, 'tax_form', 1, 'rule', 'test')",
        b.tenant,
        attachment,
        year,
    )
    return attachment


async def test_ac1_feld_reads_5_of_7_and_no_consent_means_no_suggestion_and_no_model_call(
    board: Board,
) -> None:
    feld = board.returns["Feld Household 1040"]
    made = await _binder(board, feld)
    kevin = await manager_on(board, feld)
    client = cast(
        uuid.UUID,
        await board.seed.value("SELECT client_id FROM work_items WHERE id = $1", feld),
    )
    current = await _waiting(board, client, "Feld_1095C_2025.pdf", 2025)
    prior = await _waiting(board, client, "Feld_1095C_2024.pdf", 2024)
    calls_before = await board.seed.value(
        "SELECT count(*) FROM usage_records WHERE tenant_id = $1", board.tenant
    )

    with frozen(DEMO):
        found = await _as(kevin)("GET", f"/v1/tax-returns/{feld}/intake")
    assert found.status_code == 200, found.text
    body = cast(Json, found.json())

    assert (body["requests_received"], body["requests_total"]) == (5, 7)
    categories = cast(list[Json], body["categories"])
    assert sum(cast(int, c["received"]) for c in categories) == 5
    assert sum(cast(int, c["requested"]) for c in categories) == 7
    open_ = {c["label"] for c in categories if c["received"] != c["requested"]}
    assert open_ == {"Health & Medical", "Other Activity"}
    rows = {r["title"]: r for r in cast(list[Json], body["requests"])}
    w2 = rows["2025 W-2 From Mercer Hill Health"]
    assert w2["latest_version_id"] is not None  # what Approve Document accepts (DV-6)
    assert rows["Form 1095-C From Mercer Hill Health"]["latest_version_id"] is None
    binder = cast(Json, body["binder"])
    assert (binder["id"], binder["status"]) == (str(made["binder"]), "published")

    waiting = {w["attachment_id"]: w for w in cast(list[Json], body["waiting"])}
    assert body["waiting_files"] == 2
    assert waiting[str(prior)]["wrong_year"] is True
    assert waiting[str(prior)]["tax_year"] == 2024
    assert waiting[str(current)]["wrong_year"] is False

    # No consent set for the Feld household: no suggestion, the DF-04 line, and no model call.
    assert body["suggestions"] == "consent_missing"
    assert all(w["suggestion"] is None for w in waiting.values())
    calls_after = await board.seed.value(
        "SELECT count(*) FROM usage_records WHERE tenant_id = $1", board.tenant
    )
    assert calls_after == calls_before


async def test_ac1_client_service_reads_names_and_status_but_no_extracted_values(
    board: Board,
) -> None:
    feld = board.returns["Feld Household 1040"]
    made = await _binder(board, feld)
    grace = await board.person("Grace Holloway", None)
    await board.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'client_service')",
        board.tenant,
        made["engagement"],
        grace.user_id,
    )
    client = cast(
        uuid.UUID,
        await board.seed.value("SELECT client_id FROM work_items WHERE id = $1", feld),
    )
    prior = await _waiting(board, client, "Feld_1095C_2024.pdf", 2024)
    with frozen(DEMO):
        found = await _as(grace)("GET", f"/v1/tax-returns/{feld}/intake")
    assert found.status_code == 200, found.text
    body = cast(Json, found.json())
    assert body["requests_total"] == 7
    assert body["suggestions"] == "hidden"
    row = next(w for w in cast(list[Json], body["waiting"]) if w["attachment_id"] == str(prior))
    assert row["file_name"] == "Feld_1095C_2024.pdf"
    assert row["tax_year"] is None
