"""A-07-T41 (TASK-6735; DEC-3302): AUD-23's report date and city, and the report's kind from the
engagement type (AUD-23 e/f), in the report builder."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.assurance import report_builder as rb
from abacus.modules.identity.api import AuthContext, Forbidden

WORK_ITEM = uuid.uuid4()


def _ctx(kind: ActorKind = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)), user, uuid.uuid4(), None, None
    )


def _state(status: str = "draft", version: int = 3, report: bool = True) -> rb.ReportState:
    return rb.ReportState(
        uuid.uuid4() if report else None, "audit", status, 2, "sha256:x",
        rb.default_choices(), (), None, version,
    )  # fmt: skip


@pytest.fixture
def person(monkeypatch: pytest.MonkeyPatch) -> None:
    async def engagement(*_: object) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr(rb, "_person", engagement)


@pytest.mark.parametrize(
    ("engagement_type", "kind"),
    [("ebp_audit", "audit"), ("fs_audit", "audit"), ("review", "review"),
     ("compilation", "compilation"), (None, "audit")],
)  # fmt: skip
async def test_the_reports_kind_follows_the_engagement_type(
    monkeypatch: pytest.MonkeyPatch, engagement_type: str | None, kind: str
) -> None:
    class Item:
        engagement_id = uuid.uuid4()

    async def item(*_: object) -> Item:
        return Item()

    async def of_type(*_: object) -> str | None:
        return engagement_type

    monkeypatch.setattr(rb, "assurance_item", item)
    monkeypatch.setattr(rb, "engagement_type_of", of_type)
    assert await rb.report_kind_of(TenantContext(uuid.uuid4(), "system", "t"), WORK_ITEM) == kind
    assert rb.FAMILY[rb.KIND_OF_TYPE.get(engagement_type or "", "audit")].endswith("_report")


@pytest.mark.usefixtures("person")
async def test_a_date_needs_a_report_a_current_version_and_a_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {"state": _state(report=False)}

    async def state(*_: object) -> rb.ReportState:
        return current["state"]

    monkeypatch.setattr(rb, "state", state)
    with pytest.raises(rb.NotFound):
        await rb.set_report_date(_ctx(), WORK_ITEM, date(2026, 10, 9), "Chicago, Illinois", 3)
    current["state"] = _state()
    with pytest.raises(rb.StaleReport):
        await rb.set_report_date(_ctx(), WORK_ITEM, date(2026, 10, 9), "Chicago, Illinois", 2)
    current["state"] = _state(status="approved")
    with pytest.raises(rb.ReportNotDraft):
        await rb.set_report_date(_ctx(), WORK_ITEM, date(2026, 10, 9), "Chicago, Illinois", 3)


@pytest.mark.usefixtures("person")
@pytest.mark.parametrize("city", ["", "   ", "Chicago\nIllinois", "x" * 121])
async def test_the_city_is_one_short_line(city: str) -> None:
    with pytest.raises(rb.DomainInvalid):
        await rb.set_report_date(_ctx(), WORK_ITEM, date(2026, 10, 9), city, 3)


async def test_the_agent_never_dates_the_report() -> None:
    with pytest.raises(Forbidden):
        await rb.set_report_date(_ctx("agent"), WORK_ITEM, date(2026, 10, 9), "Chicago", 1)


@pytest.mark.usefixtures("person")
async def test_a_partner_approved_report_keeps_its_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Security review (S35 round 2): the date is outside the version's hash, so once the EP's L4
    stands on the current version the date and city are fixed."""

    async def state(*_: object) -> rb.ReportState:
        return _state()

    async def approved(*_: object) -> bool:
        return True

    monkeypatch.setattr(rb, "state", state)
    monkeypatch.setattr(rb, "_partner_approved", approved)
    with pytest.raises(rb.ReportNotDraft):
        await rb.set_report_date(_ctx(), WORK_ITEM, date(2026, 10, 9), "Chicago, Illinois", 3)
