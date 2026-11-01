"""T-02-T20 (TASK-2423; T-02 §3.6; DEC-78, DEC-88; DEC-1471) against Postgres: the K-1 package
core.

The row's acceptance: "Shared Ridgeline drafts block Feld final approval and no client principal
can reach a draft package or document." Also: a draft K-1 set lands as one package per recipient
with documents marked draft and box lines; a full TIN refuses the set; a later set supersedes a
draft; the share files an `internal_handoff` copy in Feld's scope and the dependency row; a
details change is decided once, by a person.

The Ridgeline 1065 and Feld 1040 are T-02-T09's practice-board seed. The engine PDFs are seeded as
the bridge leaves them (an evidence version and its `pdfs` sync event), so no object store is
needed; the set is applied as the bridge's `k1_set` upload applies it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from typing import cast

import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import approval, k1_packages
from abacus.modules.tax.k1_packages import parse_k1_set

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json
from .test_t02t13_return_overview import manager_on

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

RECIPIENTS = (
    ("P01", "Jonah Feld", "lp", "1111"),
    ("P02", "Meera Shah", "lp", "2222"),
)


async def _pdf(b: Board, item: uuid.UUID, name: str) -> None:
    """An engine PDF on the issuing return, as the bridge files it."""
    row = (
        await b.seed.rows(
            "SELECT w.engagement_id, w.client_id FROM work_items w WHERE w.id = $1", item
        )
    )[0]
    evidence = await b.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, client_id, work_item_id, title, "
        "folder_kind, created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, $5, "
        "'deliverables', 'human', 'seed') RETURNING id",
        b.tenant,
        row["engagement_id"],
        row["client_id"],
        item,
        name,
    )
    fingerprint = hashlib.sha256(name.encode()).hexdigest()
    version = await b.seed.value(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method, "
        "pulled_at, channel) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
        "'engine_import', 'imported', now(), 'import') RETURNING id",
        b.tenant,
        row["engagement_id"],
        evidence,
        fingerprint,
        f"tenants/{b.tenant}/sha256/{fingerprint}",
    )
    await b.seed.run(
        "INSERT INTO engine_sync_events (tenant_id, return_id, engine_return_id, kind, "
        "actor_kind, actor_user_id, file_name, summary) VALUES ($1, $2, '2025P:Ridgeline', "
        "'pdfs', 'human', $3, $4, $5::jsonb)",
        b.tenant,
        item,
        b.partner,
        name,
        json.dumps({"pdf_kind": "k1", "evidence_version_id": str(version)}),
    )


def _set(*, final: bool = False, tin: str | None = None) -> bytes:
    return json.dumps(
        {
            "engine_return_id": "2025P:Ridgeline",
            "version": 2,
            "is_final": final,
            "form": "1065",
            "tax_year": 2025,
            "recipients": [
                {
                    "ref": ref,
                    "name": name,
                    "kind": kind,
                    "tin_last4": tin or last4,
                    "tin_kind": "ssn",
                    "k3": "included",
                    "states": ["IL"],
                    "documents": [
                        {"kind": "k1", "file_name": f"2025P_Ridgeline_V2_k1_{ref.lower()}.pdf"}
                    ],
                    "box_lines": [
                        {
                            "document_kind": "k1",
                            "box_code": "2",
                            "description": "Net rental real estate income",
                            "amount": "12500.00",
                        }
                    ],
                }
                for ref, name, kind, last4 in RECIPIENTS
            ],
        }
    ).encode()


async def _apply(b: Board, who: AuthContext, item: uuid.UUID, content: bytes) -> None:
    found = parse_k1_set(content)
    event = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO engine_sync_events (tenant_id, return_id, engine_return_id, kind, "
            "actor_kind, actor_user_id, summary) VALUES ($1, $2, '2025P:Ridgeline', 'k1_set', "
            "'human', $3, '{}'::jsonb) RETURNING id",
            b.tenant,
            item,
            who.user_id,
        ),
    )
    async with uow(who.tenant) as tx:
        await k1_packages.apply_k1_set(tx, who, item, found, event)


async def _ridgeline_with_drafts(b: Board) -> tuple[uuid.UUID, uuid.UUID, AuthContext]:
    ridgeline = b.returns["Ridgeline Partners 1065"]
    feld = b.returns["Feld Household 1040"]
    samuel = await manager_on(b, ridgeline)
    await b.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) SELECT $1, "
        "engagement_id, $3, 'manager' FROM tax_returns WHERE work_item_id = $2 "
        "ON CONFLICT DO NOTHING",
        b.tenant,
        feld,
        samuel.user_id,
    )
    # The sharer holds a function on the issuing return (the matrix's `function_in`).
    await b.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) SELECT $1, $2, engagement_id, $3, 'manager_reviewer', $3 "
        "FROM tax_returns WHERE work_item_id = $2",
        b.tenant,
        ridgeline,
        samuel.user_id,
    )
    for ref, *_ in RECIPIENTS:
        await _pdf(b, ridgeline, f"2025P_Ridgeline_V2_k1_{ref.lower()}.pdf")
    await _apply(b, samuel, ridgeline, _set())
    return ridgeline, feld, samuel


async def test_ac1_shared_ridgeline_drafts_block_feld_and_no_client_reaches_a_draft(
    board: Board,
) -> None:
    ridgeline, feld, samuel = await _ridgeline_with_drafts(board)
    await board.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.k1_release', 'true', 'test-seed', 'T-02-T20')",
        board.tenant,
    )
    with frozen(DEMO):
        listed = await _as(samuel)("GET", f"/v1/tax-returns/{ridgeline}/k1-packages")
    assert listed.status_code == 200, listed.text
    body = cast(Json, listed.json())
    rows = cast(list[Json], body["items"])
    assert [r["recipient_name"] for r in rows] == ["Jonah Feld", "Meera Shah"]
    assert cast(dict[str, int], body["counts"]) == {"draft": 2}
    assert all(cast(list[Json], r["documents"])[0]["is_draft"] for r in rows)

    shared = await k1_packages.share_internal(
        samuel, ridgeline, [uuid.UUID(cast(str, r["id"])) for r in rows], [feld]
    )
    assert shared == 2
    blockers = [b.kind for b in (await approval.eligibility(samuel, feld)).blockers]
    assert blockers.count("draft_k1") == 2
    copies = await board.seed.rows(
        "SELECT v.channel, i.work_item_id FROM k1_handoffs h JOIN evidence_versions v "
        "ON v.id = h.target_evidence_version_id "
        "JOIN evidence_items i ON i.id = v.evidence_item_id "
        "WHERE h.target_work_item_id = $1",
        feld,
    )
    assert {(r["channel"], r["work_item_id"]) for r in copies} == {("internal_handoff", feld)}
    with frozen(DEMO):
        overview = await _as(samuel)("GET", f"/v1/tax-returns/{feld}/overview")
    deps = cast(list[Json], cast(Json, overview.json())["k1_dependencies"])
    assert [(d["source_return_id"], d["blocking"]) for d in deps] == [
        (str(ridgeline), True),
        (str(ridgeline), True),
    ]

    # No client principal reaches a draft package or document: the firm routes answer 404 to a
    # client, and the portal's K-1 routes stay closed to drafts.
    client = replace(samuel, client=True)  # the same person, signed in through the portal
    package_id = cast(str, rows[0]["id"])
    first_document = cast(list[Json], rows[0]["documents"])[0]["id"]
    for path in (
        f"/v1/tax-returns/{ridgeline}/k1-packages",
        f"/v1/k1-packages/{package_id}",
        f"/v1/k1-packages/{package_id}/documents/{first_document}",
    ):
        answered = await _as(client)("GET", path)
        assert answered.status_code == 404, path
    portal = await _as(client)("GET", f"/v1/portal/k1s/{package_id}")
    assert portal.status_code in (404, 501)


async def test_ac1_a_full_tin_refuses_the_set_and_a_later_set_supersedes_the_draft(
    board: Board,
) -> None:
    ridgeline, _feld, samuel = await _ridgeline_with_drafts(board)
    with pytest.raises(ValueError, match="full_tin"):
        parse_k1_set(_set(tin="900-12-3456"))  # a reserved 9xx area: never a real SSN
    await _apply(board, samuel, ridgeline, _set(final=True))
    rows = await board.seed.rows(
        "SELECT r.engine_ref, p.version_no, p.status, p.is_final_set FROM k1_packages p "
        "JOIN k1_recipients r ON r.id = p.recipient_id WHERE p.work_item_id = $1 "
        "ORDER BY r.engine_ref, p.version_no",
        ridgeline,
    )
    assert [(r["engine_ref"], r["version_no"], r["status"]) for r in rows] == [
        ("P01", 1, "superseded"),
        ("P01", 2, "draft"),
        ("P02", 1, "superseded"),
        ("P02", 2, "draft"),
    ]
    check = await k1_packages.release_check(samuel, ridgeline)
    assert not check.eligible and "not_final_approved" in check.failing
    lines = await board.seed.value(
        "SELECT count(*) FROM k1_box_lines l JOIN k1_packages p ON p.id = l.package_id "
        "WHERE p.work_item_id = $1",
        ridgeline,
    )
    assert lines == 4
