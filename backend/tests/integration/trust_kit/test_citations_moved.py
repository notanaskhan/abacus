"""P-03-T12 against Postgres and the S3 gateway (SPEC-322 F6, AC6.1-AC6.3; ADR-166 §6; DEC-321):
moved and broken detection, and a person's relink.

- A new version marks every citation to the item's earlier versions `moved` (one event per
  citation and cause, with a `citation.moved` outbox event), once however often the event is
  delivered; a version the client withdrew moves nothing and its own citations are `broken`.
- A relink from an agent, a worker or outside a live request is refused (and the database refuses a
  `relinked` event that is not a person's); a person's relink writes a new verified row on the
  successor, a `relinked` event and a `citation.relinked` audit event; text that is gone is 422
  `relink_unverified` with nothing written; a citation that did not move is 409 `not_moved`.
"""

from __future__ import annotations

import json
import uuid

import asyncpg
import pytest

from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    NewItem,
    Provenance,
    add_version,
    record_citations,
    stage_content,
)
from abacus.modules.evidence.citations.display import citation_display
from abacus.modules.evidence.citations.moved import (
    NotMoved,
    RelinkUnverified,
    on_version_created,
    on_version_withdrawn,
    relink,
)
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import RULES, Forbidden, agent_context_for_run
from abacus.modules.identity.authz import recording_checks
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Firm, Seeder, as_version, make_firm

V1 = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement")],
        [(72.0, 700.0, "Total investments 16,500,000.00"), (72.0, 600.0, "Net assets")],
    ]
)
# The successor: the cited line moved to page 3.
V2 = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement, corrected")],
        [(72.0, 700.0, "Prepared Jan 1, 2026")],
        [(72.0, 650.0, "Total investments 16,500,000.00")],
    ]
)
GONE = positioned_pdf([[(72.0, 700.0, "Nothing here any more")]])


async def _version(
    firm: Firm, content: bytes, item: uuid.UUID | None = None, *, scan: bool = True
) -> uuid.UUID:
    stored = await stage_content(firm.tenant_id, content)
    async with uow(firm.system) as tx:
        ref = await add_version(
            tx,
            engagement_id=firm.engagement_id,
            item=item or NewItem(f"Statement {uuid.uuid4().hex[:6]}"),
            stored=stored,
            media_type="application/pdf",
            provenance=Provenance(source="upload", method="uploaded"),
        )
    await words_upload(as_version(firm, ref.id))
    if scan:  # P-03-T13: a page no scan lists is never searched (fail closed)
        await pii_scan_upload(as_version(firm, ref.id))
    return ref.id


async def _item(firm: Firm, version: uuid.UUID) -> uuid.UUID:
    return await firm.seed.id(
        "SELECT evidence_item_id FROM evidence_versions WHERE id = $1", version
    )


async def _cited(firm: Firm, version: uuid.UUID) -> list[uuid.UUID]:
    anchor = CitationAnchor("workpaper_cell", uuid.uuid4(), "RA!C14", None, firm.engagement_id)
    acting = firm.person()
    async with uow(acting.tenant) as tx:
        made = await record_citations(
            tx,
            actor=acting,
            anchor=anchor,
            claims=[
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(version), "page": 2},
                    quote="Total investments 16,500,000.00",
                ),
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(version), "page": 1},
                    quote="Harborline statement",
                ),
            ],
        )
    assert all(m.verified for m in made)
    return [m.id for m in made]


def _created(firm: Firm, version: uuid.UUID, event_id: uuid.UUID | None = None) -> OutboxEvent:
    return OutboxEvent(
        event_id or uuid.uuid4(),
        firm.tenant_id,
        "evidence_version.created",
        {"evidence_version_id": str(version), "engagement_id": str(firm.engagement_id)},
    )


async def _events(firm: Firm, citation: uuid.UUID) -> list[tuple[str, str | None, str]]:
    rows = await firm.seed.rows(
        "SELECT kind, cause_ref, actor_kind FROM citation_events WHERE citation_id = $1 "
        "ORDER BY at, id",
        citation,
    )
    return [(r["kind"], r["cause_ref"], r["actor_kind"]) for r in rows]


async def _outbox(firm: Firm, event_type: str) -> int:
    found = await firm.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = $2",
        firm.tenant_id,
        event_type,
    )
    return found if isinstance(found, int) else 0


