# ac-test-author: ayushkbhatia
"""P-01-T14 (ADR-078): C16 notifications-half contract tests, written from
`docs/contracts/notifications.md` §3 and P-01 §4.6 and AC 3.1.9, through `notifications.api` only.

- Every registered kind code is undotted, or one of the legacy dotted codes C16 lists.
- No code is registered twice; a second, different registration fails.
- Inline actions come from the closed set, and agent-originated kinds offer none (INV-1).
- The row model carries identifiers and codes; only the read-time `facts` are Restricted.

That every registered code also passes the database CHECK is proved against a migrated Postgres
in `tests/integration/backfill/test_p01t14_notifications.py`.
"""

from __future__ import annotations

import re
from typing import Final, get_args

import pytest

from abacus.kernel.classification import level_of, restricted_fields
from abacus.modules.notifications import api as notifications
from abacus.modules.notifications.contract import (
    InlineAction,
    NotificationFeedOut,
    NotificationItemOut,
)

# C16 §3 "Kind-code convention": new codes are snake_case with no dot.
UNDOTTED: Final = re.compile(r"[a-z][a-z_]*")
# C16 §3: the legacy SPEC-013 codes that stay valid (`support_session.*`, `budget.*`, ...).
LEGACY_PREFIXES: Final = ("support_session.", "budget.", "connection.")
LEGACY_CODES: Final = frozenset(
    {
        "engagement.member_self_joined",
        "engagement_member.added",
        "independence.requested",
        "reminders.drafted",
        "agent.digest",
    }
)
# Spec drift (recorded in work/tasks/TASK-993): SPEC-305 (TASK-306) registered these three dotted
# codes before C16 froze, and C16's legacy list does not name them. They are tested as drift.
SPEC_305_DRIFT: Final = frozenset(
    {"materiality.proposed", "risk.approval_requested", "finding.severity_proposed"}
)
# C16 §3 and P-01 AC 3.1.9: the closed set, and the agent-originated kinds that offer none.
CLOSED_SET: Final = frozenset({"accept_document", "return_document", "open_sign_off"})
AGENT_ORIGINATED: Final = frozenset(
    {
        "run_finished",
        "run_needs_input",
        "proposal_routed",
        "trigger_run_finished",
        "template_update_available",
    }
)


def _legacy(code: str) -> bool:
    return code in LEGACY_CODES or code.startswith(LEGACY_PREFIXES)


def test_ac_c16_every_registered_code_is_undotted_or_a_listed_legacy_code() -> None:
    codes = notifications.registered()
    assert codes, "the SPEC-013 catalogue registers its kinds"
    dotted = {c for c in codes if not UNDOTTED.fullmatch(c)}
    assert {c for c in dotted if not _legacy(c)} == SPEC_305_DRIFT & dotted


def test_ac_c16_the_three_renamed_kinds_are_registered_undotted() -> None:
    # P-01-T03: evidence.uploaded -> client_uploaded, comment.mentioned -> mention,
    # review.assigned -> review_assigned.
    codes = set(notifications.registered())
    assert {"client_uploaded", "mention", "review_assigned"} <= codes
    assert not {"evidence.uploaded", "comment.mentioned", "review.assigned"} & codes


def test_ac_c16_every_catalogued_event_feeds_a_registered_kind() -> None:
    codes = set(notifications.registered())
    assert {entry.kind for entry in notifications.CATALOGUE.values()} <= codes
    assert set(notifications.SUBSCRIPTIONS) == set(notifications.CATALOGUE)


@pytest.mark.parametrize("code", ["thing.happened", "client.uploaded", "run.needs_input"])
def test_ac_c16_a_new_dotted_code_is_refused(code: str) -> None:
    with pytest.raises(ValueError, match="undotted"):
        notifications.register_kind(notifications.NotificationKind(code, "other", "Bell"))
    assert notifications.kind_of(code) is None


def test_ac_c16_no_code_is_registered_twice() -> None:
    codes = notifications.registered()
    assert len(codes) == len(set(codes))
    for code in ("mention", "client_uploaded", "budget.anomaly"):
        before = notifications.kind_of(code)
        assert before is not None
        with pytest.raises(ValueError, match="already registered"):
            notifications.register_kind(notifications.NotificationKind(code, "other", "Bell"))
        assert notifications.kind_of(code) == before  # the first registration stands


def test_ac3_1_9_inline_actions_stay_in_the_closed_set() -> None:
    assert frozenset(get_args(InlineAction)) == CLOSED_SET
    for code in notifications.registered():
        kind = notifications.kind_of(code)
        assert kind is not None
        assert set(kind.inline_actions) <= CLOSED_SET, code
    with pytest.raises(ValueError, match="inline action"):
        notifications.register_kind(
            notifications.NotificationKind(
                "probe_closed_set",
                "other",
                "Bell",
                inline_actions=("approve",),  # type: ignore[arg-type]  # outside on purpose
            )
        )
    assert notifications.kind_of("probe_closed_set") is None


@pytest.mark.parametrize("code", sorted(AGENT_ORIGINATED))
def test_ac3_1_9_an_agent_originated_kind_cannot_offer_an_inline_action(code: str) -> None:
    for action in sorted(CLOSED_SET):
        with pytest.raises(ValueError, match="agent rows"):
            notifications.register_kind(
                notifications.NotificationKind(
                    code,
                    "run",
                    "Zap",
                    inline_actions=(action,),  # type: ignore[arg-type]  # each closed-set action
                )
            )
    found = notifications.kind_of(code)
    assert found is None or found.inline_actions == ()


def test_ac3_1_9_only_human_review_kinds_offer_inline_actions() -> None:
    offering = {
        code: set(k.inline_actions)
        for code in notifications.registered()
        if (k := notifications.kind_of(code)) is not None and k.inline_actions
    }
    # Today the client upload is the only row with Accept and Return (SHL-04c, d).
    assert offering == {"client_uploaded": {"accept_document", "return_document"}}


def test_ac7_a_row_carries_identifiers_and_codes_and_only_facts_are_restricted() -> None:
    fields = NotificationItemOut.model_fields
    assert set(fields) == {
        "id",
        "kind",
        "category",
        "created_at",
        "read",
        "actor",
        "subject",
        "engagement_id",
        "facts",
        "inline_actions",
        "pending",
    }
    schema = NotificationItemOut.model_json_schema()
    assert restricted_fields(NotificationItemOut) == ["facts"]
    assert {level_of(field) for name, field in fields.items() if name != "facts"} == {"internal"}
    assert "text" not in schema["properties"] and "title" not in schema["properties"]
    assert set(NotificationFeedOut.model_fields) == {
        "items",
        "next_cursor",
        "counts",
        "unread_count",
    }


@pytest.mark.xfail(
    strict=True,
    reason=(
        "C16 §3 and P-01 §4.6 name `notifications.register_kind_source(code, event, recipients, "
        "subject)`; notifications.api does not export it (SUBSCRIPTIONS is computed at import). "
        "Recorded in work/tasks/TASK-993-notifications-binder-independent-tests.md (#380)"
    ),
)
def test_ac_c16_a_later_epic_can_add_a_producing_event_to_an_existing_kind() -> None:
    assert callable(getattr(notifications, "register_kind_source", None))
