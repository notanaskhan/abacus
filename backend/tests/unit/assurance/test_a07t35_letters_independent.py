"""Independent AC tests for A-07-T23, T24, T26 and T27 (A-07-T35; ADR-078; TASK-6528; DEC-3128).

Written from the A-07-T35 row, A-07 F4-F7 and the invariants, against the services' public
surface and the permission matrix, not the authors' tests. Row acceptance: "The suite fails if any
letter reaches a client principal before a named EP approval or if a regenerate drops a human
edit." Covered: going concern and the opinion decided only by the EP (INV-1); the rep-letter date
rule and the re-date mismatch; no amount or planning materiality in letter text; TCWG-only
governance reads (INV-4); walls and client principals answer 404 (INV-3); drafts attributed to the
initiator via Agent (INV-5); regenerate keeps human edits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Final

import pytest
import yaml

import abacus.modules.assurance.api  # noqa: F401  # registers A-07's decision kinds at import
from abacus.kernel.db import ActorKind, TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.assurance import agent_capabilities as caps
from abacus.modules.assurance import governance_comms as gc
from abacus.modules.assurance import governance_room as room
from abacus.modules.assurance import rep_letters as rl
from abacus.modules.assurance import report_builder as rb
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.review.api import decision_kind

ROOT: Final = Path(__file__).resolve().parents[4]
MATRIX: Final = ROOT / "docs/architecture/permission-matrix"
CLIENT_ROLES: Final = ("client_admin", "client_contributor", "third_party", "client_service")
RESERVED_VERBS: Final = ("approve", "sign", "send", "release", "decide", "lock", "conclude")


def _actions(module: str) -> dict[str, dict[str, Any]]:
    return dict(yaml.safe_load((MATRIX / f"{module}.yaml").read_text())["actions"])


def _ctx(kind: ActorKind = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)), user, uuid.uuid4(), None,
        datetime.now(UTC), client=client,
    )  # fmt: skip


# --- INV-1: going concern and the opinion are the engagement partner's alone -----------------


@pytest.mark.parametrize("code", ["going_concern", "opinion"])
def test_inv1_the_card_is_reserved_to_the_engagement_partner(code: str) -> None:
    assert decision_kind(code).reserved_role == "engagement_partner"
    decide = _actions("review")["decision.decide"]
    assert decide["agent"] == "deny" and decide["system"] == "deny"
    assert decide["reserved_role"] == "required" and decide["mfa_recent"] == "required"


async def test_inv1_going_concern_in_the_report_follows_the_decision_never_a_choice() -> None:
    with pytest.raises(rb.ChoiceLocked):
        await rb.validate(
            _ctx(), uuid.uuid4(), uuid.uuid4(), rb.default_choices(), "going_concern", True, None
        )


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_inv1_no_agent_or_system_sets_the_opinion(kind: ActorKind) -> None:
    with pytest.raises(Forbidden):
        await rb.validate(
            _ctx(kind), uuid.uuid4(), uuid.uuid4(), rb.default_choices(),
            "opinion_form", "unmodified", None,
        )  # fmt: skip


def test_inv1_only_the_ep_approves_the_report_and_its_letters() -> None:
    actions = _actions("assurance")
    for action in ("report.approve", "rep_letter.approve", "governance_comm.approve_send"):
        row = actions[action]
        allowed = {role for role, cell in row.items() if cell == "allow"}
        assert allowed == {"engagement_partner"}, action
        assert row.get("agent") == "deny", action
    for action in ("rep_letter.approve", "governance_comm.approve_send"):
        assert actions[action]["mfa_recent"] == "required", action


# --- the acceptance: no letter reaches a client principal before a named EP approval ----------


def test_ac_no_client_principal_and_no_agent_may_send_a_letter() -> None:
    actions = _actions("assurance")
    for action in ("rep_letter.send", "governance_comm.approve_send"):
        row = actions[action]
        for role in (*CLIENT_ROLES, "agent", "system"):
            assert row.get(role) == "deny", (action, role)


class _Session:
    def __init__(self, approved: bool, letter: bool = True) -> None:
        self.approved, self.letter = approved, letter

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
        row = SimpleNamespace(current_version_id=uuid.uuid4()) if self.letter else None
        return SimpleNamespace(first=lambda: row)

    async def scalar(self, *_a: object, **_k: object) -> bool:
        return self.approved


@pytest.mark.parametrize(("approved", "letter"), [(False, True), (False, False)])
async def test_ac_a_rep_letter_without_an_approval_of_its_current_version_never_sends(
    monkeypatch: pytest.MonkeyPatch, approved: bool, letter: bool
) -> None:
    monkeypatch.setattr(rl, "tenant_session", lambda _t: _Session(approved, letter))
    with pytest.raises(rl.LetterNotApproved):
        await rl.ensure_approved(TenantContext(uuid.uuid4(), "system", "test"), uuid.uuid4())


# --- the rep-letter date rule and re-date (A-07-T24) -----------------------------------------

REPORT_DATE: Final = date(2027, 10, 7)


@pytest.mark.parametrize(
    ("signed_on", "dated_as_of", "status"),
    [
        (REPORT_DATE, REPORT_DATE, "signed"),
        (REPORT_DATE + timedelta(days=1), REPORT_DATE, "date_mismatch"),
        (REPORT_DATE - timedelta(days=1), REPORT_DATE, "date_mismatch"),
        (REPORT_DATE, None, "date_mismatch"),
    ],
)
def test_the_rep_letter_is_signed_on_the_report_date_or_it_is_a_mismatch(
    signed_on: date, dated_as_of: date | None, status: str
) -> None:
    signed_at = datetime(signed_on.year, signed_on.month, signed_on.day, 15, tzinfo=UTC)
    outcome = rl.g7_outcome(signed_at, dated_as_of, signed_on)
    assert outcome.status == status
    assert outcome.signed_on == signed_on and outcome.dated_as_of == dated_as_of


def test_the_firms_date_not_utcs_decides() -> None:
    # 01:30 UTC on Oct 8 is still Oct 7 in the firm's zone: the firm's date is the one given.
    late = datetime(2027, 10, 8, 1, 30, tzinfo=UTC)
    assert rl.g7_outcome(late, REPORT_DATE, REPORT_DATE).status == "signed"


# --- no amount and no planning materiality in letter text --------------------------------------


async def _person_ok(*_a: object) -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.parametrize("wording", ["Corrected for $2,140.", "Over 18,915 in total.", "0.50 off"])
async def test_a_rep_letter_paragraph_with_an_amount_is_refused(
    monkeypatch: pytest.MonkeyPatch, wording: str
) -> None:
    monkeypatch.setattr(rl, "_person", _person_ok)
    with pytest.raises(rl.AmountInLetter):
        await rl.edit_paragraph(_ctx(), uuid.uuid4(), rl.GENERAL + 1, wording, "seen")


async def test_the_general_representations_are_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "_person", _person_ok)
    for n in (1, rl.GENERAL):
        with pytest.raises(rl.ParagraphLocked):
            await rl.edit_paragraph(_ctx(), uuid.uuid4(), n, "Plain words.", "seen")


def test_no_planning_letter_names_materiality_or_an_amount() -> None:
    clean = [gc.LetterPart("scope", "Scope", "We plan the audit.")]
    assert gc.letter_checks("planning_260", clean) == []
    for body, code in (
        ("Overall materiality was set low.", "materiality_in_planning_letter"),
        ("Revenue of $4,120,000.", "amount_in_planning_letter"),
    ):
        found = gc.letter_checks("planning_260", [gc.LetterPart("x", "Scope", body)])
        assert code in found, body


# --- INV-4: governance reads are TCWG-only --------------------------------------------------


def _grant(role: str, scope_kind: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), role=role, scope_kind=scope_kind, scope_id=uuid.uuid4()
    )


@pytest.mark.parametrize(
    ("role", "scope_kind", "opens"),
    [
        ("tcwg", "governance_room", True),
        ("client_admin", "governance_room", False),
        ("client_admin", "client", False),
        ("tcwg", "engagement", False),
    ],
)
async def test_inv4_only_a_tcwg_grant_on_the_room_opens_it(
    monkeypatch: pytest.MonkeyPatch, role: str, scope_kind: str, opens: bool
) -> None:
    grant = _grant(role, scope_kind)

    async def grants(*_a: object) -> list[SimpleNamespace]:
        return [grant]

    monkeypatch.setattr(room, "active_grants", grants)
    found = await room._room_grants(_ctx(client=True))  # pyright: ignore[reportPrivateUsage]  # the room's reader rule
    assert (grant.scope_id in found) is opens
    if not opens:
        with pytest.raises(NotFound):
            await room._open(_ctx(client=True), grant.scope_id)  # pyright: ignore[reportPrivateUsage]  # 404, not 403


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_inv4_no_firm_person_agent_or_system_reads_a_room(
    monkeypatch: pytest.MonkeyPatch, kind: ActorKind
) -> None:
    async def grants(*_a: object) -> list[SimpleNamespace]:
        return [_grant("tcwg", "governance_room")]

    monkeypatch.setattr(room, "active_grants", grants)
    assert await room._room_grants(_ctx()) == {}  # pyright: ignore[reportPrivateUsage]  # a firm person
    assert await room._room_grants(_ctx(kind, client=True)) == {}  # pyright: ignore[reportPrivateUsage]  # not a person


def test_inv4_the_portal_governance_reads_deny_agents_and_need_a_scope() -> None:
    portal = _actions("portal")
    for action in ("tcwg.read", "tcwg.acknowledge"):
        assert portal[action]["agent"] == "deny" and portal[action]["scope_only"] == "required"


# --- INV-3: walls and client principals answer 404 ---------------------------------------------


@pytest.mark.parametrize("service", [rl, gc])
async def test_inv3_a_client_principal_finds_no_letter(service: ModuleType) -> None:
    with pytest.raises(NotFound):
        await service._person(_ctx(client=True), uuid.uuid4(), "rep_letter.read")


@pytest.mark.parametrize("service", [rl, gc])
async def test_inv3_a_wall_answers_404_not_403(
    monkeypatch: pytest.MonkeyPatch, service: ModuleType
) -> None:
    async def item(*_a: object) -> SimpleNamespace:
        return SimpleNamespace(engagement_id=uuid.uuid4())

    async def ref(*_a: object) -> SimpleNamespace:
        return SimpleNamespace(resource=lambda: object())

    async def walled(*_a: object) -> None:
        raise NotFound("engagement")

    monkeypatch.setattr(service, "assurance_item", item)
    monkeypatch.setattr(service, "get_ref", ref)
    monkeypatch.setattr(service, "authorise", walled)
    with pytest.raises(NotFound):
        await service._person(_ctx(), uuid.uuid4(), "rep_letter.read")


# --- INV-5: drafts are attributed to the initiator via Agent -----------------------------------


async def test_inv5_a_composed_draft_is_the_initiators_and_reads_via_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _ctx()
    seen: dict[str, Any] = {}

    async def item(*_a: object) -> SimpleNamespace:
        return SimpleNamespace(engagement_id=uuid.uuid4())

    async def start(by: AuthContext, _wi: uuid.UUID) -> SimpleNamespace:
        seen["drafted_as"] = by
        return SimpleNamespace(version_no=2)

    async def record(_t: object, run: caps.CodeRun) -> uuid.UUID:
        seen["run"] = run
        return uuid.uuid4()

    monkeypatch.setattr(caps, "assurance_item", item)
    monkeypatch.setattr(rl, "start_letter", start)
    monkeypatch.setattr(caps, "_record", record)
    await caps.letter_compose(ctx, uuid.uuid4())
    run = seen["run"]
    assert seen["drafted_as"] is ctx  # the draft is written as the person who asked
    assert run.initiator_user_id == ctx.user_id
    assert set(run.task_scope) <= {"rep_letter.draft", "governance_comm.draft"}
    for step in run.steps:
        assert not any(verb in step.label.lower() for verb in RESERVED_VERBS), step.label


@pytest.mark.parametrize("service", [rl, gc])
async def test_inv5_an_agent_context_never_writes_a_letter_itself(service: ModuleType) -> None:
    with pytest.raises(Forbidden):
        await service._person(_ctx("agent"), uuid.uuid4(), "rep_letter.draft")


# --- regenerate keeps human edits (A-07-T26) ---------------------------------------------------


@pytest.mark.parametrize("kind", list(gc.KINDS))
def test_regenerate_never_drops_a_human_edit(kind: gc.Kind) -> None:
    first = gc.compose(kind, gc.Facts())
    assert first, kind
    edited = [
        gc.LetterPart(s.key, s.heading, f"A person's words for {s.key}.", s.built_from, True)
        for s in first
    ]
    merged = {s.key: s for s in gc.merge(edited, gc.compose(kind, gc.Facts()))}
    for part in edited:
        assert merged[part.key].body == part.body, (kind, part.key)
        assert merged[part.key].human_edited


def test_regenerate_refreshes_what_no_person_edited() -> None:
    first = gc.compose("planning_260", gc.Facts())
    later = gc.compose("planning_260", gc.Facts(significant_risks=(("R7", "Loans"),)))
    merged = {s.key: s for s in gc.merge(first, later)}
    assert merged["significant_risks"].built_from == ("R7",)
    assert not merged["significant_risks"].human_edited
