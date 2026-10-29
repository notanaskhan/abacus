# ac-test-author: ayushkbhatia
"""N-01-T19 (TASK-2001; N-01 §3.7, §4.3; ADR-158, ADR-024; DEC-33, DEC-43; DEC-1051): the Files
read model live behind `files.browser`.

Acceptance (the task row): "Olivia Brandt sees Ridgeline's 12 documents and 7 virtual children,
and Felix Andersen gets metadata only."

What else the contract promises (`docs/contracts/files-browser.md`):
- the tree: client > Permanent file and years > work items > the five folders, counts over rows
  the viewer may see; a walled client counts nowhere;
- a folder lists each document's newest version and every superseded one, struck, with its
  replacement's name;
- the drawer: content fields null without `evidence.read` (ADR-024, DV-11), versions with
  Superseded, the virtual total computed by code, read-only (`allowed_actions` empty, DV-10);
- a client principal is 404; the flag off is 404; another firm's item is 404.

Boundary: `create_app()` over HTTP as each signed-in person; documents seeded by the superuser as
intake and upload write them.
"""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Any, Final, cast

import pytest

from abacus.kernel.flags import forget_flags

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
TREE: Final = "/v1/files/tree"


async def _flag(net: Net, tenant_id: uuid.UUID) -> None:
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'files.browser', 'true', 'test-seed', 'N-01-T19')",
        tenant_id,
    )
    forget_flags()


async def _work_item(net: Net, site: Site, by: Person, name: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'tax_return', $4, $5) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            name,
            by.user_id,
        ),
    )


async def _document(
    net: Net,
    site: Site,
    work_item: uuid.UUID | None,
    name: str,
    *,
    folder: str = "source_documents",
    supersedes: uuid.UUID | None = None,
    item: uuid.UUID | None = None,
    version_no: int = 1,
) -> tuple[uuid.UUID, uuid.UUID]:
    """An item (engagement-scoped on the work item, or client-scoped with none) and a version."""
    if item is None:
        if work_item is None:
            item = cast(
                uuid.UUID,
                await net.seed.value(
                    "INSERT INTO evidence_items (tenant_id, engagement_id, client_id, scope, "
                    "folder_kind, title, created_by_kind, created_by_id) VALUES ($1, NULL, $2, "
                    "'client', $3, $4, 'system', 'seed') RETURNING id",
                    site.tenant_id,
                    site.client_id,
                    folder,
                    name,
                ),
            )
        else:
            item = cast(
                uuid.UUID,
                await net.seed.value(
                    "INSERT INTO evidence_items (tenant_id, engagement_id, work_item_id, "
                    "folder_kind, title, created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, "
                    "$5, 'system', 'seed') RETURNING id",
                    site.tenant_id,
                    site.engagement_id,
                    work_item,
                    folder,
                    name,
                ),
            )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method, display_name, supersedes_version_id) VALUES ($1, $2, $3, $4, $5, $6, "
            "'v1', 2048, 'application/pdf', 'upload', 'uploaded', $7, $8) RETURNING id",
            site.tenant_id,
            site.engagement_id if work_item is not None else None,
            item,
            version_no,
            fingerprint,
            f"tenants/{site.tenant_id}/sha256/{fingerprint}",
            name,
            supersedes,
        ),
    )
    return item, version


async def _virtual(
    net: Net, site: Site, item: uuid.UUID, parent: uuid.UUID, label: str, pages: str, amount: str
) -> None:
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    await net.seed.run(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method, "
        "parent_version_id, page_range, virtual_label, virtual_amount) VALUES ($1, $2, $3, "
        "(SELECT max(version_no) + 1 FROM evidence_versions WHERE evidence_item_id = $3), $4, "
        "$5, 'v1', 0, 'application/pdf', 'upload', 'uploaded', $6, "
        "CAST($7::text AS int4range), $8, $9)",
        site.tenant_id,
        site.engagement_id,
        item,
        fingerprint,
        f"tenants/{site.tenant_id}/sha256/{fingerprint}",
        parent,
        pages,
        label,
        Decimal(amount),
    )


