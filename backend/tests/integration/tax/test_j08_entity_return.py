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

Part 2 (TASK-8074, DEC-5060), on the same loaded day, after part 1's reads:

- K-1 drafts: none yet at 9:52 (Run 3, in progress, writes them);
- T-05-T63's DB clause: the TJE layers balance (every TJE nets to zero, so TTB foots like ATB);
- T-05-T65's DB clauses: the M-2 fix left the workbook a checkpoint trail, and a hostile import
  file is refused with its problems, never parsed into cells;
- the declined-consent variant (T-05-T63): with Ridgeline's §7216 consent revoked, every model
  step of a full run plan waits on `consent_7216` and every code step still computes.

The CCH round trip (export, import, a 1-dollar `engine_diagnostic`) waits on T-05-T60's
unvalidated CCH Axcess entity layout (T-05 OQ-1, human).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

import pytest
from tests.integration.agent_tests.support import Seeder
from tests.integration.conftest import MigratedDatabase

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.adjustments.api import adjusted_tb
from abacus.modules.agents.api import PlanRequest
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import current_values, list_checkpoints
from abacus.modules.tax.entity_guards import entity_blockers
from abacus.modules.tax.entity_reconciliation import differences, reconcile
from abacus.modules.tax.entity_run_plan import consent_in_force, entity_workbook_plan, selected
from abacus.modules.tax.workbook_imports import ImportInvalid, parse
from abacus.modules.tax.workbook_service import WORKBOOK
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS

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
    owner = Seeder(dsn)  # the tests' one connection helper (DB-001)
    version = await owner.value(
        "SELECT reference_set_draft($1, 'tax_form_lines', 'Form 1065 lines (synthetic)', "
        "'US', $2, NULL, 2025, $3, $4::jsonb, $5, '[]'::jsonb, $2, 'j08')",
        "tax_form_lines.1065.ty2025.j08",
        "ayushkbhatia",
        date(2025, 1, 1),
        raw,
        "sha256:" + hashlib.sha256(raw.encode()).hexdigest(),
    )
    await owner.value("SELECT reference_set_publish($1, 'notanaskhan', 'j08')", version)


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

    # --- part 2 (TASK-8074) ----------------------------------------------------------------
    samuel = loader.user_id_of(next(x for x in SEATS if x.initials == "SI"))
    person = AuthContext(
        TenantContext(TENANT, "human", str(samuel)), samuel, uuid.UUID(int=0), None, system_now()
    )

    # K-1 drafts are Run 3's `federal_k1s` output; at 9:52 Run 3 is still in progress (by design),
    # so none exist yet and the release (J08 step 16) is TXP-12's journey (DEC-5060).
    drafts = await seed.value(
        "SELECT count(*) FROM k1_packages WHERE tenant_id = $1 AND work_item_id = $2",
        TENANT,
        return_id,
    )
    assert drafts == 0

    # T-05-T63: the TJE layers balance; TTB foots to zero as ATB does.
    layers = cast(Any, await adjusted_tb(person, return_id, "ttb"))  # Any: the layers view
    assert sum((ln.tje or Decimal(0) for ln in layers.lines), Decimal(0)) == 0
    assert sum((ln.ttb for ln in layers.lines), Decimal(0)) == sum(
        (ln.atb for ln in layers.lines), Decimal(0)
    )

    # T-05-T65 (T50): the 9:51 fix left the workbook a checkpoint trail, one current.
    trail = await list_checkpoints(person, WORKBOOK, return_id, "all")
    assert trail.items and trail.current_checkpoint_id is not None

    # T-05-T65 (T40): a hostile import file is refused with its problems, never read into cells.
    for hostile in (b"", b"=cmd|' /C calc'!A0\n" * 3, b"\x00" * 64):
        with pytest.raises(ImportInvalid):
            parse("depreciation_register", hostile)

    # The declined-consent variant (T-05-T63): no §7216 consent in force, so every model step of
    # a full plan waits on `consent_7216` while every code step still computes.
    await seed.run(
        "UPDATE consents SET status = 'revoked', revoked_at = now() WHERE tenant_id = $1 "
        "AND status = 'signed' AND client_entity_id = (SELECT client_entity_id FROM tax_returns "
        "WHERE work_item_id = $2)",
        TENANT,
        return_id,
    )
    assert not await consent_in_force(tenant, return_id)
    engagement = cast(
        uuid.UUID,
        await seed.value(
            "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", return_id
        ),
    )
    plan = await entity_workbook_plan(tenant, engagement, PlanRequest(return_id, "all"))
    model = {s.key for s in selected("all", ()) if s.model}
    assert model, "the full plan has model steps"
    for step in plan:
        if step.key in model:
            assert step.kind == "question" and step.arguments["question_key"] == "consent_7216"
        elif step.key != "convention_706d":
            assert step.kind == "compute", step.key
