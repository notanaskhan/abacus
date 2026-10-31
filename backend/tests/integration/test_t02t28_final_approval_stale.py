# ac-test-author: ayushkbhatia
"""T-02-T28 (ADR-078; TASK-2532; T-01 §3.8; T-02 §3.3): the TAX-02 approve control goes stale
after a new import, written from the contract (`docs/contracts/tax-engine-bridge.md`) rather than
the code. A new engine import awaiting a person blocks final approval with its reason; once it is
approved the return's checkpoint moves, and an approval naming the earlier checkpoint and hash is
refused (409 `content_changed`) with nothing written.

The Feld 1040 and its first approved import are T-01-T25's harness.
"""

from __future__ import annotations

from typing import cast

import pytest

from abacus.modules.tax import approval

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import ACCEPTED, HEAD, engines, feld_return, switched_on

__all__ = ["engines", "switched_on"]

V4 = (
    HEAD
    + "2025I:FeldJ,V4,co_dr0104pn.co_source_income,DR 0104PN,34,97010\n"
    + "2025I:FeldJ,V4,f1040.direct_deposit_last4,1040,35b,6620\n"
    + "2025I:FeldJ,V4,f1040es_2026.voucher_amount,1040-ES,Q1-Q4,19990\n"
    + "2025I:FeldJ,V4,f8879.signature_method,8879,Part II,practitioner_pin\n"
    + "2025I:FeldJ,V4,il1040_schnr.il_source_income,IL-1040 Sch NR,47,141634\n"
).encode()


async def test_a_new_import_blocks_then_stales_the_approve_control(
    migrated_db: MigratedDatabase, switched_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld = await feld_return(migrated_db)

    async def named(_tenant: object, _client: object) -> object:
        return feld.samuel.user_id

    monkeypatch.setattr(approval, "signer_for", named)
    seen = await approval.eligibility(feld.samuel, feld.item)
    uploaded = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": "values"},
        headers={"X-File-Name": "2025I_FeldJ_V4.csv", "Content-Type": "text/csv"},
        content=V4,
    )
    assert uploaded.status_code == 201, uploaded.text
    pending = await approval.eligibility(feld.samuel, feld.item)
    assert "import_pending_approval" in [b.kind for b in pending.blockers]
    approved = await feld.call(
        "POST",
        f"/v1/engine-imports/{cast(dict[str, object], uploaded.json())['id']}/approve",
        json={"accepted_field_keys": ACCEPTED, "seen_version": 1},
    )
    assert approved.status_code == 200, approved.text
    now_seen = await approval.eligibility(feld.samuel, feld.item)
    assert (now_seen.checkpoint_id, now_seen.content_hash) != (
        seen.checkpoint_id,
        seen.content_hash,
    )
    assert seen.checkpoint_id is not None and seen.content_hash is not None
    with pytest.raises(approval.ContentChanged):  # the control as it was drawn before the import
        await approval.approve(feld.samuel, feld.item, seen.checkpoint_id, seen.content_hash)
    signed = await feld.seed.value(
        "SELECT count(*) FROM sign_offs WHERE target_id = $1 AND level = 4", feld.item
    )
    assert signed == 0
