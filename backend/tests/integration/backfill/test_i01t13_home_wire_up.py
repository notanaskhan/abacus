"""I-01-T13: HOME-01 lite's row targets (I-01 AC2.4, DEC-803).

With `home.approvals` off, a Waiting-on-you row opens its host gate. The `evidence_review` rows
(SPEC-004's review queue) carry a `subject_route` from assurance's presenter: an upload on an
assurance PBC list opens AUD-03 on that audit with the item; an upload on any other list (a tax
binder) opens BND-02 on the binder with the request. The SPA resolves the code through its
manifest (apps/web/src/screens/HOME-01/hosts.ts), and only opaque ids travel (ADR-031).

Built on P-04-T17's firm (Ashford and Bayside; Daniel the EP, Hannah the manager, Lena staff).
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.modules.assurance.review_gates import subject_route

from .support import Json
from .test_i01t08_registrations import (
    _uploaded,  # pyright: ignore[reportPrivateUsage] -- an upload as fulfil_by_upload writes it
)
from .test_p04t17_human_gates_independent import Firm, firm

__all__ = ["firm"]
pytestmark = pytest.mark.asyncio


async def _review_row(f: Firm) -> Json:
    status, page = await f.gates(f.hannah)
    assert status == 200, page
    rows = [r for r in cast(list[Json], page["items"]) if r["kind"] == "evidence_review"]
    assert len(rows) == 1, rows
    return rows[0]


async def _list_of(f: Firm) -> tuple[uuid.UUID, str, uuid.UUID]:
    row = (
        await f.net.seed.rows(
            "SELECT l.id, l.kind, l.work_item_id FROM request_lists l "
            "JOIN request_items i ON i.request_list_id = l.id WHERE i.id = $1",
            f.bayside.item_id,
        )
    )[0]
    return row["id"], str(row["kind"]), row["work_item_id"]


async def test_an_upload_on_a_pbc_list_opens_its_audit_with_the_item(firm: Firm) -> None:
    list_id, kind, work_item = await _list_of(firm)
    await firm.net.seed.run("UPDATE request_lists SET kind = 'pbc' WHERE id = $1", list_id)
    await _uploaded(firm, firm.bayside)
    row = await _review_row(firm)
    assert row["subject_route"] == f"AUD-03?auditId={work_item}&item={firm.bayside.item_id}"
    assert kind in {"pbc", "organizer", "intake", "close_intake", "third_party"}


async def test_an_upload_on_a_binder_opens_the_binder_on_its_request(firm: Firm) -> None:
    list_id, _, _ = await _list_of(firm)
    await firm.net.seed.run("UPDATE request_lists SET kind = 'organizer' WHERE id = $1", list_id)
    await _uploaded(firm, firm.bayside)
    row = await _review_row(firm)
    assert row["subject_route"] == f"BND-02?binderId={list_id}&request={firm.bayside.item_id}"


async def test_the_route_carries_ids_only(firm: Firm) -> None:
    await _uploaded(firm, firm.bayside)
    route = cast(str, (await _review_row(firm))["subject_route"])
    screen, query = route.split("?", 1)
    assert screen in {"AUD-03", "BND-02"}
    for pair in query.split("&"):
        _, value = pair.split("=", 1)
        uuid.UUID(value)  # every value is an opaque id, never a name


def test_subject_route_names_the_host_by_list_kind() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert subject_route("pbc", a, b, c) == f"AUD-03?auditId={b}&item={c}"
    for kind in ("organizer", "intake", "close_intake", "third_party"):
        assert subject_route(kind, a, b, c) == f"BND-02?binderId={a}&request={c}"
