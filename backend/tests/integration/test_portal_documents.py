"""R-01-T07 against Postgres: the portal PBC read model (C5 section `portal-pbc`; POR-03, POR-04;
R-01 Stories 1.1, 1.2, 3.2, 5.1; DEC-240, DEC-333).

Acceptance: "Claire Feld's binder returns 21 requests with 2 open matching TAX-03 Intake 2, Dana
Kowalski sees only Dana's own requests, and no field carries a firm status code or amount." The
seeded binder here is smaller (the Brightwater Hale slice is R-01-T11's): its counts foot the same
way (total = done + open, open = the requests still To do or Returned).

INV-4 in every read: a third party (Harborline, with two delegated requests) has no documents at
all; a client admin never reads a delegated request (only its organisation's name); a contributor
reads only what is assigned to them; drafts, internal-only requests, forged ids and another
client's binder answer 404. Withdrawn files are never listed (DEC-298). The C5 v1.1 firm-only row
fields (`owed_by`, `latest_upload`, `match_confidence`, DEC-261) never reach a client principal.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz import recording_checks
from abacus.modules.portal.documents import list_binders, read_binder, read_request
from abacus.modules.portal.pbc_contract import PortalBinderOut, PortalRowOut
from abacus.modules.requests.lifecycle import delegate_item

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

FLAGS = ("binders.engine",)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def client_ctx(who: Person) -> AuthContext:
    """A client membership's context, as the portal session builds it."""
    return replace(who.context(), client=True)


async def client_person(seed: Seeder, tenant: uuid.UUID, name: str) -> Person:
    who = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
    )
    await seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
    return who


async def grant_access(seed: Seeder, who: Person, role: str, kind: str, scope: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, $3, $4, $5)",
        who.tenant_id,
        who.user_id,
        role,
        kind,
        scope,
    )


@dataclass
class World:
    seed: Seeder
    tenant: uuid.UUID
    engagement: uuid.UUID
    client_id: uuid.UUID
    partner: Person
    claire: Person
    jonah: Person
    binder: uuid.UUID
    categories: dict[str, uuid.UUID]
    items: dict[str, uuid.UUID]
    draft: uuid.UUID


async def _binder(
    seed: Seeder,
    tenant: uuid.UUID,
    engagement: uuid.UUID,
    by: Person,
    *,
    name: str,
    kind: str = "organizer",
    status: str = "published",
    part: int = 1,
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id, name, kind, part, status, "
            "published_at, published_by) VALUES ($1, $2, $3, $4, $5, $6, "
            "CASE WHEN $6 = 'draft' THEN NULL ELSE now() END, "
            "CASE WHEN $6 = 'draft' THEN NULL ELSE $7::uuid END) RETURNING id",
            tenant,
            engagement,
            name,
            kind,
            part,
            status,
            by.user_id,
        ),
    )


async def _category(
    seed: Seeder, w_tenant: uuid.UUID, binder: uuid.UUID, name: str, pos: int
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_categories (tenant_id, request_list_id, name, position) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            w_tenant,
            binder,
            name,
            pos,
        ),
    )


async def _item(
    seed: Seeder,
    tenant: uuid.UUID,
    engagement: uuid.UUID,
    binder: uuid.UUID,
    by: Person,
    title: str,
    *,
    category: uuid.UUID | None,
    group: str = "Documents",
    status: str = "requested",
    visible: bool = True,
    kind: str = "client_upload",
    assignee: Person | None = None,
) -> uuid.UUID:
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by, title, category_id, kind, client_visible, due_on, "
            "client_assignee_user_id) VALUES ($1, $2, $3, $4, $5, $6, $4, $7, $8, $9, "
            "current_date + 30, $10) RETURNING id",
            tenant,
            engagement,
            binder,
            title,
            group,
            by.user_id,
            category,
            kind,
            visible,
            assignee.user_id if assignee else None,
        ),
    )
    if visible:
        await seed.run(
            "UPDATE request_items SET status = $2, requested_at = now() WHERE id = $1",
            item,
            status,
        )
    return item


