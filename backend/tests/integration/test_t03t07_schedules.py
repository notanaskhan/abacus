"""T-03-T07 (TASK-3336; DEC-2327): prepare, submit, estimates, the payments union and exports.

Row acceptance: "no route transmits or stores a payment instrument", the figures are code's and
TAX-13 b's Feld row foots: 110% x 123,223 = 135,545, less 55,585 = 79,960, so 19,990 a quarter.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import date
from typing import cast

import pytest
from openpyxl import load_workbook

from abacus.kernel.clock import frozen
from abacus.modules.engagements.gates import GateFact
from abacus.modules.tax import estimates, extensions

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

X = "/v1/tax/extensions"
E = "/v1/tax/estimates"
KEY = {"Idempotency-Key": "t07"}
YEAR = 2027


@dataclass(frozen=True)
class _Dates:
    original_due_on: date = date(2028, 4, 18)
    extended_due_on: date | None = date(2028, 10, 16)
    reference_set_version_ids: tuple[uuid.UUID, ...] = ()


async def _dates(*_a: object) -> _Dates:
    return _Dates()


async def _quarters(*_a: object) -> dict[int, date]:
    return {
        1: date(YEAR, 4, 15),
        2: date(YEAR, 6, 15),
        3: date(YEAR, 9, 15),
        4: date(YEAR + 1, 1, 18),
    }


async def _met(*_a: object) -> GateFact:
    return GateFact(met=True)


async def _setup(b: Board) -> tuple[uuid.UUID, uuid.UUID]:
    await b.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.extensions_estimates', 'true', 't03-t07', 'T-03-T07')",
        b.tenant,
    )
    feld = b.returns["Feld Household 1040"]
    await b.seed.run("UPDATE tax_returns SET tax_year = $1 WHERE work_item_id = $2", YEAR, feld)
    engagement = cast(
        uuid.UUID,
        await b.seed.value("SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", feld),
    )
    return feld, engagement


async def _member(
    b: Board, name: str, engagement: uuid.UUID, role: str, function: str = "first_level_reviewer"
) -> object:
    person = await b.person(name, None)
    await b.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, $5, $4)",
        b.tenant,
        b.returns["Feld Household 1040"],
        engagement,
        person.user_id,
        function,
    )
    await b.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        b.tenant,
        engagement,
        person.user_id,
        role,
    )
    return person


async def test_prepare_is_held_by_the_engagement_gates(board: Board) -> None:
    feld, engagement = await _setup(board)
    with frozen(DEMO):
        person = await _member(board, "Samuel Ito", engagement, "manager")
        refused = await _as(person)(
            "POST", f"{X}:prepare", json={"return_ids": [str(feld)]}, headers=KEY
        )
    assert (refused.status_code, refused.json()["detail"]) == (409, "gate_unmet"), refused.text


async def test_prepare_stamps_the_target_and_a_new_payment_supersedes(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld, engagement = await _setup(board)
    monkeypatch.setattr(extensions, "dates_for", _dates)
    monkeypatch.setattr(extensions, "gate_fact", _met)
    with frozen(DEMO):
        person = await _member(board, "Samuel Ito", engagement, "manager")
        call = _as(person)
        body: Json = {
            "return_ids": [str(feld)],
            "lines": [
                {
                    "return_id": str(feld),
                    "projected_liability": "100000.00",
                    "projected_liability_source": "preparer_entry",
                    "withholding_plus_estimates": "80000.00",
                }
            ],
            "payments": [{"return_id": str(feld), "jurisdiction": "US", "amount": "5000.00"}],
        }
        made = await call("POST", f"{X}:prepare", json=body, headers=KEY)
        assert made.status_code == 200, made.text
        (check,) = cast(list[Json], made.json()["checks"])
        assert check["projected_liability"] == "100000.00"
        assert check["safe_harbor_target"] == "90000.00"
        assert check["paid_by_original_due"] == "85000.00"
        assert check["meets_safe_harbor"] is False
        assert check["stamp"] is not None
        (row,) = cast(list[Json], made.json()["extensions"])
        assert cast(list[Json], row["lines"])[0]["status"] == "prepared"
        assert cast(list[Json], row["lines"])[0]["form"] == "4868"

        body["payments"] = [{"return_id": str(feld), "jurisdiction": "US", "amount": "10000.00"}]
        again = await call("POST", f"{X}:prepare", json=body, headers=KEY)
        assert again.status_code == 200, again.text
        (row,) = cast(list[Json], again.json()["extensions"])
        assert [p["amount"] for p in cast(list[Json], row["payments"])] == ["10000.00"]


async def test_a_state_line_names_its_form_and_no_body_takes_an_instrument(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld, engagement = await _setup(board)
    monkeypatch.setattr(extensions, "dates_for", _dates)
    monkeypatch.setattr(extensions, "gate_fact", _met)
    with frozen(DEMO):
        call = _as(await _member(board, "Samuel Ito", engagement, "manager"))
        no_form = await call(
            "POST",
            f"{X}:prepare",
            json={
                "return_ids": [str(feld)],
                "lines": [{"return_id": str(feld), "jurisdiction": "NY"}],
            },
            headers=KEY,
        )
        assert (no_form.status_code, no_form.json()["detail"]) == (422, "extension_form_required")
        card = await call(
            "POST",
            f"{X}:prepare",
            json={
                "return_ids": [str(feld)],
                "payments": [
                    {
                        "return_id": str(feld),
                        "jurisdiction": "US",
                        "amount": "1.00",
                        "bank_account": "000123456789",
                    }
                ],
            },
            headers=KEY,
        )
    assert card.status_code == 422, card.text


async def test_a_person_without_the_reviewer_function_cannot_approve(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld, engagement = await _setup(board)
    monkeypatch.setattr(extensions, "dates_for", _dates)
    monkeypatch.setattr(extensions, "gate_fact", _met)
    with frozen(DEMO):
        manager = await _member(board, "Samuel Ito", engagement, "manager")
        staff = await _member(board, "Kevin Osei", engagement, "staff", "preparer")
        made = await _as(manager)(
            "POST",
            f"{X}:prepare",
            json={
                "return_ids": [str(feld)],
                "payments": [{"return_id": str(feld), "jurisdiction": "US", "amount": "500.00"}],
            },
            headers=KEY,
        )
        assert made.status_code == 200, made.text
        extension = cast(list[Json], cast(list[Json], made.json()["extensions"])[0]["lines"])[0][
            "extension_id"
        ]
        refused = await _as(staff)(
            "POST",
            f"{X}:approve-and-request",
            json={"extension_ids": [extension], "send_confirmations": False},
            headers=KEY,
        )
        assert refused.status_code == 403, refused.text
        submitted = await _as(staff)(
            "POST", f"{X}:submit-for-approval", json={"extension_ids": [extension]}, headers=KEY
        )
        assert submitted.status_code == 200, submitted.text
        assert (
            await board.seed.value(
                "SELECT submitted_by FROM filing_extensions WHERE id = $1",
                uuid.UUID(cast(str, extension)),
            )
            == cast(object, staff).user_id  # type: ignore[attr-defined]
        )


async def test_feld_foots_and_a_prospect_has_no_binder_to_ask_in(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld, engagement = await _setup(board)
    monkeypatch.setattr(estimates, "installments_due", _quarters)
    entity = await board.seed.value(
        "SELECT e.id FROM client_entities e JOIN engagements g ON g.client_id = e.client_id "
        "WHERE g.id = $1 LIMIT 1",
        engagement,
    )
    if entity is None:
        client = await board.seed.value(
            "SELECT client_id FROM engagements WHERE id = $1", engagement
        )
        entity = await board.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, '=Feld Household') RETURNING id",
            board.tenant,
            client,
        )
    with frozen(DEMO):
        call = _as(await _member(board, "Samuel Ito", engagement, "manager"))
        made = await call(
            "POST",
            E,
            headers=KEY,
            json={
                "client_entity_id": str(entity),
                "basis_tax_return_id": str(feld),
                "tax_year": YEAR,
                "form": "1040-ES",
                "method": "prior_year_110",
                "prior_year_tax": "123223.00",
                "prior_agi_over_threshold": True,
                "projected_withholding": "55585.00",
                "payment_method_label": "irs_direct_pay",
            },
        )
        assert made.status_code == 201, made.text
        body = cast(Json, made.json())
        assert body["annual_required"] == "79960.00"
        quarters = cast(list[Json], body["installments"])
        assert [q["amount"] for q in quarters] == ["19990.00"] * 4
        schedule = body["schedule_id"]

        moved = await call(
            "PATCH",
            f"{E}/{schedule}",
            json={"method": "prior_year_100"},
            headers={"If-Match": str(body["row_version"])},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["annual_required"] == "67638.00"
        stale = await call(
            "PATCH",
            f"{E}/{schedule}",
            json={"method": "prior_year_110"},
            headers={"If-Match": str(body["row_version"])},
        )
        assert stale.status_code == 409, stale.text

        q3 = next(q for q in cast(list[Json], moved.json()["installments"]) if q["quarter"] == 3)
        paid = await call(
            "PATCH",
            f"{E}/{schedule}/installments/3",
            json={"paid_on": "2027-09-14"},
            headers={"If-Match": "2"},
        )
        assert paid.status_code == 200, paid.text
        assert paid.json()["status"] == "paid"
        assert q3["status"] == "not_confirmed"

        listed = await call("GET", E, params={"tax_year": YEAR, "quarter": 3})
        assert listed.status_code == 200, listed.text
        assert cast(Json, listed.json()["counts"])["paid"] == 1
        union = await call("GET", "/v1/tax/payments", params={"tax_year": YEAR})
        assert union.status_code == 200, union.text
        assert [p["source_kind"] for p in cast(list[Json], union.json()["items"])] == [
            "estimate_installment"
        ]

        book = await call("GET", f"{E}/export.xlsx", params={"tax_year": YEAR})
        assert book.status_code == 200, book.text
        sheet = load_workbook(io.BytesIO(book.content)).active
        assert sheet is not None
        assert sheet.max_row == 5
        for row in sheet.iter_rows(min_row=2, max_col=1):
            assert row[0].data_type == "s"

        prospect = await estimates.create(
            cast(object, await board.person("Nora Vale", None)),  # type: ignore[arg-type]
            cast(uuid.UUID, entity),
            basis_tax_return_id=None,
            tax_year=YEAR + 1,
            jurisdiction="US",
            form="1041-ES",
            method="prospect",
            prior_year_tax=None,
            prior_agi_over_threshold=None,
            projected_withholding=None,
            payment_method_label=None,
        )
        asked = await call(
            "POST", f"{E}/{prospect}/installments/1/confirmation-requests", json={}, headers=KEY
        )
    assert (asked.status_code, asked.json()["detail"]) == (409, "no_basis_return"), asked.text