async def _withdraw(firm: Firm, version: uuid.UUID) -> None:
    """The withdrawal row the route writes for a client's own upload (ADR-162 §4)."""
    await firm.seed.run_untriggered(
        "INSERT INTO evidence_withdrawals (tenant_id, evidence_version_id, engagement_id, "
        "withdrawn_by_user_id, withdrawn_at, erase_after) "
        "VALUES ($1, $2, $3, $4, now(), now() + interval '7 days')",
        firm.tenant_id,
        version,
        firm.engagement_id,
        firm.user_id,
    )


async def _moved(firm: Firm) -> tuple[list[uuid.UUID], uuid.UUID]:
    v1 = await _version(firm, V1)
    cited = await _cited(firm, v1)
    v2 = await _version(firm, V2, await _item(firm, v1))
    await on_version_created(_created(firm, v2))
    return cited, v2


async def test_ac6_1_a_superseded_source_marks_its_citations_moved_once(seed: Seeder) -> None:
    firm = await make_firm(seed)
    v1 = await _version(firm, V1)
    cited = await _cited(firm, v1)
    v2 = await _version(firm, V2, await _item(firm, v1))
    event = _created(firm, v2)
    await on_version_created(event)
    for citation in cited:
        assert await _events(firm, citation) == [("moved", f"evidence_version:{v2}", "system")]
        view = await citation_display(firm.person(), citation)
        assert view.state == "moved" and view.allowed_actions == ["citation.relink"]
    assert await _outbox(firm, "citation.moved") == 2
    audits = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'citation.moved'",
        firm.tenant_id,
    )
    assert audits == 2
    await on_version_created(event)  # redelivered
    await on_version_created(_created(firm, v2))  # a second relay, another event id
    for citation in cited:
        assert len(await _events(firm, citation)) == 1
    assert await _outbox(firm, "citation.moved") == 2
    # The new version's own creation moves nothing on itself or on other items.
    await on_version_created(_created(firm, v1))
    assert await _outbox(firm, "citation.moved") == 2


async def test_ac6_1_a_withdrawn_version_moves_nothing_and_its_citations_break(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    v1 = await _version(firm, V1)
    cited = await _cited(firm, v1)
    v2 = await _version(firm, V2, await _item(firm, v1))
    await _withdraw(firm, v2)
    await on_version_created(_created(firm, v2))  # delivered after the withdrawal
    assert [await _events(firm, c) for c in cited] == [[], []]
    await _withdraw(firm, v1)
    withdrawn = OutboxEvent(
        uuid.uuid4(),
        firm.tenant_id,
        "evidence_version.withdrawn",
        {"evidence_version_id": str(v1), "engagement_id": str(firm.engagement_id)},
    )
    await on_version_withdrawn(withdrawn)
    await on_version_withdrawn(withdrawn)
    for citation in cited:
        assert await _events(firm, citation) == [("broken", f"withdrawn:{v1}", "system")]
    assert await _outbox(firm, "citation.broken") == 2


async def test_ac6_1_a_successor_withdrawn_later_no_longer_moves_the_citation(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    cited, v2 = await _moved(firm)
    await _withdraw(firm, v2)
    view = await citation_display(firm.person(), cited[0])
    assert (view.state, view.moved, view.allowed_actions) == ("valid", None, [])


async def test_ac6_2_a_person_relinks_onto_the_successor(seed: Seeder) -> None:
    firm = await make_firm(seed)
    cited, v2 = await _moved(firm)
    with recording_checks():
        new_id = await relink(firm.person(), cited[0])
    old = await firm.seed.rows("SELECT * FROM citations WHERE id = $1", cited[0])
    new = await firm.seed.rows("SELECT * FROM citations WHERE id = $1", new_id)
    assert new[0]["supersedes_id"] == cited[0]
    assert new[0]["source_id"] == v2 and new[0]["verified"] is True
    assert (new[0]["n"], new[0]["cited_from_id"]) == (old[0]["n"], old[0]["cited_from_id"])
    assert new[0]["created_by_kind"] == "human"
    assert new[0]["created_by_user_id"] == firm.user_id
    assert json.loads(new[0]["locator"])["page"] == 3  # found where it moved to
    events = await firm.seed.rows(
        "SELECT kind, actor_kind, actor_user_id, successor_citation_id FROM citation_events "
        "WHERE citation_id = $1 ORDER BY at, id",
        cited[0],
    )
    assert [(e["kind"], e["actor_kind"]) for e in events] == [
        ("moved", "system"),
        ("relinked", "human"),
    ]
    assert events[1]["actor_user_id"] == firm.user_id
    assert events[1]["successor_citation_id"] == new_id
    audit = await firm.seed.rows(
        "SELECT actor_kind, actor_id, target_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'citation.relinked'",
        firm.tenant_id,
    )
    assert [(a["actor_kind"], a["actor_id"], a["target_id"]) for a in audit] == [
        ("human", str(firm.user_id), str(new_id))
    ]
    assert (await citation_display(firm.person(), cited[0])).state == "relinked"
    fresh = await citation_display(firm.person(), new_id)
    assert (fresh.state, fresh.verified) == ("valid", True)
    with recording_checks(), pytest.raises(NotMoved):  # once is enough
        await relink(firm.person(), cited[0])


async def test_ac6_2_text_gone_from_the_successor_is_422_and_nothing_is_written(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    v1 = await _version(firm, V1)
    cited = await _cited(firm, v1)
    v2 = await _version(firm, GONE, await _item(firm, v1))
    await on_version_created(_created(firm, v2))
    before = await firm.seed.value(
        "SELECT count(*) FROM citations WHERE tenant_id = $1", firm.tenant_id
    )
    with recording_checks(), pytest.raises(RelinkUnverified):
        await relink(firm.person(), cited[0])
    after = await firm.seed.value(
        "SELECT count(*) FROM citations WHERE tenant_id = $1", firm.tenant_id
    )
    assert before == after
    assert [k for k, _, _ in await _events(firm, cited[0])] == ["moved"]


async def test_ac6_2_a_citation_that_did_not_move_is_409(seed: Seeder) -> None:
    firm = await make_firm(seed)
    cited = await _cited(firm, await _version(firm, V1))
    with recording_checks(), pytest.raises(NotMoved):
        await relink(firm.person(), cited[0])


async def test_ac6_3_a_relink_outside_a_request_or_by_an_agent_is_refused(seed: Seeder) -> None:
    firm = await make_firm(seed)
    cited, _ = await _moved(firm)
    with pytest.raises(Forbidden):  # a worker or a script: no request being served
        await relink(firm.person(), cited[0])
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.screen",
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"citation.relink", "evidence.read"}),
        initiator_user_id=firm.user_id,
    )
    with recording_checks(), pytest.raises(Forbidden):
        await relink(agent, cited[0])  # type: ignore[arg-type]  # INV-1 at runtime too
    # The database's own CHECK: a relinked event is a person's.
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.run(
            "INSERT INTO citation_events (tenant_id, citation_id, kind, successor_citation_id, "
            "actor_kind) VALUES ($1, $2, 'relinked', $3, 'system')",
            firm.tenant_id,
            cited[0],
            cited[1],
        )
    assert [k for k, _, _ in await _events(firm, cited[0])] == ["moved"]


