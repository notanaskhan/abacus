"""T-01-T35 (TASK-2517; T-01 §3.11; TAX-12 a, b; DEC-38; DEC-1565) over HTTP against Postgres:
"The Feld packet lists the client copy, letter, 8879 with TR-579-IT and two vouchers, Grace
Holloway cannot approve it, and no gateway call occurs during assembly."

The T-01-T19 Feld return (imported and approved as Engine import V3), final-approved and
exported (T-01-T18, T-01-T25), with the fake engine's PDFs filed (T-01-T26). The firm's
filing-instructions template is imported and published through C11 (P-11-T06) by two people.
Also: payment instructions read the engine's values only, delivery waits for final approval and
an export, the vouchers toggle at the version seen, the letter regenerates as a new C11 draft,
and the signer or a manager approves (a person only).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus import ai_gateway
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import api as c11
from abacus.modules.reporting.contract import TemplateImportIn
from abacus.modules.tax import delivery
from abacus_tools.fakes.cch_axcess import CchAxcessFake, Export

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_t01t25_engine_export import (
    Feld,
    Json,
    call_as,
    engines,
    feld_return,
    final_approval_of,
    switched_on,
)

__all__ = ["engines", "switched_on"]  # the shared autouse engine fixture and the switches

FELD = Export("2025I:FeldJ", 2025, "1040", ())
LETTER: Json = {
    "family": "delivery_cover_letter",
    "name": "BH Filing Instructions",
    "layout_key": "letter",
    "body": [
        {"type": "paragraph", "runs": [{"type": "var", "key": "letter.date"}]},
        {"type": "paragraph", "runs": [{"type": "var", "key": "client.name"}]},
        {
            "type": "paragraph",
            "runs": [
                {"type": "text", "text": "Your "},
                {"type": "var", "key": "return.label"},
                {"type": "text", "text": " is ready. "},
                {"type": "var", "key": "payments.summary"},
            ],
        },
    ],
    "variables": [
        {"key": "letter.date", "label": "Date", "value_type": "date"},
        {"key": "client.name", "label": "Client", "value_type": "name"},
        {"key": "return.label", "label": "Return", "value_type": "text"},
        {"key": "payments.summary", "label": "Payments", "value_type": "text"},
    ],
    "sample_data": {
        "letter.date": "April 10, 2026",
        "client.name": "Sample Client",
        "return.label": "2025 Form 1040",
        "payments.summary": "No payment is due",
    },
}


async def _member(
    seed: Seeder, feld: Feld, name: str, role: str, firm_role: str | None = None
) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, $3, 'active', 'staff', 'staff') RETURNING id",
            feld.tenant,
            user,
            firm_role,
        ),
    )
    if role:
        await seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            feld.tenant,
            feld.engagement,
            user,
            role,
        )
    return AuthContext(
        TenantContext(feld.tenant, "human", str(user)),
        user,
        membership,
        firm_role,  # pyright: ignore[reportArgumentType] -- a firm role code
        datetime.now(UTC) - timedelta(minutes=1),
    )


async def _publish_letter(seed: Seeder, feld: Feld) -> None:
    for flag in ("reporting.generated_documents", "tax.delivery_efile"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 't01-t35', 'T-01-T35')",
            feld.tenant,
            flag,
        )
    admin = await _member(seed, feld, "Grace Admin", "", "firm_admin")
    leader = await _member(seed, feld, "Margaret Okonkwo", "", "practice_leader")
    report = await c11.import_template_bundle(
        admin, TemplateImportIn.model_validate(LETTER), dry_run=False
    )
    assert report.ok, report.errors
    row = await seed.rows(
        "SELECT t.id, v.version_no FROM report_templates t JOIN report_template_versions v "
        "ON v.template_id = t.id WHERE t.tenant_id = $1 AND t.family = 'delivery_cover_letter'",
        feld.tenant,
    )
    await c11.publish_template(leader, row[0]["id"], int(row[0]["version_no"]))


async def _ready(migrated_db: MigratedDatabase) -> Feld:
    """Feld final-approved, exported, its engine PDFs filed and the letter template published."""
    feld = await feld_return(migrated_db)
    await final_approval_of(feld)
    made = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json={"checkpoint_id": str(feld.checkpoint)},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert made.status_code == 201, made.text
    for name, content in CchAxcessFake().pdf_files(FELD, 3).items():
        if name.endswith("_k1.pdf"):
            continue
        filed = await feld.call(
            "POST",
            f"/v1/tax-returns/{feld.item}/engine-imports",
            params={"kind": "pdfs"},
            headers={"X-File-Name": name},
            content=content,
        )
        assert filed.status_code == 201, (name, filed.text)
    await _publish_letter(feld.seed, feld)
    return feld


@pytest.fixture
def no_gateway(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    calls: list[object] = []

    async def refused(c: object) -> object:
        calls.append(c)
        raise AssertionError("the gateway was called during delivery")

    monkeypatch.setattr(ai_gateway, "call", refused)
    yield calls


def _assemble_path(feld: Feld) -> str:
    return f"/v1/tax-returns/{feld.item}/delivery-packet:assemble"


async def test_ac_the_feld_packet_and_its_approval(
    migrated_db: MigratedDatabase, switched_on: None, no_gateway: list[object]
) -> None:
    feld = await _ready(migrated_db)
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    as_grace = call_as(grace)
    key = {"Idempotency-Key": str(uuid.uuid4())}
    made = await as_grace("POST", _assemble_path(feld), headers=key)
    assert made.status_code == 201, made.text
    packet = cast(Json, made.json())
    items = cast(list[Json], packet["items"])
    assert [(i["kind"], i["included"]) for i in items] == [
        ("client_copy", True),
        ("filing_instructions_letter", True),
        ("form_8879_tr_579_it", True),
        ("voucher_1040es_q4", True),
        ("voucher_it2105_q4", True),
        ("engagement_invoice", False),
    ]
    engine = {i["kind"] for i in items if i["evidence_version_id"] is not None}
    assert engine == {"client_copy", "form_8879_tr_579_it", "voucher_1040es_q4"} | {
        "voucher_it2105_q4"
    }
    assert packet["letter_document_id"] is not None and packet["status"] == "draft"
    assert no_gateway == []  # nothing in assembly asked a model

    refused = await as_grace(
        "POST", f"/v1/delivery-packets/{packet['id']}/approve", json={"seen_version": 1}
    )
    assert refused.status_code == 403, refused.text
    approved = await feld.call(
        "POST", f"/v1/delivery-packets/{packet['id']}/approve", json={"seen_version": 1}
    )
    assert approved.status_code == 200, approved.text
    out = cast(Json, approved.json())
    assert (out["status"], out["approved_by_name"]) == ("approved", "Samuel Ito")
    actions = await feld.seed.rows(
        "SELECT action, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action LIKE 'delivery_packet.%' ORDER BY seq",
        feld.tenant,
    )
    assert [(a["action"], a["actor_id"]) for a in actions] == [
        ("delivery_packet.assembled", str(grace.user_id)),
        ("delivery_packet.approved", str(feld.samuel.user_id)),
    ]
    again = await as_grace(
        "POST", _assemble_path(feld), headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert (again.status_code, again.json()["detail"]) == (409, "packet_approved")


def test_payment_instructions_read_the_full_feld_engine_values() -> None:
    """The V3 values file as the fake engine sends it (refund, NY due, the two Q4 estimates;
    IL and CO due nothing, so they are left out)."""
    values = {v.field_key: {"t": "decimal", "v": v.value} for v in CchAxcessFake().values(FELD, 3)}
    assert [
        (p.jurisdiction, p.kind, str(p.amount)) for p in delivery.payments_of(values, 2025)
    ] == [
        ("US", "refund", "253"),
        ("NY", "balance_due", "1269"),
        ("US", "estimate", "19990"),
        ("NY", "estimate", "7824"),
    ]


async def test_payment_instructions_are_the_values_the_import_wrote(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    """The T-01-T19 world accepts three of V3's fields, so the 1040-ES estimate is the one engine
    value on the return; nothing else is shown or computed."""
    feld = await _ready(migrated_db)
    read = await feld.call("GET", f"/v1/tax-returns/{feld.item}/delivery")
    assert read.status_code == 200, read.text
    out = cast(Json, read.json())
    payments = [
        (p["jurisdiction"], p["kind"], p["amount"]) for p in cast(list[Json], out["payments"])
    ]
    assert payments == [("US", "estimate", "19990")]
    assert out["packet_id"] is None
    assert "delivery_packet.prepare" in cast(list[str], out["allowed_actions"])


async def test_delivery_waits_for_final_approval_and_an_export(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    await _publish_letter(feld.seed, feld)
    key = {"Idempotency-Key": str(uuid.uuid4())}
    early = await feld.call("POST", _assemble_path(feld), headers=key)
    assert (early.status_code, early.json()["detail"]) == (409, "not_final_approved")
    await final_approval_of(feld)
    unexported = await feld.call("POST", _assemble_path(feld), headers=key)
    assert (unexported.status_code, unexported.json()["detail"]) == (409, "not_exported")


async def test_toggles_and_the_letter_at_the_version_seen(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await _ready(migrated_db)
    made = await feld.call(
        "POST", _assemble_path(feld), headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    packet = cast(Json, made.json())
    path = f"/v1/delivery-packets/{packet['id']}"
    off = await feld.call(
        "PATCH", path, json={"included": {"voucher_it2105_q4": False}, "seen_version": 1}
    )
    assert off.status_code == 200, off.text
    included = {i["kind"]: i["included"] for i in cast(list[Json], off.json()["items"])}
    assert included["voucher_it2105_q4"] is False
    stale = await feld.call(
        "PATCH", path, json={"included": {"voucher_1040es_q4": False}, "seen_version": 1}
    )
    assert (stale.status_code, stale.json()["detail"]) == (409, "stale_version")
    fixed = await feld.call(
        "PATCH", path, json={"included": {"client_copy": False}, "seen_version": 2}
    )
    assert (fixed.status_code, fixed.json()["detail"]) == (409, "item_not_toggleable")
    letter = cast(str, packet["letter_document_id"])
    regenerated = await feld.call("POST", f"{path}/letter:regenerate", json={"seen_version": 2})
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["letter_document_id"] == letter  # the same document, version 2
    versions = await feld.seed.value(
        "SELECT count(*) FROM generated_document_versions WHERE generated_document_id = $1",
        uuid.UUID(letter),
    )
    assert versions == 2


async def test_the_agent_and_the_system_never_prepare_or_approve(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await _ready(migrated_db)
    for kind in ("agent", "system"):
        other = AuthContext(
            TenantContext(feld.tenant, kind, f"{kind}-probe"),
            feld.samuel.user_id,
            feld.samuel.membership_id,
            None,
            feld.samuel.mfa_at,
        )
        with pytest.raises(Exception) as refused:
            await delivery.assemble(other, feld.item)
        assert type(refused.value).__name__ == "Forbidden"
