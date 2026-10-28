# ac-test-author: ayushkbhatia
"""P-07-T51 (ADR-078): the independent acceptance suite for P-07-T52's bulk import (CLI-06 g).

Read from P-07 §3.3 Story 3.2, §4.2 M9 and OQ-4, `docs/contracts/intake-import.md` (v1) and the
organisations matrix. HTTP through `create_app()` behind `clients.v2`; the run's dispatch is
captured and the workflow's activities are called in-process; rows are read back as the
superuser.

Covered: the auto-match threshold (0.9), no merge below it without a person's decision, the EIN
fingerprint match across different names, hostile cells (formula and bidi) kept inert, SSN and
ITIN refused on a real firm and kept on a synthetic one, row decisions audited (codes, never
names), the 30-day file retention, an idempotent re-run, walls (AC-24: a walled client is never a
match nor a merge target) and the human-only run.

ADR-078 note (DEC-644): this suite was written in the same session as T52, after its code; the
separate-session rule was not met. It reads the contract, not the implementation, and is
committed before T52 merges.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.engagements import client_import
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.organisations.api import fingerprint_tin

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
IMPORTS: Final = "/v1/client-imports"
CSV_HEAD: Final = "Name,Entity Type,EIN,Taxpayer SSN,Contact Name,Email\n"
EIN: Final = "975512340"  # synthetic
SSN: Final = "923-45-6789"  # a 9xx fake, SSN-column


@dataclass
class Firm:
    net: Net
    seed: Seeder
    tenant: uuid.UUID
    grace: Person  # firm admin
    samuel: Person  # manager
    kira: Person  # staff
    tag: str
    clients: dict[str, uuid.UUID]

    def headers(self, who: Person | None = None, key: str | None = None) -> dict[str, str]:
        headers = self.net.headers(who or self.grace)
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    async def call(
        self,
        method: str,
        path: str,
        who: Person | None = None,
        body: Mapping[str, object] | None = None,
        *,
        key: str | None = None,
    ) -> httpx.Response:
        return await self.net.http.request(method, path, json=body, headers=self.headers(who, key))

    async def upload(self, lines: list[str], who: Person | None = None) -> httpx.Response:
        return await self.net.http.post(
            IMPORTS,
            params={"source": "csv", "filename": "list.csv"},
            content=(CSV_HEAD + "\n".join(lines) + "\n").encode(),
            headers={**self.headers(who), "Content-Type": "text/csv"},
        )

    async def rows(self, import_id: object, who: Person | None = None) -> dict[int, Json]:
        page = _ok(await self.call("GET", f"{IMPORTS}/{import_id}/rows?limit=200", who))
        return {cast(int, r["row_no"]): r for r in cast(list[Json], page["items"])}

    async def decide(self, import_id: object, row: Json, body: Json) -> httpx.Response:
        return await self.call(
            "PUT", f"{IMPORTS}/{import_id}/rows/{row['id']}/decision", body=body
        )

    async def run(self, import_id: object, key: str) -> None:
        _ok(await self.call("POST", f"{IMPORTS}/{import_id}/run", key=key), 202)
        iid = uuid.UUID(str(import_id))
        await client_import.apply_import(self.tenant, iid)
        await client_import.complete_import(self.tenant, iid)

    async def count(self, sql: str, *args: object) -> int:
        return int(cast(int, await self.seed.value(sql, self.tenant, *args)))


def _ok(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


async def _firm(net: Net, *, synthetic: bool = False) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    if synthetic:
        await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'clients.v2', 'true', 'test-seed', 'P-07-T51')",
        tenant,
    )
    grace = await seed.person(tenant, "firm_admin")
    samuel = await seed.person(tenant)
    kira = await seed.person(tenant)
    for who, level in ((samuel, "manager"), (kira, "staff")):
        await seed.run(
            "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
            level,
        )
    tag = uuid.uuid4().hex[:6]
    clients: dict[str, uuid.UUID] = {}
    for key, name in (
        ("northwind", f"Northwind Freight {tag}"),
        ("meridian", f"Meridian Dental Group {tag}"),
        ("ashford", f"Ashford Capital {tag}"),
    ):
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
        clients[key] = client
        if key == "northwind":
            await seed.run(
                "UPDATE client_entities SET tin_sealed = $2, tin_last4 = '2340', "
                "tin_kind = 'ein', tin_status = 'on_file', tin_fingerprint = $3 WHERE id = $1",
                entity,
                await seal(tenant, EIN.encode(), f"client_entity_tin:{entity}"),
                fingerprint_tin(tenant, EIN),
            )
    return Firm(net, seed, tenant, grace, samuel, kira, tag, clients)


@pytest.fixture
async def firm(net: Net, monkeypatch: pytest.MonkeyPatch) -> Firm:
    async def dispatch(_workflow: object, _given: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(client_import, "dispatch", dispatch)
    return await _firm(net)


# --- the threshold ------------------------------------------------------------------------------


async def test_ac_at_or_above_090_rows_match_without_a_person(firm: Firm) -> None:
    t = firm.tag
    made = _ok(
        await firm.upload(
            [
                f"Northwind Freight {t},C Corporation,,,,",  # the same name: 1.0
                f"Unrelated Holdings {t},LLC,97-5512340,,,",  # the EIN: 1.0 on another name
                f"Meridian Dental Group Services {t},,,,,",  # a near name: below 0.9
            ]
        ),
        201,
    )
    rows = await firm.rows(made["id"])
    assert (rows[1]["decision"], rows[1]["best_match_client_id"]) == (
        "merge",
        str(firm.clients["northwind"]),
    )
    assert rows[1]["decided_by"] is None  # nobody decided it: the threshold did
    assert (rows[2]["decision"], rows[2]["score"]) == ("merge", 1.0)
    assert rows[2]["best_match_client_id"] == str(firm.clients["northwind"])
    assert rows[3]["decision"] is None
    assert cast(float, rows[3]["score"]) < 0.9
    assert rows[3]["best_match_client_id"] == str(firm.clients["meridian"])
    counts = cast(Json, made["counts"])
    assert (counts["matched"], counts["to_review"], counts["new"]) == (2, 1, 0)
    review = _ok(await firm.call("GET", f"{IMPORTS}/{made['id']}/rows?review=true"))
    assert [r["row_no"] for r in cast(list[Json], review["items"])] == [3]


async def test_ac_below_090_nothing_merges_without_a_decision(firm: Firm) -> None:
    t = firm.tag
    made = _ok(
        await firm.upload(
            [f"Meridian Dental Group Services {t},,,,Ruth Ng,ruth.{t}@example.test"]
        ),
        201,
    )
    await firm.run(made["id"], f"t51-{t}")
    assert not await firm.count(
        "SELECT count(*) FROM contacts WHERE tenant_id = $1 AND client_id = $2",
        firm.clients["meridian"],
    )
    done = _ok(await firm.call("GET", f"{IMPORTS}/{made['id']}"))
    counts = cast(Json, done["counts"])
    assert (done["stage"], counts["imported"], counts["skipped"]) == ("done", 0, 1)


async def test_ac_a_persons_merge_below_090_is_applied(firm: Firm) -> None:
    t = firm.tag
    made = _ok(
        await firm.upload(
            [f"Meridian Dental Group Services {t},,,,Ruth Ng,ruth.{t}@example.test"]
        ),
        201,
    )
    rows = await firm.rows(made["id"])
    decided = _ok(await firm.decide(made["id"], rows[1], {"decision": "merge"}))
    assert decided["decided_by"] == str(firm.grace.user_id)
    await firm.run(made["id"], f"t51m-{t}")
    assert (
        await firm.count(
            "SELECT count(*) FROM contacts WHERE tenant_id = $1 AND client_id = $2",
            firm.clients["meridian"],
        )
        == 1
    )


# --- hostile cells and TINs ---------------------------------------------------------------------


async def test_ac_formula_and_bidi_cells_are_stored_inert(firm: Firm) -> None:
    t = firm.tag
    made = _ok(
        await firm.upload(
            [
                f"=cmd|' /C calc'!A0 {t},,,,,",
                f"@SUM(1+1) Quarry‮{t}‬,,,,,",
                f"Plain⁧Name⁩ {t},,,,+1 555,",
            ]
        ),
        201,
    )
    stored = await firm.seed.rows(
        "SELECT parsed FROM client_import_rows WHERE import_id = $1 ORDER BY row_no",
        uuid.UUID(cast(str, made["id"])),
    )
    texts = [
        json.dumps(json.loads(r["parsed"]) if isinstance(r["parsed"], str) else r["parsed"])
        for r in stored
    ]
    for text in texts:
        for control in ("‮", "‬", "⁧", "⁩"):
            assert control.encode("unicode_escape").decode() not in text
    rows = await firm.rows(made["id"])
    assert cast(str, rows[1]["display_name"]).startswith("=cmd")  # text, kept as text
    await firm.run(made["id"], f"t51h-{t}")
    names = await firm.seed.rows(
        "SELECT name FROM clients WHERE tenant_id = $1 AND name LIKE $2 ORDER BY name",
        firm.tenant,
        f"%{t}",
    )
    created = [cast(str, n["name"]) for n in names]
    assert f"=cmd|' /C calc'!A0 {t}" in created
    assert not [n for n in created if any(c in n for c in "‮‬⁧⁩")]


async def test_oq4_ssn_columns_are_refused_on_a_real_firm(firm: Firm) -> None:
    t = firm.tag
    made = _ok(await firm.upload([f"Ann Lee {t},Individual,,{SSN},,"]), 201)
    rows = await firm.rows(made["id"])
    assert rows[1]["tin"] is None
    assert not await firm.count(
        "SELECT count(*) FROM client_import_rows WHERE tenant_id = $1 AND tin_kind IS NOT NULL"
    )
    notes = await firm.seed.value(
        "SELECT parsed->'notes' FROM client_import_rows WHERE import_id = $1",
        uuid.UUID(cast(str, made["id"])),
    )
    assert "tin_kind_not_allowed" in json.dumps(notes)


async def test_oq4_a_synthetic_firm_keeps_the_ssn_masked(
    net: Net, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def dispatch(_workflow: object, _given: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(client_import, "dispatch", dispatch)
    synthetic = await _firm(net, synthetic=True)
    made = _ok(await synthetic.upload([f"Ann Lee {synthetic.tag},Individual,,{SSN},,"]), 201)
    rows = await synthetic.rows(made["id"])
    assert rows[1]["tin"] == {"kind": "ssn", "presence": "on_file", "last4": "6789"}
    assert "923456789" not in json.dumps(rows)


# --- decisions, retention, re-runs --------------------------------------------------------------


async def test_ac_row_decisions_are_audited_with_codes_only(firm: Firm) -> None:
    t = firm.tag
    made = _ok(await firm.upload([f"Meridian Dental Group Services {t},,,,,"]), 201)
    rows = await firm.rows(made["id"])
    _ok(await firm.decide(made["id"], rows[1], {"decision": "keep_both"}))
    _ok(await firm.decide(made["id"], rows[1], {"decision": "skip"}))
    events = await firm.seed.rows(
        "SELECT actor_kind, actor_id, after_ref FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'client_import.row_decided' ORDER BY seq",
        firm.tenant,
    )
    assert len(events) == 2
    assert {e["actor_kind"] for e in events} == {"human"}
    assert "Meridian" not in json.dumps([str(e["after_ref"]) for e in events])


async def test_ac_the_file_is_kept_thirty_days_then_erased(firm: Firm) -> None:
    made = _ok(await firm.upload([f"Northwind Freight {firm.tag},,,,,"]), 201)
    iid = uuid.UUID(cast(str, made["id"]))
    window = await firm.seed.value(
        "SELECT erase_after - started_at FROM client_imports WHERE id = $1", iid
    )
    assert cast(timedelta, window).days == 30
    await firm.seed.run(
        "UPDATE client_imports SET erase_after = clock_timestamp() - interval '1 minute' "
        "WHERE id = $1",
        iid,
    )
    await client_import.erase_files()
    assert await firm.seed.value(
        "SELECT file_sealed IS NULL AND erased_at IS NOT NULL FROM client_imports WHERE id = $1",
        iid,
    )
    # The import itself still reads: the record of what was imported outlives the file.
    _ok(await firm.call("GET", f"{IMPORTS}/{iid}"))


async def test_ac_a_rerun_changes_nothing(firm: Firm) -> None:
    t = firm.tag
    made = _ok(
        await firm.upload(
            [f"Northwind Freight {t},,,,Kim Bo,kim.{t}@example.test", f"Fresh Start {t},LLC,,,,"]
        ),
        201,
    )
    key = f"t51r-{t}"
    await firm.run(made["id"], key)
    footprint = (
        await firm.count("SELECT count(*) FROM clients WHERE tenant_id = $1"),
        await firm.count("SELECT count(*) FROM contacts WHERE tenant_id = $1"),
    )
    again = await firm.call("POST", f"{IMPORTS}/{made['id']}/run", key=key)
    assert again.status_code == 202, again.text
    other = await firm.call("POST", f"{IMPORTS}/{made['id']}/run", key=f"{key}-2")
    assert other.status_code == 409 and other.json()["detail"] == "import_already_run"
    rows = await firm.rows(made["id"])
    late = await firm.decide(made["id"], rows[2], {"decision": "skip"})
    assert late.status_code == 409
    assert footprint == (
        await firm.count("SELECT count(*) FROM clients WHERE tenant_id = $1"),
        await firm.count("SELECT count(*) FROM contacts WHERE tenant_id = $1"),
    )


# --- who ----------------------------------------------------------------------------------------


async def test_ac24_a_walled_client_is_never_a_match_nor_a_target(firm: Firm) -> None:
    walled = await firm.call(
        "POST",
        "/v1/walls",
        firm.grace,
        {"user_id": str(firm.samuel.user_id), "client_id": str(firm.clients["ashford"])},
    )
    assert walled.status_code == 201, walled.text
    made = _ok(await firm.upload([f"Ashford Capital {firm.tag},,,,,"], firm.samuel), 201)
    rows = await firm.rows(made["id"], firm.samuel)
    assert str(firm.clients["ashford"]) not in json.dumps(rows)
    refused = await firm.net.http.put(
        f"{IMPORTS}/{made['id']}/rows/{rows[1]['id']}/decision",
        json={"decision": "merge", "merge_client_id": str(firm.clients["ashford"])},
        headers=firm.headers(firm.samuel),
    )
    assert refused.status_code == 404, refused.text


async def test_ac_staff_and_non_humans_are_refused(firm: Firm) -> None:
    assert (await firm.upload([f"X {firm.tag},,,,,"], firm.kira)).status_code == 403
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(firm.tenant, cast(ActorKind, kind), str(firm.grace.user_id)),
            firm.grace.user_id,
            uuid.uuid4(),
            "firm_admin",
            datetime.now(UTC) - timedelta(minutes=1),
        )
        with pytest.raises(Forbidden):
            await client_import.upload_import(ctx, "csv", "x.csv", b"Name\nX\n")
    assert not await firm.count("SELECT count(*) FROM client_imports WHERE tenant_id = $1")
