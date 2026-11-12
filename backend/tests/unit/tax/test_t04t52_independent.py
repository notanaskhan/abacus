"""T-04-T52 (ADR-078; TASK-7516): independent acceptance tests for T-04-T23 (a return's issues),
T-04-T28 (the review scenario's issues), T-04-T36 (K-1 activities and treatments) and T-04-T39
(residency), written from SPEC-649 §3.4, §3.7, §3.8 and the rows' acceptance, not from the
implementation.

Row acceptance: "A walled user sees no K-1 link, a hand resolve of the dependency issue is
refused, and every residency or treatment decision row names a human." Each test names its guard.
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import RULES, AuthContext
from abacus.modules.review import issue_resolutions
from abacus.modules.review.api import IssueSystemResolvedOnly
from abacus.modules.tax import k1_treatments, residency_service, return_issues

_source_visible = k1_treatments._source_visible  # pyright: ignore[reportPrivateUsage] -- the rule under test
_cell = return_issues._cell  # pyright: ignore[reportPrivateUsage] -- the rule under test

MIGRATION = (
    Path(__file__).resolve().parents[3] / "migrations/versions/0761_tax_individual_workspace.py"
)
PACKAGE = uuid.UUID("00000000-0000-4000-8000-00000000c0de")


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(Any, "manager"),  # Any: a firm role name stand-in
        None,
        client=client,
    )


# --- DEC-88: a walled person sees no K-1 link ----------------------------------------------------


def _fake_session(value: object):  # noqa: ANN202 -- a stand-in tenant_session
    @asynccontextmanager
    async def session(_tenant: object):  # noqa: ANN202
        yield SimpleNamespace(scalar=_scalar(value))

    return session


async def _ready(value: object) -> object:
    return value


def _scalar(value: object):  # noqa: ANN202 -- a session.scalar stand-in
    def scalar(*_a: object, **_k: object) -> object:
        return _ready(value)

    return scalar


def _wire_source(monkeypatch: pytest.MonkeyPatch, *, walled: bool, may_read: bool = True) -> None:
    async def engagement_of(_tenant: object, _work_item: object) -> uuid.UUID:
        return uuid.uuid4()

    async def get_ref(_ctx: object, _engagement: object) -> Any:  # noqa: ANN401 -- a stand-in ref
        if walled:
            raise NotFound("engagement")  # a wall answers 404 (ADR-026)
        return SimpleNamespace(resource=lambda: object())

    async def could(*_: object) -> bool:
        return may_read

    monkeypatch.setattr(k1_treatments, "tenant_session", _fake_session(uuid.uuid4()))
    monkeypatch.setattr(k1_treatments, "work_item_engagement", engagement_of)
    monkeypatch.setattr(k1_treatments, "get_ref", get_ref)
    monkeypatch.setattr(k1_treatments, "could", could)


def test_dec88_a_walled_person_sees_no_k1_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard: `_source_visible` hides the source package when the issuing engagement 404s."""
    _wire_source(monkeypatch, walled=True)
    assert asyncio.run(_source_visible(_ctx(), PACKAGE)) is None


def test_dec88_a_person_without_read_on_the_issuer_sees_no_k1_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_source(monkeypatch, walled=False, may_read=False)
    assert asyncio.run(_source_visible(_ctx(), PACKAGE)) is None


def test_dec88_a_person_who_reads_both_engagements_sees_the_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_source(monkeypatch, walled=False)
    assert asyncio.run(_source_visible(_ctx(), PACKAGE)) == PACKAGE
    assert asyncio.run(_source_visible(_ctx(), None)) is None


# --- the Draft K-1 dependency: only the system resolves it ---------------------------------------


def test_the_draft_k1_issue_is_system_resolved_only_and_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}  # Any: the issue kwargs under test

    async def create(_ctx: object, **kwargs: object) -> uuid.UUID:
        seen.update(kwargs)
        return uuid.uuid4()

    monkeypatch.setattr(return_issues, "create_issue", create)
    asyncio.run(
        return_issues.raise_draft_k1_issue(
            _ctx(), return_id=uuid.uuid4(), package_id=PACKAGE, assignee_user_id=None
        )
    )
    assert seen["source"].system_resolved_only is True
    assert set(seen["blocks"]) == {"final_approval", "export"}
    assert (seen["kind"], seen["priority"], seen["assignee_agent"]) == (
        "action_required",
        "high",
        False,
    )


@dataclass(frozen=True)
class _Issue:
    status: str
    record_type: str = "tax_return"
    record_id: uuid.UUID = PACKAGE
    version: int = 1


@pytest.mark.parametrize("to", ["resolved", "not_applicable"])
def test_a_hand_resolve_of_the_dependency_issue_is_refused(
    monkeypatch: pytest.MonkeyPatch, to: str
) -> None:
    """Guard: `move` checks `system_resolved_only` before writing (the database refuses too)."""

    async def one(_tenant: object, _issue: object) -> _Issue:
        return _Issue("open")

    async def record(*_: object) -> tuple[None, object, None]:
        return None, object(), None

    async def allowed(*_: object) -> None:
        return None

    async def system_only(*_: object) -> bool:
        return True

    @asynccontextmanager
    async def no_write(_tenant: object):  # noqa: ANN202
        raise AssertionError("nothing is written")
        yield

    monkeypatch.setattr(issue_resolutions, "_one", one)
    monkeypatch.setattr(issue_resolutions, "_record", record)
    monkeypatch.setattr(issue_resolutions, "authorise", allowed)
    monkeypatch.setattr(issue_resolutions, "_system_only", system_only)
    monkeypatch.setattr(issue_resolutions, "uow", no_write)
    with pytest.raises(IssueSystemResolvedOnly) as refused:
        asyncio.run(issue_resolutions.move(_ctx(), uuid.uuid4(), to, 1))
    assert refused.value.code == "system_resolved_only"