async def _file(
    w: World,
    item: uuid.UUID,
    name: str,
    *,
    by: Person,
    source: str = "client_upload",
    method: str = "uploaded",
    linked_by: str = "human",
) -> tuple[uuid.UUID, uuid.UUID]:
    """An evidence version on the request, fulfilling it: (version, fulfilment)."""
    evidence = await w.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'human', $4) RETURNING id",
        w.tenant,
        w.engagement,
        name,
        str(by.user_id),
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await w.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 2048, 'application/pdf', "
            "$6, $7) RETURNING id",
            w.tenant,
            w.engagement,
            evidence,
            fingerprint,
            f"tenants/{w.tenant}/sha256/{fingerprint}",
            source,
            method,
        ),
    )
    fulfilment = cast(
        uuid.UUID,
        await w.seed.value(
            "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
            "evidence_version_id, created_by_kind, created_by_id) "
            "VALUES ($1, $2, $3, $4, $5, 'seed') RETURNING id",
            w.tenant,
            w.engagement,
            item,
            version,
            linked_by,
        ),
    )
    return version, fulfilment


async def feld_world(seed: Seeder) -> World:
    """The Feld household's 2025 Binder in small: three sections, five requests the household
    reads (two open), and three it never does (internal-only, delegated, and in a draft)."""
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'R-01-T07')",
            tenant,
            flag,
        )
    partner = await seed.person(tenant)
    await seed.run("UPDATE users SET display_name = 'Kevin Osei' WHERE id = $1", partner.user_id)
    entity = await seed.entity(tenant)
    client_id = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    claire = await client_person(seed, tenant, "Claire Feld")
    jonah = await client_person(seed, tenant, "Jonah Feld")
    for who in (claire, jonah):
        await grant_access(seed, who, "owner", "engagement", engagement)
    binder = await _binder(seed, tenant, engagement, partner, name="2025 Binder")
    cats = {
        name: await _category(seed, tenant, binder, name, pos)
        for pos, name in enumerate(("Income Sources", "Health & Medical", "Retirement"))
    }
    items: dict[str, uuid.UUID] = {}

    async def add(
        key: str,
        title: str,
        category: str,
        group: str,
        *,
        status: str = "requested",
        visible: bool = True,
        kind: str = "client_upload",
    ) -> None:
        items[key] = await _item(
            seed,
            tenant,
            engagement,
            binder,
            partner,
            title,
            category=cats[category],
            group=group,
            status=status,
            visible=visible,
            kind=kind,
        )

    income = "Income Sources"
    await add("w2", "2025 W-2 From Mercer Hill Health", income, "W-2s", status="uploaded")
    await add("1099", "2025 Consolidated 1099", income, "1099s", status="uploaded")
    await add(
        "k1", "Schedule K-1 from Ridgeline", income, "Partnership K-1s", kind="firm_provided"
    )
    await add(
        "1095", "Form 1095-C From Mercer Hill Health", "Health & Medical", "Health insurance"
    )
    await add("1099b", "2025 Form 1099-B", income, "Brokerage")
    await add("internal", "Partner memo", income, "Brokerage", visible=False)
    await add("delegated", "Brokerage cost basis letter", income, "Brokerage")
    draft = await _binder(seed, tenant, engagement, partner, name="Draft", status="draft", part=2)
    items["in_draft"] = await _item(
        seed, tenant, engagement, draft, partner, "Draft request", category=None, visible=False
    )
    world = World(
        seed, tenant, engagement, client_id, partner, claire, jonah, binder, cats, items, draft
    )
    await _file(world, items["w2"], "Claire_Feld_2025_W2_MercerHill.pdf", by=claire)
    await _file(world, items["1099"], "Jonah_Feld_2025_1099_Composite.pdf", by=jonah)
    harborline = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, email, organisation_name, "
        "contact_kind) VALUES ($1, $2, 'Harborline Benefits', 'h@example.test', 'Harborline', "
        "'third_party') RETURNING id",
        tenant,
        client_id,
    )
    grant = await seed.value(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "contact_id, status) VALUES ($1, NULL, 'third_party', 'request_item', $2, $3, 'pending') "
        "RETURNING id",
        tenant,
        items["delegated"],
        harborline,
    )
    await seed.run(
        "INSERT INTO request_delegations (tenant_id, request_item_id, contact_id, grant_id, "
        "granted_by) VALUES ($1, $2, $3, $4, $5)",
        tenant,
        items["delegated"],
        harborline,
        grant,
        partner.user_id,
    )
    return world


def rows_of(binder: PortalBinderOut) -> dict[uuid.UUID, PortalRowOut]:
    return {r.id: r for g in [*binder.groups, *binder.bands] for r in g.rows}


