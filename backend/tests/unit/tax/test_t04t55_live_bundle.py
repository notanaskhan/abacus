"""T-04-T55 (TASK-7514; T-04 AC-13.2; DEC-4514): the post-window live-path bundle. The return frame
lists T-04's tabs only with their flag on and only for an individual return; the draft-run entry
is a person's, checks `tax_return.draft_run` on the return, refuses a return past final approval
and starts T-04-T25's run; the export's field-profile hook is the engine's validated profile."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import dataclass
from typing import Any, cast

import pytest

from abacus.kernel._flags import TAX_REVIEW_WORKSPACE
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import api as tax_api
from abacus.modules.tax import draft_entry, export_fields, overview, return_tabs

RETURN = uuid.UUID("00000000-0000-4000-8000-0000000000aa")
ENGAGEMENT = uuid.UUID("00000000-0000-4000-8000-0000000000bb")


def _ctx(*, kind: str = "human", client: bool = False, support: bool = False) -> AuthContext:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), cast(Any, kind), str(user)),  # Any: an actor kind under test
        user,
        uuid.uuid4(),
        cast(Any, "manager"),  # Any: a firm role name stand-in
        None,
        client=client,
    )
    if support:
        object.__setattr__(ctx, "is_support", True)
    return ctx


# --- the return frame's tabs ---------------------------------------------------------------------


def _flags(on: bool):  # noqa: ANN202 -- a fake flag reader
    async def enabled(_tenant: object, flag: Flag) -> bool:
        assert flag is TAX_REVIEW_WORKSPACE
        return on

    return enabled


@pytest.mark.parametrize(
    ("on", "form", "tabs"),
    [
        (True, "1040", ["overview", "intake", "review", "issues", "activity"]),
        (False, "1040", ["overview", "intake"]),
        (True, "1065", ["overview", "intake"]),  # T-05's entity tabs register their own
    ],
)
def test_the_frame_lists_t04_tabs_with_the_flag_on_for_individual_returns(
    monkeypatch: pytest.MonkeyPatch, on: bool, form: str, tabs: list[str]
) -> None:
    monkeypatch.setattr(return_tabs, "flag_enabled", _flags(on))
    found = asyncio.run(return_tabs.frame_tabs(_ctx().tenant, form))
    assert [t.tab for t in found] == tabs
    assert all(t.count is None for t in found)


def test_tab_registration_fails_closed() -> None:
    with pytest.raises(ValueError, match="T-02's own"):
        return_tabs.register_return_tab("overview", TAX_REVIEW_WORKSPACE, order=1)
    with pytest.raises(ValueError, match="already registered"):
        return_tabs.register_return_tab("review", TAX_REVIEW_WORKSPACE, order=99)
    # The same registration again (a reloaded module) is a no-op.
    return_tabs.register_return_tab(
        "review", TAX_REVIEW_WORKSPACE, order=10, forms=frozenset({"1040", "1040x"})
    )


def test_the_frame_record_reads_the_registry_and_offers_run_draft() -> None:
    assert "tax_return.draft_run" in overview.ACTIONS
    assert "frame_tabs" in inspect.getsource(overview.record)


# --- the draft-run entry -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Item:
    work_item_id: uuid.UUID
    engagement_id: uuid.UUID


@dataclass(frozen=True)
class _Resource:
    engagement_id: uuid.UUID
    work_item_id: uuid.UUID | None = None


def _wire(monkeypatch: pytest.MonkeyPatch, status: str | None, seen: list[object]) -> None:
    async def facts(_ctx: object, target: str) -> list[_Item]:
        assert target == "tax_return"
        return [_Item(RETURN, ENGAGEMENT)]

    async def resource(_tenant: object, engagement_id: uuid.UUID) -> _Resource:
        return _Resource(engagement_id)

    async def authorise(_ctx: object, action: str, res: _Resource) -> None:
        seen.append((action, res.work_item_id))

    async def read_status(_ctx: object, _r: uuid.UUID) -> str | None:
        return status

    async def start(_ctx: object, r: uuid.UUID) -> uuid.UUID:
        seen.append(("start", r))
        return uuid.UUID(int=7)

    monkeypatch.setattr(draft_entry, "work_item_facts", facts)
    monkeypatch.setattr(draft_entry, "engagement_resource", resource)
    monkeypatch.setattr(draft_entry, "authorise", authorise)
    monkeypatch.setattr(draft_entry, "_status", read_status)
    monkeypatch.setattr(draft_entry, "start_draft", start)


def test_a_person_starts_a_draft_run_on_an_open_return(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []
    _wire(monkeypatch, "in_review", seen)
    assert asyncio.run(draft_entry.run_draft(_ctx(), RETURN)) == uuid.UUID(int=7)
    assert seen == [("tax_return.draft_run", RETURN), ("start", RETURN)]


@pytest.mark.parametrize("status", sorted(draft_entry.LOCKED))
def test_a_return_past_final_approval_is_never_redrafted(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    seen: list[object] = []
    _wire(monkeypatch, status, seen)
    with pytest.raises(draft_entry.DraftNotAllowed) as refused:
        asyncio.run(draft_entry.run_draft(_ctx(), RETURN))
    assert refused.value.code == "draft_not_allowed"
    assert ("start", RETURN) not in seen


def test_the_agent_the_system_and_support_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []
    _wire(monkeypatch, "in_review", seen)
    for ctx in (_ctx(kind="agent"), _ctx(kind="system")):
        with pytest.raises(Forbidden):
            asyncio.run(draft_entry.run_draft(ctx, RETURN))
    with pytest.raises(NotFound):
        asyncio.run(draft_entry.run_draft(_ctx(client=True), RETURN))
    assert seen == []


def test_a_return_the_viewer_cannot_see_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []
    _wire(monkeypatch, "in_review", seen)
    with pytest.raises(NotFound):
        asyncio.run(draft_entry.run_draft(_ctx(), uuid.uuid4()))


def test_the_bundle_is_on_the_tax_api() -> None:
    assert tax_api.run_draft is draft_entry.run_draft
    assert [t.tab for t in return_tabs.registered_tabs()][:3] == ["review", "issues", "activity"]


# --- the export's field-profile hook -------------------------------------------------------------


def test_the_export_checks_engine_keys_against_the_engine_profile() -> None:
    source = inspect.getsource(export_fields)
    assert "engine_field_profile().valid_key" in source
    assert export_fields.EngineFieldUnmapped.code == "engine_field_unmapped"