# --- override reason, reviewer-only confirmation and approval ------------------------------------


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
def test_an_override_needs_a_reason_before_anything_is_read(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    @asynccontextmanager
    async def untouched(_tenant: object):  # noqa: ANN202
        raise AssertionError("no read before the reason is checked")
        yield

    monkeypatch.setattr(k1_treatments, "tenant_session", untouched)
    with pytest.raises(k1_treatments.ReasonRequired):
        asyncio.run(k1_treatments.override_treatment(_ctx(), uuid.uuid4(), "Passive", reason, 1))


@pytest.mark.parametrize(
    ("action", "functions"),
    [
        ("residency.confirm", {"detail_reviewer", "manager_reviewer", "signer"}),
        ("k1_treatment.approve", {"detail_reviewer", "manager_reviewer", "signer"}),
        ("k1_treatment.override", {"manager_reviewer", "signer"}),
    ],
)
def test_decisions_are_held_by_reviewer_functions_never_the_agent(
    action: str, functions: set[str]
) -> None:
    rule = RULES[action]
    assert set(rule.function_in) == functions
    assert "preparer" not in rule.function_in
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert rule.decisions.get(principal) != "allow", (action, principal)


def test_residency_confirmation_needs_a_named_approver_and_a_known_option() -> None:
    tenant = _ctx().tenant
    with pytest.raises(residency_service.OptionUnknown):
        asyncio.run(
            residency_service.confirm_approved(
                tenant, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "somewhere_else"
            )
        )
    with pytest.raises(residency_service.ConfirmNotPermitted):
        asyncio.run(
            residency_service.confirm_approved(
                tenant, uuid.uuid4(), None, uuid.uuid4(), "full_year_nys_nyc"
            )
        )


def test_every_decision_row_names_a_human_in_the_database() -> None:
    """Guard: `residency_confirmed` binds a confirmed row to its person and its proposal, and the
    treatment events' check refuses a decision whose actor is not a person."""
    sql = MIGRATION.read_text()
    assert "CONSTRAINT residency_confirmed CHECK" in sql
    assert "confirmed_by IS NOT NULL" in sql
    assert "status <> 'confirmed' OR proposal_id IS NOT NULL" in sql
    assert "CONSTRAINT k1_treatment_events_decided_by_a_person CHECK" in sql
    override = inspect.getsource(k1_treatments.override_treatment)
    assert '"by": ctx.user_id' in override  # the overriding person, never the agent


@pytest.mark.parametrize(
    ("confirmed", "asked", "status"),
    [(True, True, "confirmed"), (False, True, "action_required"), (False, False, "review_point")],
)
def test_residency_status_projection(confirmed: bool, asked: bool, status: str) -> None:
    assert residency_service.status_of(confirmed, asked) == status


# --- human-sent client questions -----------------------------------------------------------------


def test_only_a_person_sends_a_question_to_the_client() -> None:
    rule = RULES["issue.send_to_client"]
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"


@pytest.mark.parametrize(
    "recommended", ["full_year_nys_nyc", "full_year_nys_part_year_nyc", "part_year_nys"]
)
def test_the_client_question_is_template_words_only(recommended: str) -> None:
    title, wording = residency_service.client_question(recommended)  # type: ignore[arg-type] -- the parametrised option keys
    labels = [o.label for o in residency_service.OPTIONS]
    first = wording.split("\n")[1]
    assert first == f"- {next(o.label for o in residency_service.OPTIONS if o.key == recommended)}"
    assert all(label in wording for label in labels)
    assert not any(ch.isdigit() for ch in title + wording)  # no figure, no day count travels


# --- CSV escaping and activity attribution -------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "cell"),
    [
        ("=SUM(A1:A9)", "'=SUM(A1:A9)"),
        ("+1 555", "'+1 555"),
        ("-(1,550)", "'-(1,550)"),
        ("@cmd", "'@cmd"),
        ("\tTabbed", "'\tTabbed"),
        ("\rReturn", "'\rReturn"),
        ("Box 18A", "Box 18A"),
        (None, ""),
    ],
)
def test_csv_cells_are_neutralised_against_formula_injection(value: object, cell: str) -> None:
    assert _cell(value) == cell


def test_the_csv_export_is_a_person_s_audited_export() -> None:
    assert return_issues.EXPORT_ACTION == "export.create"
    source = inspect.getsource(return_issues.issues_csv)
    assert "export.created" in source


def test_issue_categories_name_their_source() -> None:
    assert return_issues.category_for("k1_dependency", "draft_k1") == "approvals/k1"
    assert return_issues.dependency_ref(PACKAGE).endswith(str(PACKAGE))
