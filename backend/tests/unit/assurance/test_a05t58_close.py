"""A-05-T58 close (S31; TASK-6225; DEC-2820): EBP-07's 4i schedule from stored rows, and a keyed
value (DV-EBP-07-1's agent-off path).

The schedule is code's: the trust report's holdings, the participant loans and the plan's parties
in interest; it ties only when its total equals the draft's line 1c investments. A keyed value is
a person's alone, needs its citation note, and leaves the tie-out to code.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal as D
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import ebp_form5500 as svc
from abacus.modules.identity.context import AuthContext

TENANT = cast(TenantContext, SimpleNamespace(tenant_id=uuid.uuid4()))
WI = uuid.uuid4()


class _Result:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self.rows

    def one(self) -> SimpleNamespace:
        return self.rows[0]

    def __iter__(self):  # noqa: ANN204  # a row iterator double
        return iter(self.rows)


class _Session:
    def __init__(self, answers: dict[str, list[SimpleNamespace]], invested: D | None) -> None:
        self.answers = answers
        self.invested = invested

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, stmt: object, *_: object) -> _Result:
        sql = str(stmt)
        for key, rows in self.answers.items():
            if key in sql:
                return _Result(rows)
        raise AssertionError(sql)

    async def scalar(self, *_: object) -> D | None:
        return self.invested


def _db(monkeypatch: pytest.MonkeyPatch, invested: D | None, parties: list[str]) -> None:
    answers = {
        "ebp_trust_report_lines": [
            SimpleNamespace(fund_name="KRS 500 Index Fund", eoy=D("6120450")),
            SimpleNamespace(fund_name="Harborline Stable Value Fund", eoy=D("1163480")),
            SimpleNamespace(fund_name="Self-directed brokerage (BrokerWindow)", eoy=D("1605000")),
        ],
        "ebp_participant_loans": [SimpleNamespace(total=D("312400"), n=12)],
        "parties_in_interest": [SimpleNamespace(name=p) for p in parties],
    }

    def open_session(_t: object) -> _Session:
        return _Session(answers, invested)

    monkeypatch.setattr(svc, "tenant_session", open_session)


async def test_the_schedule_ties_to_the_draft_s_line_1c(monkeypatch: pytest.MonkeyPatch) -> None:
    _db(monkeypatch, D("9200930"), ["KRS", "Harborline"])
    found = await svc.schedule_4i_facts(TENANT, WI)
    assert found.total == D("9200930") and found.ties
    marks = {r.identity: r.mark for r in found.rows}
    assert marks == {
        "KRS 500 Index Fund": "*",
        "Harborline Stable Value Fund": "*",
        "Self-directed brokerage (BrokerWindow)": "",
        "Participant loans": "*",
    }
    loans = next(r for r in found.rows if r.identity == "Participant loans")
    assert not loans.cost_omitted and loans.cost == D(0)
    assert all(r.cost_omitted for r in found.rows if r.identity != "Participant loans")


async def test_without_the_draft_the_schedule_does_not_tie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _db(monkeypatch, None, [])
    found = await svc.schedule_4i_facts(TENANT, WI)
    assert not found.ties
    assert all(r.mark == "" or r.identity == "Participant loans" for r in found.rows)


def _ctx(kind: str = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # actor kind under test
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
        client=client,
    )


@pytest.mark.parametrize(
    ("ctx", "note"),
    [(_ctx("agent"), "Sched H p.2 line 1c(9)"), (_ctx(client=True), "p.2"), (_ctx(), "  ")],
    ids=["agent", "client", "no_note"],
)
async def test_only_a_person_keys_a_value_and_names_where_they_read_it(
    monkeypatch: pytest.MonkeyPatch, ctx: AuthContext, note: str
) -> None:
    async def allowed(*_: object) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr(svc, "_engagement", allowed)
    with pytest.raises(svc.KeyedValueRefused):
        await svc.key_line_value(ctx, WI, uuid.uuid4(), D("1163480"), note)


def test_a_party_in_interest_matches_by_name() -> None:
    assert svc._party_in_interest("KRS Bond Index Fund", ["krs"])  # pyright: ignore[reportPrivateUsage]  # the matcher under test
    assert not svc._party_in_interest("BrokerWindow", ["KRS"])  # pyright: ignore[reportPrivateUsage]  # the matcher under test
