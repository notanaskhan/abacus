# ac-test-author: ayushkbhatia
"""T-01-T03 (TASK-2110; SPEC-501 AC-9): the engine bridge and e-file record as T-02 and TAX-09/12
read them. Written against the stub; holds as the routes go live.

- Figures, diffs, payments and engine messages are TRI; a submission id shows its last four only.
- The sync chip's states are the status registry's.
- No agent may export, approve an import or record a transmission, whatever its task scope."""

from __future__ import annotations

from typing import get_args

from abacus.kernel._statuses import EfileAckStatus, EngineSyncStatus
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.tax import engine_contract as engine


def test_ac9_figures_payments_and_messages_are_tri() -> None:
    for model, field in (
        (engine.ImportDiffRowOut, "accrued"),
        (engine.ImportDiffRowOut, "engine"),
        (engine.EngineDiagnosticOut, "message_text"),
        (engine.PaymentInstructionOut, "amount"),
        (engine.EfileAckOut, "reject_text"),
    ):
        assert model.model_json_schema()["properties"][field].get("x-tri") is True, (model, field)


def test_ac9_a_submission_id_is_its_last_four_only() -> None:
    fields = set(engine.EfileAckOut.model_fields)
    assert "submission_id_last4" in fields and "submission_id" not in fields


def test_ac9_sync_chip_and_ack_codes_are_the_registrys() -> None:
    assert set(get_args(engine.SyncState)) == {s.value for s in EngineSyncStatus}
    assert {"accepted", "rejected"} == {s.value for s in EfileAckStatus}


def test_ac9_no_agent_holds_export_import_approval_or_transmission() -> None:
    for action in ("tax_return.export", "engine_import.approve", "transmission.record"):
        assert RULES[action].decisions.get("agent", "deny") == "deny", action
        assert RULES[action].decisions.get("system", "deny") == "deny", action
