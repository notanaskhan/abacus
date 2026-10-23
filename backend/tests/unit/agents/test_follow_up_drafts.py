"""P-06-T14 (SPEC-319 AC-16; BND-01 b, BND-02 d): one follow-up per client contact per engagement,
each open request listed once, never one already waiting in a draft to that contact. And DEC-74:
no code path lets the agent principal send one."""

from __future__ import annotations

import ast
import uuid
from datetime import date
from pathlib import Path

from abacus.modules.agents import follow_up_drafts
from abacus.modules.agents.follow_up_drafts import group_by_contact
from abacus.modules.requests.api import FollowUpCandidate

E1, E2 = uuid.uuid4(), uuid.uuid4()
CLAIRE, PAUL, DANA = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
CONTACT = uuid.uuid4()


def _item(engagement: uuid.UUID, title: str) -> FollowUpCandidate:
    return FollowUpCandidate(
        id=uuid.uuid4(),
        engagement_id=engagement,
        binder_id=uuid.uuid4(),
        title=title,
        due_on=date(2026, 9, 1),
        client_assignee_user_id=None,
        binder_recipient_contact_ids=(),
    )


def test_ac16_one_draft_per_contact_per_engagement_with_each_request_once() -> None:
    a, b, c = _item(E1, "Brokerage statements"), _item(E1, "Form 1098"), _item(E2, "K-1")
    recipients = {
        a.id: [(CLAIRE, CONTACT), (PAUL, None)],
        b.id: [(CLAIRE, CONTACT)],
        c.id: [(CLAIRE, None)],
    }
    # The same request named twice in the selection is still listed once.
    groups = group_by_contact([a, b, a, c], recipients, set())
    assert {k: [i.title for i, _ in v] for k, v in groups.items()} == {
        (E1, CLAIRE): ["Brokerage statements", "Form 1098"],
        (E1, PAUL): ["Brokerage statements"],
        (E2, CLAIRE): ["K-1"],
    }
    assert [contact for _, contact in groups[(E1, CLAIRE)]] == [CONTACT, CONTACT]


def test_ac16_a_request_already_waiting_to_that_contact_is_never_repeated() -> None:
    a, b = _item(E1, "Brokerage statements"), _item(E1, "Form 1098")
    recipients = {a.id: [(CLAIRE, None), (DANA, None)], b.id: [(CLAIRE, None)]}
    groups = group_by_contact([a, b], recipients, {(CLAIRE, a.id)})
    assert {k: [i.title for i, _ in v] for k, v in groups.items()} == {
        (E1, CLAIRE): ["Form 1098"],
        (E1, DANA): ["Brokerage statements"],
    }


def test_ac16_nothing_left_to_chase_drafts_nothing() -> None:
    a = _item(E1, "Brokerage statements")
    assert group_by_contact([a], {a.id: [(CLAIRE, None)]}, {(CLAIRE, a.id)}) == {}
    assert group_by_contact([a], {}, set()) == {}


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                found.add(func.id)
            elif isinstance(func, ast.Attribute):
                found.add(func.attr)
    return found


def test_ac19_the_p4_tick_never_reaches_a_send_path() -> None:
    """DEC-74: the agent's P-4 module drafts; it calls no send, deliver or grant function."""
    p4 = Path(follow_up_drafts.__file__).with_name("follow_ups.py")
    calls = _calls(p4)
    assert "insert_follow_up" in calls
    assert not {c for c in calls if "send" in c or "deliver" in c or "grant" in c}


def test_ac19_every_send_path_refuses_a_non_person_before_anything_else() -> None:
    """Each public send, undo and dismiss starts with the human-only check (INV-1)."""
    tree = ast.parse(Path(follow_up_drafts.__file__).read_text(encoding="utf-8"))
    functions = {
        n.name: n for n in tree.body if isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef)
    }
    for name in ("send", "send_many", "undo", "dismiss", "edit", "draft_for"):
        first = functions[name].body[1 if ast.get_docstring(functions[name]) else 0]
        assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
        assert isinstance(first.value.func, ast.Name) and first.value.func.id == "_human", name
