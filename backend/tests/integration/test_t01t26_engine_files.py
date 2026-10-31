"""T-01-T26 (TASK-2416; T-01 §3.10; tax-engine-bridge §6; DEC-1464) over HTTP against Postgres:
"The IP PIN diagnostic raises one Action required issue however often the file is re-imported,
and the Ridgeline K-1 PDFs reach T-02's package as engine evidence."

The T-01-T19 Feld return (imported and approved as Engine import V3) carries the engine's files:
the fake engine's IP PIN diagnostics run twice, its K-1 PDF, and its rejected status report.
"""

from __future__ import annotations

from typing import cast

from abacus.modules.tax.engine_files import engine_documents
from abacus_tools.fakes.cch_axcess import CchAxcessFake, Export

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Json, engines, feld_return

__all__ = ["engines"]  # the module's autouse engine fixture, shared

FELD = Export("2025I:FeldJ", 2025, "1040", ())


async def test_ac_the_ip_pin_diagnostic_raises_one_issue_however_often(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    run = CchAxcessFake().diagnostics_file(FELD, 3, "ip_pin")
    for n in range(3):
        uploaded = await feld.call(
            "POST",
            f"/v1/tax-returns/{feld.item}/engine-imports",
            params={"kind": "diagnostics"},
            headers={"X-File-Name": f"2025I_FeldJ_V3_diagnostics_{n}.csv"},
            content=run,
        )
        assert uploaded.status_code == 201, uploaded.text
    issues = await feld.seed.rows(
        "SELECT kind, priority, source_ref FROM issues WHERE work_item_id = $1", feld.item
    )
    assert [(i["kind"], i["source_ref"]) for i in issues] == [
        ("engine_diagnostic", "engine:EF-IPPIN-01:f1040.ip_pin_primary")
    ]
    named = await feld.seed.value(
        "SELECT count(DISTINCT issue_id) FROM engine_diagnostics WHERE return_id = $1 "
        "AND issue_id IS NOT NULL",
        feld.item,
    )
    assert named == 1
    sync = cast(Json, (await feld.call("GET", f"/v1/tax-returns/{feld.item}/engine-sync")).json())
    assert sync["state"] == "failed"


async def test_ac_the_k1_pdf_reaches_the_package_as_engine_evidence(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    files = CchAxcessFake().pdf_files(FELD, 3)
    name = "2025I_FeldJ_V3_k1.pdf"
    uploaded = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": "pdfs"},
        headers={"X-File-Name": name},
        content=files[name],
    )
    assert uploaded.status_code == 201, uploaded.text
    found = await engine_documents(feld.samuel.tenant, feld.item, "k1")
    assert len(found) == 1
    row = await feld.seed.rows(
        "SELECT v.source, v.method, v.channel, i.folder_kind FROM evidence_versions v "
        "JOIN evidence_items i ON i.id = v.evidence_item_id WHERE v.id = $1",
        found[0],
    )
    assert [(r["source"], r["method"], r["channel"], r["folder_kind"]) for r in row] == [
        ("engine_import", "imported", "import", "deliverables")
    ]


async def test_a_rejected_status_report_is_kept_pending_and_announced(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    report = CchAxcessFake().efile_status_file(FELD, "rejected")
    uploaded = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": "acks"},
        headers={"X-File-Name": "2025I_FeldJ_efile_status.csv"},
        content=report,
    )
    assert uploaded.status_code == 201, uploaded.text
    acks = await feld.seed.rows(
        "SELECT status, state, length(submission_last4) AS n FROM engine_acks "
        "WHERE return_id = $1",
        feld.item,
    )
    assert acks and {a["state"] for a in acks} == {"pending"} and {a["n"] for a in acks} == {4}
    announced = await feld.seed.value(
        "SELECT count(*) FROM outbox WHERE event_type = 'engine_ack.rejected' "
        "AND payload ->> 'work_item_id' = $1",
        str(feld.item),
    )
    assert announced == sum(1 for a in acks if a["status"] == "rejected")
