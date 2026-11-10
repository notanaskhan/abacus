"""P-05-T08 (ac-test-author; SPEC-650 AC-7, AC-8, AC-15, AC-30, AC-36, AC-38; P-05 §8.2): P-05's
consumer contract tests for C3 (review grammar), C13 (the human-gate projection) and C16
(notification kinds), and the matrix half of AUD-29's readers. Written from the SPEC and the
contracts, not from the services.

- C16: `mention.created` is a second source of the existing `mention` (never a second
  registration); `todo_assigned` is registered; neither sentence can carry a body; a mention
  reaches only a person still on the team when it fans out (AC-8).
- C13 and C3: no comment, thread or to-do is a gate source or a reviewable, so none can enter the
  `human_gates` projection or block a sign-off (R7, AC-15, AC-30).
- AUD-29 readers (AC-36, AC-38): the engagement team reads, firm admins and client roles do not,
  staff and seniors gain nothing on ADM-07's `audit_event.read`, export needs a fresh MFA.
"""

from __future__ import annotations

import uuid

import pytest

from abacus.modules.identity.api import RULES
from abacus.modules.notifications import api as notifications
from abacus.modules.notifications import catalogue
from abacus.modules.review import gates, slots

COLLABORATION_KINDS = {"todo", "comment_thread", "thread_comment", "comment"}


def test_c16_mention_created_is_a_source_of_the_existing_mention_kind() -> None:
    entry = notifications.CATALOGUE["mention.created"]
    assert entry.kind == "mention"
    assert entry.subject_type == "comment_thread"
    codes = notifications.registered()
    assert codes.count("mention") == 1


def test_c16_todo_assigned_is_registered_and_fed_by_todo_assigned() -> None:
    assert "todo_assigned" in notifications.registered()
    entry = notifications.CATALOGUE["todo.assigned"]
    assert (entry.kind, entry.subject_type, entry.subject_key) == (
        "todo_assigned",
        "todo",
        "todo_id",
    )


@pytest.mark.parametrize("event", ["mention.created", "todo.assigned"])
def test_c16_the_sentences_carry_no_body_or_row_text(event: str) -> None:
    sentence = notifications.TEMPLATES[event]
    assert "{body}" not in sentence and "{text}" not in sentence and "{title}" not in sentence


async def test_c16_ac8_a_mention_of_someone_off_the_team_notifies_nobody(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, engagement = uuid.uuid4(), uuid.uuid4()
    hannah, removed = uuid.uuid4(), uuid.uuid4()

    async def team_of(_tenant: uuid.UUID, _engagement: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
        return [(hannah, "manager")]

    monkeypatch.setattr(catalogue, "team_of", team_of)
    entry = notifications.CATALOGUE["mention.created"]
    payload: dict[str, object] = {"engagement_id": str(engagement)}
    assert await entry.recipients(tenant, {**payload, "user_id": str(hannah)}) == [hannah]
    assert await entry.recipients(tenant, {**payload, "user_id": str(removed)}) == []
    assigned = notifications.CATALOGUE["todo.assigned"]
    assert await assigned.recipients(tenant, {**payload, "assignee_user_id": str(removed)}) == []


def test_c13_no_collaboration_object_is_a_gate_source() -> None:
    sources = gates._SOURCES  # pyright: ignore[reportPrivateUsage] -- the C13 registry under test
    assert not {s.subject_type for s in sources.values()} & COLLABORATION_KINDS


def test_c3_no_comment_or_to_do_is_a_reviewable_so_none_blocks_a_sign_off() -> None:
    providers = slots._PROVIDERS  # pyright: ignore[reportPrivateUsage] -- the C3 registry under test
    assert not set(providers) & COLLABORATION_KINDS


TEAM = (
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "specialist",
    "eqr_reviewer",
    "reviewer",
)


@pytest.mark.parametrize("role", TEAM)
def test_ac36_the_engagement_team_reads_the_activity_log(role: str) -> None:
    assert RULES["audit_event.read_engagement"].decisions.get(role) == "allow"


@pytest.mark.parametrize(
    "role", ["firm_admin", "client_admin", "client_contributor", "client_service", "agent"]
)
def test_ac36_firm_admins_clients_and_the_agent_do_not(role: str) -> None:
    assert RULES["audit_event.read_engagement"].decisions.get(role, "deny") == "deny"


@pytest.mark.parametrize("role", ["senior", "staff"])
def test_ac36_staff_gain_no_adm07_access(role: str) -> None:
    assert RULES["audit_event.read"].decisions.get(role, "deny") != "allow"


def test_ac38_export_needs_a_fresh_mfa() -> None:
    assert RULES["export.create"].mfa_recent is True