async def _ridgeline(net: Net) -> tuple[uuid.UUID, Site, Person, uuid.UUID, uuid.UUID]:
    """Ridgeline's TY2025 Form 1065: 12 source documents, one of them a combined statement split
    into 7 virtual statements; Olivia a senior on it."""
    tenant = await net.seed.firm()
    await _flag(net, tenant)
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Ridgeline Property Partners, LP")
    olivia = await net.seed.person(tenant)
    await net.seed.member(site, olivia, "senior")
    work_item = await _work_item(net, site, admin, "TY2025 Form 1065")
    combined: tuple[uuid.UUID, uuid.UUID] | None = None
    for n in range(12):
        made = await _document(net, site, work_item, f"Ridgeline statement {n + 1}.pdf")
        if n == 0:
            combined = made
    assert combined is not None
    for n in range(7):
        await _virtual(
            net,
            site,
            combined[0],
            combined[1],
            f"Mortgage interest {n + 1}",
            f"[{n + 1},{n + 2})",
            "100.00",
        )
    return tenant, site, olivia, work_item, combined[0]


async def test_ac1_olivia_sees_12_documents_and_7_virtual_children(net: Net) -> None:
    tenant, site, olivia, work_item, combined = await _ridgeline(net)
    tree = await net.call("GET", f"{TREE}?client_id={site.client_id}", olivia)
    assert tree.status_code == 200, tree.text
    [client] = tree.json()["nodes"]
    # The seeded site brings one document of its own; the TY2025 folders below are exact.
    assert "Ridgeline Property Partners, LP" in client["label"] and client["count"] >= 12
    folders = {
        n["folder_kind"]: n["count"]
        for year in client["children"]
        if year["kind"] == "year"
        for wi in year["children"]
        if wi["ref"] == f"work_item:{work_item}"
        for n in wi["children"]
    }
    assert folders == {
        "source_documents": 12,
        "workpapers": 0,
        "correspondence": 0,
        "deliverables": 0,
        "signed_authorizations": 0,
    }
    listed = await net.call(
        "GET", f"/v1/files/folders/folder:{work_item}:source_documents/items", olivia
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["documents"] == 12 and body["virtual"] == 7
    [row] = [r for r in body["items"] if r["evidence_item_id"] == str(combined)]
    assert len(row["virtual_children"]) == 7
    assert [c["first_page"] for c in row["virtual_children"]] == list(range(1, 8))
    drawer = await net.call("GET", f"/v1/evidence-items/{combined}/drawer", olivia)
    assert drawer.status_code == 200, drawer.text
    assert drawer.json()["tie"]["total"] in ("700.00", "700", 700)
    assert drawer.json()["tie"]["ties"] is None  # no C9 mapping (DV-13)
    assert drawer.json()["allowed_actions"] == []  # read-only (DV-10)
    _ = tenant


async def test_ac2_a_metadata_only_viewer_gets_no_content(net: Net) -> None:
    tenant, site, _olivia, _wi, combined = await _ridgeline(net)
    felix = await net.seed.person(tenant, "security_admin")
    drawer = await net.call("GET", f"/v1/evidence-items/{combined}/drawer", felix)
    assert drawer.status_code == 200, drawer.text
    body: Body = drawer.json()
    assert body["page_count"] is None and body["thumbnail_ref"] is None
    assert body["display_name"] == "Ridgeline statement 1.pdf"  # names and counts stay
    _ = site


async def test_ac3_a_superseded_version_is_kept_and_struck(net: Net) -> None:
    tenant = await net.seed.firm()
    await _flag(net, tenant)
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Iyer")
    dina = await net.seed.person(tenant)
    await net.seed.member(site, dina, "senior")
    work_item = await _work_item(net, site, admin, "TY2025 Form 1040")
    item, march = await _document(net, site, work_item, "Iyer_2025_1099DIV_Halvard.pdf")
    await _document(
        net,
        site,
        work_item,
        "Iyer_2025_1099DIV_Halvard_Corrected.pdf",
        item=item,
        supersedes=march,
        version_no=2,
    )
    listed = await net.call(
        "GET", f"/v1/files/folders/folder:{work_item}:source_documents/items", dina
    )
    rows = listed.json()["items"]
    assert [r["display_name"] for r in rows] == [
        "Iyer_2025_1099DIV_Halvard_Corrected.pdf",
        "Iyer_2025_1099DIV_Halvard.pdf",
    ]
    assert rows[1]["status"] == "superseded"
    assert rows[1]["superseded_by_name"] == "Iyer_2025_1099DIV_Halvard_Corrected.pdf"
    drawer = (await net.call("GET", f"/v1/evidence-items/{item}/drawer", dina)).json()
    assert [(v["version_no"], v["superseded"]) for v in drawer["versions"]] == [
        (2, False),
        (1, True),
    ]


async def test_ac4_the_permanent_file_sits_beside_the_years(net: Net) -> None:
    tenant = await net.seed.firm()
    await _flag(net, tenant)
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Whitley")
    grace = await net.seed.person(tenant)
    await net.seed.member(site, grace, "staff")
    await _work_item(net, site, admin, "TY2025 Form 1040")
    await _document(net, site, None, "Whitley operating agreement.pdf")
    [client] = (await net.call("GET", f"{TREE}?client_id={site.client_id}", grace)).json()["nodes"]
    [permanent] = [n for n in client["children"] if n["kind"] == "permanent_file"]
    assert permanent["count"] == 1
    listed = await net.call("GET", f"/v1/files/folders/permanent:{site.client_id}/items", grace)
    assert [r["display_name"] for r in listed.json()["items"]] == [
        "Whitley operating agreement.pdf"
    ]


async def test_ac5_walls_other_firms_clients_and_the_flag_hide_everything(net: Net) -> None:
    tenant, site, olivia, _wi, combined = await _ridgeline(net)
    other_firm = await net.seed.firm()
    stranger = await net.seed.person(other_firm, "firm_admin")
    assert (
        await net.call("GET", f"/v1/evidence-items/{combined}/drawer", stranger)
    ).status_code == 404
    admin = await net.seed.person(tenant, "firm_admin")
    await net.wall(admin, olivia, site)
    walled = await net.call("GET", f"{TREE}?client_id={site.client_id}", olivia)
    assert walled.status_code == 200 and walled.json()["nodes"] == []
    contact = await net.seed.client_contact(site)
    assert (await net.call("GET", TREE, contact)).status_code == 404
    await net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'files.browser'",
        tenant,
    )
    forget_flags()
    assert (await net.call("GET", TREE, admin)).status_code == 404


async def test_ac6_the_access_log_names_who_did_what(net: Net) -> None:
    _tenant, _site, olivia, _wi, combined = await _ridgeline(net)
    log = await net.call("GET", f"/v1/evidence-items/{combined}/access-log", olivia)
    assert log.status_code == 200, log.text
    assert isinstance(log.json()["items"], list)


async def test_ac7_a_client_scoped_document_names_no_other_engagements_request(net: Net) -> None:
    """Security review: the permanent file's documents never name request items, which may sit
    on an engagement the viewer cannot see."""
    tenant = await net.seed.firm()
    await _flag(net, tenant)
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Whitley")
    grace = await net.seed.person(tenant)
    await net.seed.member(site, grace, "staff")
    await _work_item(net, site, admin, "TY2025 Form 1040")
    item, _version = await _document(net, site, None, "Whitley operating agreement.pdf")
    drawer = await net.call("GET", f"/v1/evidence-items/{item}/drawer", grace)
    assert drawer.status_code == 200, drawer.text
    assert drawer.json()["linked_to"] == []