def _field_names(model: BaseModel) -> set[str]:
    found: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, BaseModel):
            for name in type(value).model_fields:
                found.add(name)
                walk(getattr(value, name))
        elif isinstance(value, list):
            for v in cast(list[object], value):
                walk(v)

    walk(model)
    return found


async def test_ac_claires_binder_foots_in_client_words_with_receipts(seed: Seeder) -> None:
    w = await feld_world(seed)
    out = await read_binder(client_ctx(w.claire), w.binder, "all", None)

    rows = rows_of(out)
    assert set(rows) == {w.items[k] for k in ("w2", "1099", "k1", "1095", "1099b")}
    assert (out.total, out.done_count, out.open_count) == (5, 3, 2)
    assert out.total == out.done_count + out.open_count
    assert out.layout == "groups" and out.binder.title == "2025 Binder" and out.binder.year == 2025
    statuses = {k: rows[w.items[k]].client_status for k in ("w2", "1099", "k1", "1095", "1099b")}
    assert statuses == {
        "w2": "done",
        "1099": "done",
        "k1": "done",
        "1095": "to_do",
        "1099b": "to_do",
    }
    w2, jonahs, k1, open_row = (rows[w.items[k]] for k in ("w2", "1099", "k1", "1095"))
    assert [(f.name, f.receipt.kind) for f in w2.files] == [
        ("Claire_Feld_2025_W2_MercerHill.pdf", "uploaded")
    ]
    assert (jonahs.files[0].receipt.kind, jonahs.files[0].receipt.by_first_name) == (
        "uploaded_by_other_contact",
        "Jonah",
    )
    assert k1.kind == "firm_provided" and k1.allowed_actions == ["comment"]
    assert set(open_row.allowed_actions) == {"upload", "ignore", "comment"}
    by_code = {c.code: c for c in out.categories}
    assert [c.code for c in out.categories] == ["income_sources", "health_medical", "retirement"]
    assert (by_code["health_medical"].complete, by_code["health_medical"].requested) == (False, 1)
    assert (by_code["retirement"].complete, by_code["retirement"].requested) == (False, 0)
    assert not by_code["income_sources"].complete  # the 1099-B is open
    assert out.mark_done.state == "tonal" and set(out.allowed_actions) == {"upload", "mark_done"}
    assert out.other_parties == ["Harborline"]  # the organisation, never the request's title
    groups = {g.label: g.category_code for g in out.groups}
    assert groups["Health insurance"] == "health_medical"


async def test_ac_no_field_carries_a_firm_status_an_amount_or_a_firm_only_c5_field(
    seed: Seeder,
) -> None:
    """DEC-261: `owed_by`, `latest_upload` and `match_confidence` never reach a client; nor does a
    C2 status code, an amount, a confidence or an agent field (contract §1)."""
    w = await feld_world(seed)
    out = await read_binder(client_ctx(w.claire), w.binder, "all", None)
    sheet = await read_request(client_ctx(w.claire), w.items["w2"])
    for model in (out, sheet):
        names = _field_names(model)
        assert not names & {"owed_by", "latest_upload", "match_confidence", "status", "amount"}
        assert not any("confidence" in n or "agent" in n or "screening" in n for n in names)
        dumped = model.model_dump_json()
        assert "Accrued" not in dumped
        # A C2 code never appears as a value (the receipt kind `uploaded` is a client word).
        assert (
            re.search(r':"(requested|received|not_applicable|returned_to_client)"', dumped) is None
        )


async def test_ac_filters_requested_uploaded_by_me_and_the_category(seed: Seeder) -> None:
    w = await feld_world(seed)
    ctx = client_ctx(w.claire)
    mine = rows_of(await read_binder(ctx, w.binder, "uploaded_by_me", None))
    assert set(mine) == {w.items["w2"]}
    health = await read_binder(ctx, w.binder, "requested", "health_medical")
    assert set(rows_of(health)) == {w.items["1095"]}
    assert health.total == 5  # the counts are the binder's, whatever the filter
    await seed.run(
        "UPDATE request_items SET status = 'not_applicable', na_reason = 'firm_waived', "
        "na_note = 'Not needed', na_by = $2, na_at = now() WHERE id = $1",
        w.items["1099b"],
        w.partner.user_id,
    )
    requested = rows_of(await read_binder(ctx, w.binder, "requested", None))
    assert w.items["1099b"] not in requested  # waived by the firm: no longer requested
    assert w.items["1099b"] in rows_of(await read_binder(ctx, w.binder, "all", None))


