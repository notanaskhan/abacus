"""T-05-T67 part 1 (TASK-8026; T-05 §9 T67; SPEC-651 AC-14.1, F11, F12, F13): the API-level J08
journey on the loaded Brightwater Hale tenant, against the real services with the scenario's
clock. Ridgeline Property Partners, LP's 2025 Form 1065 is loaded through the `entity` slice at
Sep 14, 9:52 AM CT (Run 3 done, the M-2 fix approved at 9:51, the memo stale) and read back
through tax's and review's service APIs, never by re-deriving a figure:

- shoebox to workbook: the QuickBooks trial balance is adopted and Samuel's 28 form-line
  mappings leave nothing unmapped (no `trial_balance_missing` or `unmapped_accounts`);
- the L3 allocation structure is approved (no `allocation_structure_not_approved`);
- TJE-1 reclasses 6,200 to Schedule K line 18a, and after the fix M-2 line 9 reads 6,866,200;
- the tie holds: no tie-out is off unacknowledged; Run 3 (9:52) is in progress, by design;
- reconciliation before any CCH import compares nothing and raises no difference (F11);
- the agents-off variant: the loaded day made zero model calls (usage ledger empty).

Part 2 (recorded in TASK-8026): the declined-consent variant, the K-1 drafts and the CCH import
round trip on this database; the DB clauses T-05-T63 and T65 left here (the consent_7216 refusal
on every model step, the TJE layers' balance, hostile import parsing, the fix flow's checkpoints).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from tests.integration.agent_tests.support import Seeder
from tests.integration.conftest import MigratedDatabase

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.review.api import current_values
from abacus.modules.tax.entity_guards import entity_blockers
from abacus.modules.tax.entity_reconciliation import differences, reconcile
from abacus.modules.tax.workbook_service import WORKBOOK
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
RIDGELINE = "Ridgeline Property Partners, LP"
AT = "2026-09-14T09:52"
GOLDEN = Path(__file__).parents[2] / "golden" / "reference_sets" / "tax_form_lines.json"
_SCHEDULES = ("8825", "M-1", "M-2", "M-3", "K", "L")


def _line(key: str) -> dict[str, object]:
    schedule = next(s for s in _SCHEDULES if key.startswith(s))
    line = key.removeprefix(schedule).strip() or key
    return {"key": key, "schedule": schedule, "line": line[:10], "label": key, "side": "memo"}


async def _publish_line_set(dsn: str) -> None:
    """The reviewed TY2025 Form 1065 line set is CPA-gated content outside git; the journey
    publishes a synthetic set with its public keys (the golden's `mappable_keys`) into its own
    database, two-person, as the C21 tests publish their probes (DEC-5019)."""
    keys = json.loads(GOLDEN.read_text(encoding="utf-8"))["mappable_keys"]
    payload = {"kind": "tax_form_lines", "form": "1065", "tax_year": 2025,
               "rows": [_line(k) for k in keys]}  # fmt: skip
    raw = json.dumps(payload)
    conn = await asyncpg.connect(dsn)
    try:
        version = await conn.fetchval(
            "SELECT reference_set_draft($1, 'tax_form_lines', 'Form 1065 lines (synthetic)', "
            "'US', $2, NULL, 2025, $3, $4::jsonb, $5, '[]'::jsonb, $2, 'j08')",
            "tax_form_lines.1065.ty2025.j08",
            "ayushkbhatia",
            date(2025, 1, 1),
            raw,
            "sha256:" + hashlib.sha256(raw.encode()).hexdigest(),
        )
        await conn.execute("SELECT reference_set_publish($1, 'notanaskhan', 'j08')", version)
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def _loaded(own_db: Database, monkeypatch: pytest.MonkeyPatch) -> tuple[Seeder, uuid.UUID]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    await _publish_line_set(own_db.superuser_dsn)
    await loader.load(own_db.superuser_dsn, AT, slices=("tax_board", "entity"), wait=False)
    seed = Seeder(own_db.superuser_dsn)
    found = cast(
        uuid.UUID | None,
        await seed.value(
            "SELECT t.work_item_id FROM tax_returns t JOIN client_entities c "
            "ON c.id = t.client_entity_id WHERE t.tenant_id = $1 AND c.name = $2 "
            "AND t.form = '1065' AND t.tax_year = 2025",
            TENANT,
            RIDGELINE,
        ),
    )
    assert found is not None, "the entity slice loads Ridgeline's 2025 Form 1065"
    return seed, found


def _amount(values: dict[str, dict[str, object]], key: str) -> Decimal | None:
    cell = values.get(key)
    if cell is None or cell.get("v") is None:
        return None
    try:
        return Decimal(str(cell["v"]))
    except InvalidOperation:  # a label or a formula text cell
        return None


async def test_j08_the_return_reaches_final_approval_without_a_blocker(
    own_db: Database,
    migrated_db: MigratedDatabase,
    object_store: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del migrated_db, object_store
    seed, return_id = await _loaded(own_db, monkeypatch)
    tenant = TenantContext(TENANT, "system", "t05t67")
    kinds = [b.kind for b in await entity_blockers(tenant, return_id)]
    assert "trial_balance_missing" not in kinds
    assert "unmapped_accounts" not in kinds  # shoebox to workbook: every account mapped
    assert "allocation_structure_not_approved" not in kinds  # the L3 allocation
    assert "tie_out_off_unacknowledged" not in kinds  # the fix closed M-2's off 6,200
    # Run 3 starts at 9:52 (TXP-00 b, "7 of 10"): final approval waits for it, by design.
    assert "workbook_run_in_progress" in kinds

    values = await current_values(tenant, WORKBOOK, return_id)
    line_9 = [
        v
        for k, v in values.items()
        if k.startswith("07!") and _amount(values, k) == Decimal("6866200")
    ]
    assert line_9, "M-2 line 9 reads 6,866,200 after the 9:51 fix"
    assert any(k.startswith("06!") and _amount(values, k) == Decimal("6200") for k in values), (
        "TJE-1's 6,200 sits on Schedule K line 18a"
    )

    # F11: before any approved CCH import, reconciliation compares nothing and raises nothing.
    assert differences(await reconcile(tenant, return_id)) == []

    # Agents-off variant (F13): the loaded day made no model call at all.
    calls = await seed.value("SELECT count(*) FROM usage_records WHERE tenant_id = $1", TENANT)
    assert calls == 0
