"""T-04-T25 (TASK-6723; T-04 §6; SPEC-649 AC-9.3, AC-11.1): the return drafter through its start
service and its draft activity, on the Feld return.

Row acceptance (part held here): "a missing consent leaves the run waiting_on_inputs", with no
model call and nothing proposed. The Feld draft's proposal, cited fields and box 18A issue need
the extracted boxes and their page words seeded (P-11's word layer): the code rules are held by
`tests/unit/tax/test_t04t25_drafter_rules.py`, and the full Feld draft by T-04-T35's labelled
cases and P-10-T49's journey (flagged in TASK-6723).
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.modules.tax import drafter_run, drafter_workflow
from abacus.modules.tax.api import start_draft
from abacus.modules.tax.drafter_workflow import DraftInput, draft_activity

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import engines, feld_return  # noqa: F401 -- fixtures

pytestmark = pytest.mark.asyncio


async def test_ac_a_missing_consent_leaves_the_run_waiting_on_inputs_with_no_model_call(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld = await feld_return(migrated_db)
    dispatched: list[object] = []

    async def capture(workflow: object, arg: object, *, id: str) -> None:  # noqa: A002
        dispatched.append(arg)

    async def no_model(*_: object, **__: object) -> object:
        raise AssertionError("a model was called without both §7216 consents")

    monkeypatch.setattr(drafter_workflow, "dispatch", capture)
    monkeypatch.setattr(drafter_run, "call", no_model)
    run_id = await start_draft(feld.samuel, feld.item)
    (started,) = dispatched
    p = cast(DraftInput, started)
    assert (p.run_id, p.tax_year) == (str(run_id), 2025)
    row = await feld.seed.rows(
        "SELECT agent_id, state, run_number, runs_as_user_id FROM agent_runs WHERE id = $1", run_id
    )
    assert (row[0]["agent_id"], row[0]["state"]) == ("tax.return_drafter", "queued")
    assert row[0]["run_number"] is not None
    outcome = await draft_activity(p)
    assert (outcome.outcome, outcome.needs) == ("waiting_on_inputs", ["consent_7216"])
    proposals = await feld.seed.value(
        "SELECT count(*) FROM proposals WHERE agent_run_id = $1", run_id
    )
    assert proposals == 0


async def test_a_person_who_may_not_start_runs_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    from abacus.modules.identity.api import Forbidden

    stranger = feld.samuel.__class__(
        feld.samuel.tenant.__class__(feld.tenant, "agent", str(uuid.uuid4())),
        feld.samuel.user_id,
        feld.samuel.membership_id,
        None,
        feld.samuel.mfa_at,
    )
    with pytest.raises(Forbidden):
        await start_draft(stranger, feld.item)