async def test_ac_the_binder_picker_lists_the_binders_with_the_closed_one_read_only(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    prior = await _binder(
        seed, w.tenant, w.engagement, w.partner, name="2024 Binder", status="closed", part=3
    )
    await _item(seed, w.tenant, w.engagement, prior, w.partner, "2024 W-2", category=None)
    picker = await list_binders(client_ctx(w.claire), None)
    by_title = {b.title: b for b in picker.items}
    assert set(by_title) == {"2025 Binder", "2024 Binder"}  # never the draft
    assert (by_title["2024 Binder"].closed, by_title["2024 Binder"].read_only) == (True, True)
    assert (by_title["2025 Binder"].closed, by_title["2025 Binder"].read_only) == (False, False)
    closed = await read_binder(client_ctx(w.claire), prior, "all", None)
    assert closed.allowed_actions == [] and closed.binder.read_only
    assert all(r.allowed_actions == [] for r in rows_of(closed).values())
    scoped = await list_binders(client_ctx(w.claire), w.engagement)
    assert scoped.total == 2
    with pytest.raises(NotFound):
        await list_binders(client_ctx(w.claire), uuid.uuid4())


async def test_inv4_a_contributor_reads_only_what_is_assigned_to_them(seed: Seeder) -> None:
    """R-01 Story 1.2: Dana sees only her own requests, and a contributor no other-parties note."""
    w = await feld_world(seed)
    dana = await client_person(seed, w.tenant, "Dana Kowalski")
    await grant_access(seed, dana, "contributor", "engagement", w.engagement)
    await seed.run(
        "UPDATE request_items SET client_assignee_user_id = $2 WHERE id = $1",
        w.items["1095"],
        dana.user_id,
    )
    out = await read_binder(client_ctx(dana), w.binder, "all", None)
    assert set(rows_of(out)) == {w.items["1095"]}
    assert (out.total, out.open_count) == (1, 1)
    assert out.other_parties == []
    with pytest.raises(NotFound):
        await read_request(client_ctx(dana), w.items["w2"])
    assert (await read_request(client_ctx(dana), w.items["1095"])).id == w.items["1095"]


async def test_inv4_a_third_party_with_two_delegated_requests_has_no_documents(
    seed: Seeder,
) -> None:
    """Harborline's grant covers its two delegated requests only (P-07-T25); every read here
    answers 404 to it, and the client admin never reads a delegated request."""
    w = await feld_world(seed)
    second = await _item(
        seed,
        w.tenant,
        w.engagement,
        w.binder,
        w.partner,
        "Payroll register",
        category=w.categories["Income Sources"],
    )
    harborline = await client_person(seed, w.tenant, "Harborline Benefits")
    for item in (w.items["delegated"], second):
        await grant_access(seed, harborline, "third_party", "request_item", item)
    contact = await seed.value(
        "SELECT contact_id FROM request_delegations WHERE request_item_id = $1",
        w.items["delegated"],
    )
    grant = await seed.value(
        "SELECT id FROM client_access_grants WHERE user_id = $1 AND scope_id = $2",
        harborline.user_id,
        second,
    )
    await seed.run(
        "INSERT INTO request_delegations (tenant_id, request_item_id, contact_id, grant_id, "
        "granted_by) VALUES ($1, $2, $3, $4, $5)",
        w.tenant,
        second,
        contact,
        grant,
        w.partner.user_id,
    )
    ctx = client_ctx(harborline)
    with pytest.raises(NotFound):
        await list_binders(ctx, None)
    with pytest.raises(NotFound):
        await read_binder(ctx, w.binder, "all", None)
    for item in (w.items["delegated"], second, w.items["1095"]):
        with pytest.raises(NotFound):
            await read_request(ctx, item)
    claire = client_ctx(w.claire)
    rows = rows_of(await read_binder(claire, w.binder, "all", None))
    assert w.items["delegated"] not in rows and second not in rows
    for item in (w.items["delegated"], second):
        with pytest.raises(NotFound):
            await read_request(claire, item)


async def test_inv4_drafts_internal_forged_other_clients_and_the_firm_answer_404(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    claire = client_ctx(w.claire)
    for binder in (w.draft, uuid.uuid4()):
        with pytest.raises(NotFound):
            await read_binder(claire, binder, "all", None)
    for item in (w.items["internal"], w.items["in_draft"], uuid.uuid4()):
        with pytest.raises(NotFound):
            await read_request(claire, item)
    other = await feld_world(seed)  # another firm's household
    with pytest.raises(NotFound):
        await read_binder(claire, other.binder, "all", None)
    with pytest.raises(NotFound):  # the firm's own partner has no portal documents
        await read_binder(w.partner.context(), w.binder, "all", None)


async def test_dec298_a_withdrawn_file_is_never_listed(seed: Seeder) -> None:
    w = await feld_world(seed)
    version, fulfilment = await _file(w, w.items["1095"], "Feld_1095C_wrong.pdf", by=w.claire)
    before = rows_of(await read_binder(client_ctx(w.claire), w.binder, "all", None))
    assert [f.id for f in before[w.items["1095"]].files] == [version]
    await seed.as_actor(
        w.tenant,
        ("human", str(w.claire.user_id)),
        "INSERT INTO fulfilment_withdrawals (tenant_id, fulfilment_id, engagement_id, "
        "request_item_id, evidence_version_id, withdrawn_by_user_id) "
        "VALUES ($1, $2, $3, $4, $5, $6)",
        w.tenant,
        fulfilment,
        w.engagement,
        w.items["1095"],
        version,
        w.claire.user_id,
    )
    for who in (w.claire, w.jonah):
        rows = rows_of(await read_binder(client_ctx(who), w.binder, "all", None))
        assert rows[w.items["1095"]].files == []
        sheet = await read_request(client_ctx(who), w.items["1095"])
        assert sheet.files == []


async def test_ac_a_send_back_reads_returned_wrong_year_with_the_firms_note(seed: Seeder) -> None:
    """R-01 Story 3.2 (POR-03 g, POR-04 d): the red-tint "Returned · wrong year", Kevin's note
    with his name and date, the struck file and Upload…."""
    w = await feld_world(seed)
    version, _ = await _file(w, w.items["1095"], "Feld_1095C_2024.pdf", by=w.claire)
    await seed.as_actor(
        w.tenant,
        ("human", str(w.partner.user_id)),
        "INSERT INTO review_decisions (tenant_id, engagement_id, evidence_version_id, "
        "request_item_id, decision, reason_code, note, corrects_proposal, actor_kind, "
        "actor_id, decision_seq) VALUES ($1, $2, $3, $4, 'send_back', 'wrong_period', $5, "
        "false, 'human', $6, 1)",
        w.tenant,
        w.engagement,
        version,
        w.items["1095"],
        "This is the 2024 form. We need the 2025 Form 1095-C.",
        str(w.partner.user_id),
    )
    await seed.run("UPDATE request_items SET status = 'returned' WHERE id = $1", w.items["1095"])
    sheet = await read_request(client_ctx(w.claire), w.items["1095"])
    assert sheet.client_status == "returned"
    assert sheet.returned is not None
    assert (sheet.returned.reason, sheet.returned.by_name) == ("wrong_year", "Kevin Osei")
    assert sheet.returned.note == "This is the 2024 form. We need the 2025 Form 1095-C."
    assert [(f.name, f.struck) for f in sheet.files] == [("Feld_1095C_2024.pdf", True)]
    assert "upload" in sheet.allowed_actions
    assert sheet.category.code == "health_medical" and sheet.category.label == "Health & Medical"


async def test_ac_the_sheet_carries_guidance_counts_and_a_rule_links_suggested_receipt(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    await seed.run(
        "UPDATE request_items SET why = 'We report your coverage on your return.' WHERE id = $1",
        w.items["1095"],
    )
    await _file(w, w.items["1095"], "Feld_2025_1095C.pdf", by=w.claire, linked_by="rule")
    sheet = await read_request(client_ctx(w.claire), w.items["1095"])
    assert sheet.guidance == "We report your coverage on your return."
    assert sheet.variant == "request" and sheet.comment_count == 0 and sheet.pre_checks == []
    assert sheet.files[0].receipt.kind == "rule_linked_pending"
    binder = await read_binder(client_ctx(w.claire), w.binder, "all", None)
    assert binder.sorted_count == 1


async def test_both_reads_record_the_one_action_for_the_route_guard(seed: Seeder) -> None:
    w = await feld_world(seed)
    for read in (
        lambda: read_binder(client_ctx(w.claire), w.binder, "requested", None),
        lambda: read_request(client_ctx(w.claire), w.items["1095"]),
        lambda: list_binders(client_ctx(w.claire), None),
    ):
        with recording_checks() as checked:
            await read()
        assert "portal_documents.read" in checked


# --- Security review of R-01-T07 (DEC-333 amended) ----------------------------------------------


async def test_review1_a_binder_unpublished_then_closed_is_404_everywhere(seed: Seeder) -> None:
    """AC-7: closing a binder while it is Unpublished never shows it to the client again."""
    w = await feld_world(seed)
    await _file(w, w.items["1095"], "Feld_1095C_2025.pdf", by=w.claire)
    await seed.run(
        "UPDATE request_lists SET published_at = now() - interval '1 hour', "
        "status = 'unpublished', unpublished_at = now() - interval '30 minutes', "
        "unpublished_by = $2 WHERE id = $1",
        w.binder,
        w.partner.user_id,
    )
    await seed.run(
        "UPDATE request_lists SET status = 'closed', closed_at = now(), "
        "closed_reason = 'work_delivered' WHERE id = $1",
        w.binder,
    )
    claire = client_ctx(w.claire)
    assert w.binder not in {b.id for b in (await list_binders(claire, None)).items}
    with pytest.raises(NotFound):
        await read_binder(claire, w.binder, "all", None)
    for key in ("1095", "w2"):
        with pytest.raises(NotFound):
            await read_request(claire, w.items[key])


async def test_review1_a_binder_republished_then_closed_stays_readable(seed: Seeder) -> None:
    w = await feld_world(seed)
    await seed.run(
        "UPDATE request_lists SET unpublished_at = now() - interval '2 hours', "
        "unpublished_by = $2, status = 'closed', closed_at = now(), "
        "closed_reason = 'work_delivered' WHERE id = $1",
        w.binder,
        w.partner.user_id,
    )
    closed = await read_binder(client_ctx(w.claire), w.binder, "all", None)
    assert closed.binder.closed and closed.allowed_actions == []


async def _prior(w: World, status: str) -> uuid.UUID:
    """Last year's binder with the 1095-C and its file; this year's binder rolled from it."""
    prior = await _binder(
        w.seed, w.tenant, w.engagement, w.partner, name="2024 Binder", status=status, part=5
    )
    old = await _item(
        w.seed,
        w.tenant,
        w.engagement,
        prior,
        w.partner,
        "Form 1095-C From Mercer Hill Health",
        category=None,
    )
    await _file(w, old, "Feld_1095C_2024.pdf", by=w.claire)
    await w.seed.run(
        "UPDATE request_lists SET prior_year_source_ref = $2 WHERE id = $1", w.binder, prior
    )
    return prior


async def test_review2_last_years_file_comes_only_from_a_binder_the_client_reads(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    prior = await _prior(w, "published")
    sheet = await read_request(client_ctx(w.claire), w.items["1095"])
    assert sheet.prior_year is not None and sheet.prior_year.file_name == "Feld_1095C_2024.pdf"
    await seed.run(
        "UPDATE request_lists SET status = 'unpublished', unpublished_at = now(), "
        "unpublished_by = $2 WHERE id = $1",
        prior,
        w.partner.user_id,
    )
    assert (await read_request(client_ctx(w.claire), w.items["1095"])).prior_year is None


async def test_review2_a_draft_prior_binder_leaks_nothing(seed: Seeder) -> None:
    w = await feld_world(seed)
    prior = await _prior(w, "published")
    await seed.run(
        "UPDATE request_lists SET status = 'draft', published_at = NULL, published_by = NULL "
        "WHERE id = $1",
        prior,
    )
    assert (await read_request(client_ctx(w.claire), w.items["1095"])).prior_year is None


async def test_review5_a_delegate_made_by_delegate_item_has_no_documents(seed: Seeder) -> None:
    """The P-06 delegation issues role `delegate` (a full-shell role); it opens no documents."""
    w = await feld_world(seed)
    sam = await client_person(seed, w.tenant, "Sam Ortiz")
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, email, organisation_name, "
        "contact_kind, user_id) VALUES ($1, $2, 'Sam Ortiz', 'sam@example.test', "
        "'Keystone Retirement Services', 'third_party', $3) RETURNING id",
        w.tenant,
        w.client_id,
        sam.user_id,
    )
    await delegate_item(
        w.partner.context(), w.engagement, w.items["1099b"], cast(uuid.UUID, contact)
    )
    roles = await seed.rows(
        "SELECT role, scope_kind FROM client_access_grants WHERE user_id = $1", sam.user_id
    )
    assert [(r["role"], r["scope_kind"]) for r in roles] == [("delegate", "request_item")]
    ctx = client_ctx(sam)
    with pytest.raises(NotFound):
        await list_binders(ctx, None)
    with pytest.raises(NotFound):
        await read_binder(ctx, w.binder, "all", None)
    with pytest.raises(NotFound):
        await read_request(ctx, w.items["1099b"])


async def _comment(w: World, item: uuid.UUID, version: uuid.UUID | None, by: Person) -> None:
    await w.seed.run(
        "INSERT INTO comments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "author_user_id, author_side, visibility, body_sealed, body_fingerprint) "
        "VALUES ($1, $2, $3, $4, $5, 'client', 'shared', '\\x00'::bytea, $6)",
        w.tenant,
        w.engagement,
        item,
        version,
        by.user_id,
        hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
    )


async def test_review6_the_comment_count_leaves_out_a_withdrawn_files_thread(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    version, fulfilment = await _file(w, w.items["1095"], "Feld_wrong.pdf", by=w.claire)
    await _comment(w, w.items["1095"], None, w.claire)
    await _comment(w, w.items["1095"], version, w.claire)
    assert (await read_request(client_ctx(w.claire), w.items["1095"])).comment_count == 2
    await seed.as_actor(
        w.tenant,
        ("human", str(w.claire.user_id)),
        "INSERT INTO fulfilment_withdrawals (tenant_id, fulfilment_id, engagement_id, "
        "request_item_id, evidence_version_id, withdrawn_by_user_id) "
        "VALUES ($1, $2, $3, $4, $5, $6)",
        w.tenant,
        fulfilment,
        w.engagement,
        w.items["1095"],
        version,
        w.claire.user_id,
    )
    assert (await read_request(client_ctx(w.claire), w.items["1095"])).comment_count == 1


async def test_review6_a_category_of_only_hidden_requests_is_not_named(seed: Seeder) -> None:
    w = await feld_world(seed)
    business = await _category(seed, w.tenant, w.binder, "Business & Self-Employment", 9)
    await _item(
        seed,
        w.tenant,
        w.engagement,
        w.binder,
        w.partner,
        "Partner memo 2",
        category=business,
        visible=False,
    )
    out = await read_binder(client_ctx(w.claire), w.binder, "all", None)
    codes = [c.code for c in out.categories]
    assert "business_self_employment" not in codes
    assert "retirement" in codes  # an empty category still reads "Nothing requested"


async def test_review7_a_third_partys_upload_names_only_its_organisation(seed: Seeder) -> None:
    """After the delegation ends the request is the client's again: Harborline's upload stays on
    it, named "Harborline", never the person who uploaded; a person with no client role on the
    engagement and no contact is not named at all."""
    w = await feld_world(seed)
    sam = await client_person(seed, w.tenant, "Sam Ortiz")
    await seed.run(
        "UPDATE contacts SET user_id = $2 "
        "WHERE tenant_id = $1 AND organisation_name = 'Harborline'",
        w.tenant,
        sam.user_id,
    )
    await _file(w, w.items["delegated"], "Harborline_cost_basis.pdf", by=sam)
    await seed.run(
        "UPDATE request_delegations SET revoked_at = now() WHERE request_item_id = $1",
        w.items["delegated"],
    )
    stranger = await client_person(seed, w.tenant, "Pat Stranger")
    await _file(w, w.items["1099b"], "stray.pdf", by=stranger)
    rows = rows_of(await read_binder(client_ctx(w.claire), w.binder, "all", None))
    [harborline] = rows[w.items["delegated"]].files
    assert (harborline.receipt.kind, harborline.receipt.by_first_name) == (
        "uploaded_by_other_contact",
        "Harborline",
    )
    [stray] = rows[w.items["1099b"]].files
    assert stray.receipt.by_first_name is None
    dumped = (await read_binder(client_ctx(w.claire), w.binder, "all", None)).model_dump_json()
    assert "Sam" not in dumped and "Pat" not in dumped
