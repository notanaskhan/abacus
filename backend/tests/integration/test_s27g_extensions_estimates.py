"""S27 gap, T-03-T07 (TASK-3350; DEC-2350) over HTTP against Postgres.

The row's acceptance: a person's click approves payments, a walled return is absent from what they
see, and no route stores a payment instrument. The firm-level gate refused every reviewer before
this, so the approval and the refusal both run through the real authorisation.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from openpyxl import load_workbook

from abacus.kernel.clock import frozen
from abacus.modules.tax import estimates, extensions

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- the sibling suite's helper

pytestmark = pytest.mark.usefixtures("flag_on", "rules")


@dataclass(frozen=True)
class _Dates:
    original_due_on: date = date(2028, 4, 18)
    extended_due_on: date | None = date(2028, 10, 16)
    extension_form: str | None = "4868"
    reference_set_version_ids: tuple[uuid.UUID, ...] = ()
    rule_text: str | None = None
    extended_rule_text: str | None = None


@pytest.fixture
async def flag_on(board: Board) -> None:
    await board.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.extensions_estimates', 'true', 's27g', 'S27 gap')",
        board.tenant,
    )


@pytest.fixture
def rules(monkeypatch: pytest.MonkeyPatch) -> None:
    async def dates_for(*_args: object) -> _Dates:
        return _Dates()

    async def met(*_args: object) -> list[str]:
        return []

    monkeypatch.setattr(extensions, "dates_for", dates_for)
    monkeypatch.setattr(extensions, "_unmet_gates", met)


_FUNCTION = {"manager": "manager_reviewer", "staff": "preparer"}


async def _member(b: Board, return_id: uuid.UUID, ctx_user: uuid.UUID, role: str) -> uuid.UUID:
    engagement = cast(
        uuid.UUID,
        await b.seed.value("SELECT engagement_id FROM work_items WHERE id = $1", return_id),
    )
    await b.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        b.tenant,
        engagement,
        ctx_user,
        role,
    )
    await b.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, $5, $6)",
        b.tenant,
        return_id,
        engagement,
        ctx_user,
        _FUNCTION[role],
        b.partner,
    )
    return engagement


def _feld(b: Board) -> uuid.UUID:
    return b.returns["Feld Household 1040"]


def _body(return_id: uuid.UUID, amount: str = "10000.00") -> Json:
    return {
        "return_ids": [str(return_id)],
        "payments": [
            {"return_id": str(return_id), "jurisdiction": "US", "amount": amount},
        ],
    }


async def test_ac_prepare_refuses_an_unmet_gate_and_writes_nothing(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unmet(*_args: object) -> list[str]:
        return ["G1", "G3"]

    monkeypatch.setattr(extensions, "_unmet_gates", unmet)
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    with frozen(DEMO):
        out = await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert out.status_code == 409, out.text
    assert out.json()["detail"] == "gate_unmet"
    assert out.json()["facts"]["gate"] == "G1"
    assert (
        await board.seed.value(
            "SELECT count(*) FROM filing_extensions WHERE tenant_id = $1", board.tenant
        )
        == 0
    )


async def test_ac_prepare_proposes_and_a_repeat_writes_nothing_more(board: Board) -> None:
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    call = _as(samuel)
    with frozen(DEMO):
        first = await call(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        again = await call(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        changed = await call(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld, "12000.00"),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert changed.status_code == 200, changed.text
    line = cast(list[Json], first.json()["extensions"])[0]
    assert line["return_form"] == "1040"
    row = (
        await board.seed.rows(
            "SELECT status, form FROM filing_extensions WHERE tenant_id = $1", board.tenant
        )
    )[0]
    assert row is not None
    assert (row["status"], row["form"]) == ("prepared", "4868")
    # Two rows, not three: the repeat wrote nothing and the change superseded the first.
    assert (
        await board.seed.value(
            "SELECT count(*) FROM extension_payments WHERE tenant_id = $1", board.tenant
        )
        == 2
    )
    assert (
        await board.seed.value(
            "SELECT count(*) FROM extension_payments WHERE supersedes_id IS NOT NULL "
            "AND tenant_id = $1",
            board.tenant,
        )
        == 1
    )


async def test_ac_a_manager_approves_on_the_return_and_staff_are_refused(board: Board) -> None:
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    kevin = await board.person("Kevin Osei", None)
    await _member(board, feld, kevin.user_id, "staff")
    with frozen(DEMO):
        prepared = await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert prepared.status_code == 200, prepared.text
        extension = cast(
            uuid.UUID,
            await board.seed.value(
                "SELECT id FROM filing_extensions WHERE tenant_id = $1 LIMIT 1", board.tenant
            ),
        )
        body = {"extension_ids": [str(extension)], "send_confirmations": False}
        refused = await _as(kevin)(
            "POST",
            "/v1/tax/extensions:approve-and-request",
            json=body,
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        approved = await _as(samuel)(
            "POST",
            "/v1/tax/extensions:approve-and-request",
            json=body,
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert refused.status_code == 403, refused.text
    assert approved.status_code == 200, approved.text
    row = (
        await board.seed.rows(
            "SELECT approved_by, approved_actor_kind FROM extension_payments WHERE tenant_id = $1",
            board.tenant,
        )
    )[0]
    assert row is not None
    assert (row["approved_by"], row["approved_actor_kind"]) == (samuel.user_id, "human")


async def test_ac_a_walled_return_is_absent_for_the_viewer(board: Board) -> None:
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    with frozen(DEMO):
        await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        outsider = await board.person("Walled Partner", None)
        await board.seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "VALUES ($1, $2, $3, $4)",
            board.tenant,
            outsider.user_id,
            board.clients["Feld Household"],
            board.partner,
        )
        listed = await _as(outsider)("GET", "/v1/tax/extensions", params={"tax_year": 2025})
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    assert listed.json()["counts"]["extended"] == 0


async def test_ac_the_liability_needs_its_source_and_code_stores_the_target(board: Board) -> None:
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    await board.seed.run("UPDATE tax_returns SET tax_year = 2027 WHERE work_item_id = $1", feld)
    with frozen(DEMO):
        await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        row = (
            await board.seed.rows(
                "SELECT id, row_version FROM filing_extensions WHERE tenant_id = $1", board.tenant
            )
        )[0]
        assert row is not None
        path = f"/v1/tax/extensions/{row['id']}"
        headers = {"If-Match": str(row["row_version"])}
        bare = await _as(samuel)(
            "PATCH", path, json={"projected_liability": "122500.00"}, headers=headers
        )
        entered = await _as(samuel)(
            "PATCH",
            path,
            json={
                "projected_liability": "122500.00",
                "projected_liability_source": "preparer_entry",
                "projected_liability_ref": {"worksheet": "WS-1"},
            },
            headers=headers,
        )
    assert bare.status_code == 422, bare.text
    assert entered.status_code == 200, entered.text
    assert Decimal(cast(str, entered.json()["safe_harbor_target"])) == Decimal("110250.00")


async def test_ac_estimates_compute_in_code_and_paid_needs_evidence(board: Board) -> None:
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    entity = cast(
        uuid.UUID,
        await board.seed.value(
            "SELECT client_entity_id FROM tax_returns WHERE work_item_id = $1", feld
        ),
    )
    dates = [(q, date(2028, q * 3, 15), None) for q in (1, 2, 3, 4)]
    with frozen(DEMO):
        schedule = await estimates.create_schedule(
            samuel,
            client_entity_id=entity,
            basis_tax_return_id=feld,
            tax_year=2027,
            jurisdiction="US",
            form="1040-ES",
            method="prior_year_110",
            due_dates=dates,
        )
        call = _as(samuel)
        patched = await call(
            "PATCH",
            f"/v1/tax/estimates/{schedule}",
            json={
                "prior_year_tax": "123223.00",
                "prior_year_tax_source": "preparer_entry",
                "projected_withholding": "55585.00",
                "prior_agi_over_threshold": True,
            },
            headers={"If-Match": "1"},
        )
        assert patched.status_code == 200, patched.text
        assert Decimal(cast(str, patched.json()["annual_required"])) == Decimal("79960")
        assert patched.json()["stamp"] is not None
        installment = cast(list[Json], patched.json()["installments"])[0]
        assert Decimal(cast(str, installment["amount"])) == Decimal("19990")
        version = str(installment["row_version"])
        unbacked = await call(
            "PATCH",
            f"/v1/tax/estimates/{schedule}/installments/1",
            json={"paid_on": "2028-03-10"},
            headers={"If-Match": version},
        )
        evidence = uuid.uuid4()
        paid = await call(
            "PATCH",
            f"/v1/tax/estimates/{schedule}/installments/1",
            json={"paid_on": "2028-03-10", "evidence_version_id": str(evidence)},
            headers={"If-Match": version},
        )
        listed = await call("GET", "/v1/tax/estimates", params={"tax_year": 2027, "quarter": 1})
        union = await call("GET", "/v1/tax/payments", params={"tax_year": 2027})
    assert unbacked.status_code == 422, unbacked.text
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert listed.json()["counts"]["paid"] == 1
    assert [r["source_kind"] for r in cast(list[Json], union.json()["items"])] == [
        "estimate_installment"
    ]


async def test_ac_the_export_is_text_for_a_client_string_and_audited_by_count(
    board: Board,
) -> None:
    feld = _feld(board)
    samuel = await board.person("Margaret Osei", None)
    await _member(board, feld, samuel.user_id, "manager")
    await board.seed.run(
        "UPDATE clients SET name = '=HYPERLINK(1)' WHERE id = "
        "(SELECT client_id FROM work_items WHERE id = $1)",
        feld,
    )
    with frozen(DEMO):
        await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        out = await _as(samuel)("GET", "/v1/tax/extensions/export.xlsx", params={"tax_year": 2025})
    assert out.status_code == 200, out.text
    sheet = load_workbook(io.BytesIO(out.content)).active
    assert sheet is not None
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0][0] == "Client"
    cell = sheet.cell(row=2, column=1)
    assert cell.data_type == "s"
    assert (
        await board.seed.value(
            "SELECT count(*) FROM audit_events WHERE action = 'tax_schedule.extensions_exported' "
            "AND tenant_id = $1",
            board.tenant,
        )
        == 1
    )


async def test_ac_one_click_approves_and_sends_the_confirmation(board: Board) -> None:
    """The row's acceptance, for one return: a single click, attributed to the person."""
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    with frozen(DEMO):
        out = await _as(samuel)(
            "POST",
            "/v1/tax/extensions:approve-and-request",
            json={**_body(feld), "send_confirmations": True},
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert out.status_code == 200, out.text
    body = out.json()
    assert len(body["approved_payment_ids"]) == 1
    assert len(body["confirmation_request_item_ids"]) == 1
    item = uuid.UUID(body["confirmation_request_item_ids"][0])
    row = (
        await board.seed.rows(
            "SELECT created_by, sent_at, client_visible, due_on FROM request_items WHERE id = $1",
            item,
        )
    )[0]
    assert row["created_by"] == samuel.user_id
    assert row["sent_at"] is not None
    assert row["client_visible"] is True
    linked = await board.seed.value(
        "SELECT confirmation_request_item_id FROM filing_extensions WHERE tax_return_id = $1", feld
    )
    assert linked == item


async def test_ac_a_preparer_submits_and_cannot_approve(board: Board) -> None:
    feld = _feld(board)
    kevin = await board.person("Kevin Osei", None)
    await _member(board, feld, kevin.user_id, "staff")
    with frozen(DEMO):
        await _as(kevin)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        extension = await board.seed.value(
            "SELECT id FROM filing_extensions WHERE tenant_id = $1 LIMIT 1", board.tenant
        )
        out = await _as(kevin)(
            "POST",
            "/v1/tax/extensions:submit-for-approval",
            json={"extension_ids": [str(extension)]},
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert out.status_code == 200, out.text
    assert (
        await board.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'filing_extension.submitted_for_approval'",
            board.tenant,
        )
        == 1
    )
    assert (
        await board.seed.value(
            "SELECT count(*) FROM extension_payments WHERE tenant_id = $1 "
            "AND approved_by IS NOT NULL",
            board.tenant,
        )
        == 0
    )


async def test_ac_a_rule_raises_its_issue_once(board: Board) -> None:
    from abacus.kernel.db import TenantContext
    from abacus.modules.review.api import record_rule_issue

    feld = _feld(board)
    engagement = cast(
        uuid.UUID,
        await board.seed.value("SELECT engagement_id FROM work_items WHERE id = $1", feld),
    )
    tenant = TenantContext(board.tenant, "system", "answer_effects")

    async def raise_it() -> uuid.UUID:
        return await record_rule_issue(
            tenant,
            engagement_id=engagement,
            work_item_id=feld,
            record_type="tax_return",
            record_id=feld,
            kind="review_point",
            priority="medium",
            title="Confirm full-year NYC residency",
            source_ref="answer_effect:q2:residency",
        )

    with frozen(DEMO):
        first = await raise_it()
        again = await raise_it()
    assert first == again
    assert (
        await board.seed.value(
            "SELECT count(*) FROM issues WHERE work_item_id = $1 AND kind = 'review_point'", feld
        )
        == 1
    )


async def test_ac_an_offshore_reader_sees_no_client_without_consent(board: Board) -> None:
    """Amounts are tax return information (DEC-52): fail closed with no consent on file."""
    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    offshore = await board.person("Offshore Reader", None)
    await board.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        board.tenant,
        offshore.user_id,
    )
    with frozen(DEMO):
        await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        listed = await _as(offshore)("GET", "/v1/tax/extensions", params={"tax_year": 2025})
        mine = await _as(samuel)("GET", "/v1/tax/extensions", params={"tax_year": 2025})
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    assert len(mine.json()["items"]) == 1


