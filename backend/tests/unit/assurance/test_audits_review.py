"""Security review fixes on the audits family (A-01-T02 / T05 follow-up; SPEC-330 AC-3, AC-14):
a stub authorises before it answers 501, so a client principal or an agent never learns the flag
state; PATCH profile refuses a null 103(a)(3)(C) label and an empty body (422); the C5 v1.1 row
fields are firm-only."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.kernel.db import ActorKind, TenantContext
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.assurance import audits_contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.requests import contract as requests_contract
from abacus.modules.requests.api import RequestLatestUploadOut, RequestOwedByOut

Stub = Callable[..., Awaitable[object]]
ACTIONS = (
    ("engagement.read_metadata", None),
    ("engagement.read", uuid.uuid4()),
    ("request_item.read", uuid.uuid4()),
    ("assurance.record_release", uuid.uuid4()),
    ("assurance.record_archive", uuid.uuid4()),
)


def _ctx(kind: ActorKind = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)), user, uuid.uuid4(), None, None, client=client
    )


async def _on(_tenant: object, _flag: object) -> bool:
    return True


@pytest.mark.parametrize(("action", "work_item"), ACTIONS)
@pytest.mark.parametrize(
    "ctx", [_ctx(client=True), _ctx("agent"), _ctx("system")], ids=["client", "agent", "system"]
)
async def test_a_client_an_agent_or_the_system_never_reaches_the_501(
    action: str, work_item: uuid.UUID | None, ctx: AuthContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audits_contract, "flag_enabled", _on)
    stub = cast(Stub, vars(audits_contract)["_stub"])
    with pytest.raises(Forbidden):
        await stub(ctx, action, work_item)


async def test_a_person_the_matrix_refuses_gets_403_not_501(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audits_contract, "flag_enabled", _on)
    seen: list[str] = []

    async def deny(ctx: object, action: str, work_item_id: uuid.UUID) -> None:
        seen.append(action)
        raise Forbidden(action, "role")

    monkeypatch.setattr(audits_contract, "_authorise_on_item", deny)
    stub = cast(Stub, vars(audits_contract)["_stub"])
    with pytest.raises(Forbidden):
        await stub(_ctx(), "assurance.record_release", uuid.uuid4())
    assert seen == ["assurance.record_release"]


async def test_an_allowed_person_reaches_the_501(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audits_contract, "flag_enabled", _on)

    async def allow(ctx: object, action: str, work_item_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(audits_contract, "_authorise_on_item", allow)
    stub = cast(Stub, vars(audits_contract)["_stub"])
    with pytest.raises(NotImplementedYet):
        await stub(_ctx(), "engagement.read", uuid.uuid4())
    with pytest.raises(NotImplementedYet):
        await stub(_ctx(), "engagement.read_metadata", None)


def test_ac14_a_null_103a3c_label_is_refused() -> None:
    with pytest.raises(ValidationError):
        audits_contract.AuditProfileIn.model_validate(
            {"limited_scope_103a3c": None, "seen_version": 1}
        )


def test_ac14_an_empty_profile_patch_is_refused() -> None:
    with pytest.raises(ValidationError):
        audits_contract.AuditProfileIn.model_validate({"seen_version": 1})
    ok = audits_contract.AuditProfileIn.model_validate({"ebp_plan_kind": None, "seen_version": 1})
    assert ok.model_fields_set == {"ebp_plan_kind", "seen_version"}


def _row() -> requests_contract.BinderRequestRowOut:
    return requests_contract.BinderRequestRowOut(
        id=uuid.uuid4(),
        category_id=None,
        title="Trust agreement",
        status=requests_contract.RequestStatus.REQUESTED,
        overdue=False,
        client_visible=True,
        kind="client_upload",
        owed_by=RequestOwedByOut(kind="third_party", display="Sam Ortiz, Keystone"),
        latest_upload=RequestLatestUploadOut(
            evidence_version_id=uuid.uuid4(),
            path_label="initial-input/x.pdf",
            uploaded_on=date(2026, 9, 11),
            uploader_kind="client",
        ),
        match_confidence=94,
    )


def test_the_c5_v1_1_fields_are_firm_only() -> None:
    row = _row()
    shown = requests_contract.for_viewer(row, _ctx(client=True))
    assert (shown.owed_by, shown.latest_upload, shown.match_confidence) == (None, None, None)
    assert shown.title == row.title
    firm = requests_contract.for_viewer(row, _ctx())
    assert firm.match_confidence == 94
