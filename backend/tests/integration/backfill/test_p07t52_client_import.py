"""P-07-T52: CLI-06's bulk import, live (DEC-643). "The 212-row file imports 210 records with 2
skipped and 0 new clients, and a re-run changes nothing" (Story 3.2), on a small file with the
same shape: every row matched or decided, two skipped, nothing new.

HTTP through `create_app()` behind `clients.v2`; the workflow's dispatch is captured and its
activities' functions run in-process (`apply_import`, `complete_import`); rows are read back as
the superuser. The independent suite is P-07-T51's.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

import httpx
import pytest

from abacus.kernel.crypto import seal
from abacus.modules.engagements import client_import
from abacus.modules.organisations.api import fingerprint_tin

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
IMPORTS: Final = "/v1/client-imports"
HEAD: Final = "Client Name,Client Type,Federal ID Number,Primary Contact,Email Address\n"
EIN: Final = "984512345"  # a synthetic EIN (98-4512345)
ITIN: Final = "912-70-0001"  # a 9xx fake, ITIN-shaped


@dataclass
class World:
    net: Net
    seed: Seeder
    tenant: uuid.UUID
    grace: Person  # firm admin
    kira: Person  # staff: no `client_import.run`
    copperleaf: uuid.UUID  # holds the EIN, under another name
    harborline: uuid.UUID
    marker: str

    async def call(
        self,
        method: str,
        path: str,
        who: Person | None = None,
        body: Mapping[str, object] | None = None,
        *,
        key: str | None = None,
    ) -> httpx.Response:
        headers = self.net.headers(who or self.grace)
        if key is not None:
            headers["Idempotency-Key"] = key
        return await self.net.http.request(method, path, json=body, headers=headers)

    async def upload(
        self, content: str, *, source: str = "cch_axcess_tax_export"
    ) -> httpx.Response:
        headers = self.net.headers(self.grace)
        headers["Content-Type"] = "text/csv"
        return await self.net.http.post(
            IMPORTS,
            params={"source": source, "filename": "clients.csv"},
            content=content.encode(),
            headers=headers,
        )

    async def count(self, sql: str) -> int:
        return int(cast(int, await self.seed.value(sql, self.tenant)))


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


async def _client(seed: Seeder, tenant: uuid.UUID, name: str) -> tuple[uuid.UUID, uuid.UUID]:
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", tenant, name
        ),
    )
    entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            client,
            name,
        ),
    )
    return client, entity


@pytest.fixture
async def w(net: Net, monkeypatch: pytest.MonkeyPatch) -> World:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'clients.v2', 'true', 'test-seed', 'P-07-T52')",
        tenant,
    )
    grace = await seed.person(tenant, "firm_admin")
    kira = await seed.person(tenant)
    marker = uuid.uuid4().hex[:6]
    copperleaf, copperleaf_entity = await _client(seed, tenant, f"Copperleaf Outfitters {marker}")
    harborline, _ = await _client(seed, tenant, f"Harborline Marine {marker}")
    sealed = await seal(tenant, EIN.encode(), f"client_entity_tin:{copperleaf_entity}")
    await seed.run(
        "UPDATE client_entities SET tin_sealed = $2, tin_last4 = '2345', tin_kind = 'ein', "
        "tin_status = 'on_file', tin_fingerprint = $3 WHERE id = $1",
        copperleaf_entity,
        sealed,
        fingerprint_tin(tenant, EIN),
    )

    async def dispatch(_workflow: object, _given: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(client_import, "dispatch", dispatch)
    return World(net, seed, tenant, grace, kira, copperleaf, harborline, marker)


def _file(w: World) -> str:
    m = w.marker
    return HEAD + "\n".join(
        [
            f"CL Outfitters Holdings {m},S Corporation,98-4512345,Tess Moreno,"
            f"tess.{m}@example.test",
            f"Harborline Marine {m},Partnership,,Ben Ashby,ben.{m}@example.test",
            f"Harborline Maritime Group {m},Partnership,,,",
            f'=HYPERLINK("x") ‮Quill {m},Individual,{ITIN},,',
            f"Zephyr Garden Supply {m},LLC,,,",
        ]
    )


async def _rows(w: World, import_id: object) -> list[Json]:
    page = _json(await w.call("GET", f"{IMPORTS}/{import_id}/rows"))
    return cast(list[Json], page["items"])


async def test_upload_maps_scores_and_keeps_cells_inert(w: World) -> None:
    made = _json(await w.upload(_file(w)), 201)
    assert made["stage"] == "reviewing"
    assert made["mapping"] == {
        "Client Name": "client_name",
        "Client Type": "entity_type",
        "Federal ID Number": "ein",
        "Primary Contact": "contact_name",
        "Email Address": "email",
    }
    counts = cast(Json, made["counts"])
    assert (counts["rows"], counts["matched"], counts["new"]) == (5, 2, 2)
    assert counts["to_review"] == 1
    rows = await _rows(w, made["id"])
    by_no = {cast(int, r["row_no"]): r for r in rows}
    # The EIN matches Copperleaf under another name: 1.0, merged without a person.
    assert by_no[1]["best_match_client_id"] == str(w.copperleaf)
    assert (by_no[1]["score"], by_no[1]["decision"]) == (1.0, "merge")
    assert by_no[1]["tin"] == {"kind": "ein", "presence": "on_file", "last4": "2345"}
    assert (by_no[2]["best_match_client_id"], by_no[2]["decision"]) == (str(w.harborline), "merge")
    assert by_no[3]["decision"] is None and cast(float, by_no[3]["score"]) < 0.9
    # Bidi controls removed, the formula kept as inert text; the ITIN dropped on a real firm.
    assert "‮" not in cast(str, by_no[4]["display_name"])
    assert cast(str, by_no[4]["display_name"]).startswith("=HYPERLINK")
    assert by_no[4]["tin"] is None
    notes = await w.seed.value(
        "SELECT parsed->'notes' FROM client_import_rows WHERE import_id = $1 AND row_no = 4",
        uuid.UUID(cast(str, made["id"])),
    )
    assert {"bidi_removed", "formula_like", "tin_kind_not_allowed"} <= set(
        cast(list[str], _loads(notes))
    )
    assert not await w.count(
        "SELECT count(*) FROM client_import_rows WHERE tenant_id = $1 AND tin_kind = 'itin'"
    )


def _loads(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


async def test_the_run_imports_the_rest_skips_two_and_a_rerun_changes_nothing(w: World) -> None:
    made = _json(await w.upload(_file(w)), 201)
    import_id = cast(str, made["id"])
    rows = {cast(int, r["row_no"]): r for r in await _rows(w, import_id)}
    decide = f"{IMPORTS}/{import_id}/rows"
    _json(
        await w.call(
            "PUT",
            f"{decide}/{rows[3]['id']}/decision",
            body={"decision": "merge", "merge_client_id": str(w.harborline)},
        )
    )
    for n in (4, 5):
        _json(await w.call("PUT", f"{decide}/{rows[n]['id']}/decision", body={"decision": "skip"}))
    clients_before = await w.count("SELECT count(*) FROM clients WHERE tenant_id = $1")

    started = _json(await w.call("POST", f"{IMPORTS}/{import_id}/run", key="run-1"), 202)
    assert started["stage"] == "importing"
    tenant, iid = w.tenant, uuid.UUID(import_id)
    assert await client_import.apply_import(tenant, iid) == 3
    assert await client_import.complete_import(tenant, iid) == "done"

    done = _json(await w.call("GET", f"{IMPORTS}/{import_id}"))
    counts = cast(Json, done["counts"])
    assert (counts["imported"], counts["skipped"], counts["new"]) == (3, 2, 0)
    assert await w.count("SELECT count(*) FROM clients WHERE tenant_id = $1") == clients_before
    emails = await w.count(
        "SELECT count(*) FROM contacts WHERE tenant_id = $1 AND email LIKE '%@example.test'"
    )
    assert emails == 2  # Tess on Copperleaf, Ben on Harborline

    # A re-run: the same key answers the same; another key is refused; the activity applies
    # nothing again.
    again = _json(await w.call("POST", f"{IMPORTS}/{import_id}/run", key="run-1"), 202)
    assert again["id"] == import_id
    refused = await w.call("POST", f"{IMPORTS}/{import_id}/run", key="run-2")
    assert refused.status_code == 409 and refused.json()["detail"] == "import_already_run"
    with pytest.raises(client_import.ImportNotRunnable):
        await client_import.apply_import(tenant, iid)
    assert await w.count("SELECT count(*) FROM clients WHERE tenant_id = $1") == clients_before
    late = await w.call("PUT", f"{decide}/{rows[3]['id']}/decision", body={"decision": "skip"})
    assert late.status_code == 409


async def test_new_rows_create_clients_once(w: World) -> None:
    made = _json(await w.upload(_file(w)), 201)
    import_id = cast(str, made["id"])
    rows = {cast(int, r["row_no"]): r for r in await _rows(w, import_id)}
    _json(
        await w.call(
            "PUT",
            f"{IMPORTS}/{import_id}/rows/{rows[3]['id']}/decision",
            body={"decision": "skip"},
        )
    )
    before = await w.count("SELECT count(*) FROM clients WHERE tenant_id = $1")
    _json(await w.call("POST", f"{IMPORTS}/{import_id}/run", key="run-new"), 202)
    iid = uuid.UUID(import_id)
    await client_import.apply_import(w.tenant, iid)
    # A retried activity (the workflow's retry) applies nothing twice.
    assert await client_import.apply_import(w.tenant, iid) == 0
    await client_import.complete_import(w.tenant, iid)
    assert await w.count("SELECT count(*) FROM clients WHERE tenant_id = $1") == before + 2
    counts = cast(Json, _json(await w.call("GET", f"{IMPORTS}/{import_id}"))["counts"])
    assert (counts["new"], counts["skipped"]) == (2, 1)


async def test_decisions_are_checked_and_audited(w: World) -> None:
    made = _json(await w.upload(_file(w)), 201)
    import_id = cast(str, made["id"])
    rows = {cast(int, r["row_no"]): r for r in await _rows(w, import_id)}
    path = f"{IMPORTS}/{import_id}/rows/{rows[5]['id']}/decision"
    # Row 5 has no match: nothing to keep both with, nothing to merge into.
    for body in ({"decision": "keep_both"}, {"decision": "merge"}):
        refused = await w.call("PUT", path, body=body)
        assert refused.status_code == 422 and refused.json()["detail"] == "import_row_invalid"
    refused = await w.call(
        "PUT", path, body={"decision": "skip", "merge_client_id": str(w.harborline)}
    )
    assert refused.status_code == 422
    _json(await w.call("PUT", path, body={"decision": "skip"}))
    assert (
        await w.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'client_import.row_decided'"
        )
        == 1
    )
    # Staff hold no `client_import.run`.
    assert (await w.call("GET", f"{IMPORTS}/{import_id}", w.kira)).status_code == 403


async def test_a_file_the_import_cannot_read_is_refused(w: World) -> None:
    for content, source, reason in (
        ("Name,Type\nAcme,LLC\n", "cch_axcess_tax_export", "not_cch_export"),
        ("Code,Type\nA1,LLC\n", "csv", "no_name_column"),
        (HEAD, "csv", "no_rows"),
    ):
        refused = await w.upload(content, source=source)
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"] == "import_file_invalid"
        assert refused.json()["facts"] == {"reason": reason}
    assert not await w.count("SELECT count(*) FROM client_imports WHERE tenant_id = $1")


async def test_the_file_is_kept_sealed_and_erased_after_thirty_days(w: World) -> None:
    made = _json(await w.upload(_file(w)), 201)
    iid = uuid.UUID(cast(str, made["id"]))
    kept = await w.seed.rows(
        "SELECT file_sealed IS NOT NULL AS kept, erase_after - started_at AS window "
        "FROM client_imports WHERE id = $1",
        iid,
    )
    assert kept[0]["kept"] and kept[0]["window"].days == 30
    await w.seed.run(
        "UPDATE client_imports SET erase_after = clock_timestamp() - interval '1 second' "
        "WHERE id = $1",
        iid,
    )
    assert await client_import.erase_files() >= 1
    gone = await w.seed.rows(
        "SELECT file_sealed IS NULL AS erased, erased_at IS NOT NULL AS stamped, file_sha256 "
        "FROM client_imports WHERE id = $1",
        iid,
    )
    assert gone[0]["erased"] and gone[0]["stamped"] and gone[0]["file_sha256"]
    assert not await w.count(
        "SELECT count(*) FROM client_import_rows WHERE tenant_id = $1 AND tin_sealed IS NOT NULL"
    )