# --- Security review (DEC-321) -------------------------------------------------------------------


async def test_sec4_a_successor_page_never_scanned_is_never_searched(seed: Seeder) -> None:
    firm = await make_firm(seed)
    v1 = await _version(firm, V1)
    cited = await _cited(firm, v1)
    v2 = await _version(firm, V2, await _item(firm, v1), scan=False)
    await on_version_created(_created(firm, v2))
    with recording_checks(), pytest.raises(RelinkUnverified):
        await relink(firm.person(), cited[0])


async def test_sec4_a_walled_person_is_refused_at_the_wall(seed: Seeder) -> None:
    """The API answers a wall's refusal as 404 (DEC-43); the service raises it at `wall`."""
    firm = await make_firm(seed)
    cited, _ = await _moved(firm)
    client_id = await seed.id(
        "SELECT client_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $2)",
        firm.tenant_id,
        firm.user_id,
        client_id,
    )
    with recording_checks(), pytest.raises(Forbidden) as refused:
        await relink(firm.person(), cited[0])
    assert refused.value.layer == "wall"


def test_sec4_relink_needs_independence_on_the_engagement() -> None:
    """The matrix row `authorise` applies on the citing host (independence is checked there for
    attest clients, G2 v2; tests/unit/identity/test_independence.py lists the action)."""
    rule = RULES["citation.relink"]
    assert rule.independence
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"


async def test_sec4_an_archived_engagement_is_never_relinked(seed: Seeder) -> None:
    firm = await make_firm(seed)
    cited, _ = await _moved(firm)
    await seed.run_untriggered(
        "UPDATE engagements SET status = 'archived' WHERE id = $1", firm.engagement_id
    )
    with recording_checks(), pytest.raises((Forbidden, DomainConflict)):
        await relink(firm.person(), cited[0])
    assert [k for k, _, _ in await _events(firm, cited[0])] == ["moved"]