async def _audited(board: Board, action: str) -> int:
    return cast(
        int,
        await board.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = $2",
            board.tenant,
            action,
        ),
    )


async def test_ac_the_due_soon_sweep_commits_through_a_real_unit_of_work(board: Board) -> None:
    """A unit of work that only emits raises MissingAuditEvent: stubs cannot show this."""
    from abacus.kernel.db import TenantContext

    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    entity = cast(
        uuid.UUID,
        await board.seed.value(
            "SELECT client_entity_id FROM tax_returns WHERE work_item_id = $1", feld
        ),
    )
    dates = [(q, date(2028, q * 3, 15), None) for q in (1, 2, 3, 4)]
    with frozen(DEMO):
        await estimates.create_schedule(
            samuel,
            client_entity_id=entity,
            basis_tax_return_id=feld,
            tax_year=2027,
            jurisdiction="US",
            form="1040-ES",
            method="prior_year_110",
            due_dates=dates,
        )
    with frozen(datetime(2028, 3, 14, 12, tzinfo=UTC)):
        sent = await estimates.send_due_soon(
            TenantContext(board.tenant, "system", "tax:estimates")
        )
    assert sent == 1
    assert await _audited(board, "estimate_installment.due_soon_notified") == 1


async def test_ac_the_date_sweep_runs_on_a_prepared_line(board: Board) -> None:
    from abacus.kernel.db import TenantContext

    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    await _member(board, feld, samuel.user_id, "manager")
    with frozen(DEMO):
        out = await _as(samuel)(
            "POST",
            "/v1/tax/extensions:prepare",
            json=_body(feld),
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert out.status_code == 200, out.text
        changed = await extensions.recompute_open_lines(
            TenantContext(board.tenant, "system", "tax:extensions")
        )
    assert changed == 0  # the rules have not moved


async def test_ac_a_rejected_ack_notifies_through_a_real_unit_of_work(board: Board) -> None:
    from abacus.kernel.uow.relay import OutboxEvent

    feld = _feld(board)
    samuel = await board.person("Samuel Ito", None)
    engagement = await _member(board, feld, samuel.user_id, "manager")
    extension = uuid.uuid4()
    await extensions.on_filing_acknowledged(
        OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=board.tenant,
            event_type="filing.acknowledged",
            payload={
                "extension_id": str(extension),
                "return_id": str(feld),
                "engagement_id": str(engagement),
                "status": "rejected",
                "reject_code": "R0000-500",
            },
        )
    )
    assert await _audited(board, "filing_extension.ack_rejection_notified") == 1


def test_ac_an_answer_effects_rule_key_is_a_ref_the_audit_accepts() -> None:
    """A rule key is text: `Ref` refuses it, which raised whenever a rule fired."""
    from abacus.kernel.uow import Ref
    from abacus.modules.requests.answer_effect_slots import rule_fingerprint

    assert Ref(rule=rule_fingerprint("q2_residency"), pending=0).fields["pending"] == 0
