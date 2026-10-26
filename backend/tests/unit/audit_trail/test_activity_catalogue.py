"""G-02-T08 (TASK-1329; SPEC-349 AC-1, AC-3): the activity catalogue v1.

The static check: every audited action literal in the codebase (`.record("entity.verb", ...)`)
has a catalogue entry, a module's registered entry, or a place on the reviewed fallback list, so
a new action's category and marker are a reviewed decision. And no agent or system event is ever
marked as an approval (`ok`), whatever the catalogue says (AC-3, INV-1)."""

from __future__ import annotations

import ast
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.audit_trail.activity_catalogue import (
    CATALOGUE,
    CatalogueEntry,
    activity_of,
    fallback,
    register_activity_kinds,
    registered_kinds,
)
from abacus.modules.audit_trail.activity_reviewed import REVIEWED_FALLBACK
from abacus.modules.audit_trail.explorer import (
    Reader,
    _Labels,  # pyright: ignore[reportPrivateUsage] -- the projection's input
    row_of,
)
from abacus.modules.identity.api import AuthContext

SRC: Final = Path(__file__).resolve().parents[3] / "src" / "abacus"
ACTION: Final = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")


def _audited_literals() -> set[str]:
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "record"
                and node.args
                and any(k.arg == "target" for k in node.keywords)
            ):
                found |= {
                    c.value
                    for c in ast.walk(node.args[0])
                    if isinstance(c, ast.Constant)
                    and isinstance(c.value, str)
                    and ACTION.fullmatch(c.value)
                }
    return found


def test_g02t08_every_audited_action_literal_has_an_entry_or_is_reviewed() -> None:
    literals = _audited_literals()
    assert len(literals) > 300, "the scan found the codebase's audited actions"
    known = set(registered_kinds()) | REVIEWED_FALLBACK
    missing = sorted(literals - known)
    assert missing == [], (
        "give these a catalogue entry (activity_catalogue.py) or review them onto "
        f"activity_reviewed.py: {missing}"
    )


def test_g02t08_the_reviewed_list_holds_no_catalogued_action() -> None:
    assert not (REVIEWED_FALLBACK & set(CATALOGUE))
    for action in REVIEWED_FALLBACK:
        assert ACTION.fullmatch(action), action


@pytest.mark.parametrize(
    ("action", "category", "mark"),
    [
        ("sample.approved", "decision", "ok"),
        ("support_session.revoked", "access", "no"),
        ("follow_up.sent", "communication", "pl"),
        ("firm_export.requested", "export", "pl"),
        ("auth_session.signed_in", "sign_in", "pl"),
        ("agent_run.started", "run", "pl"),
        ("request_item.received", "change", "pl"),
    ],
)
def test_g02t08_the_fallback_reads_the_entity_and_verb(
    action: str, category: str, mark: str
) -> None:
    found = fallback(action)
    assert (found.category, found.mark) == (category, mark)


def test_g02t08_a_module_registers_its_entries_once() -> None:
    entry = CatalogueEntry("change", "pl", ("version",))
    register_activity_kinds({"g02_probe.tested": entry})
    register_activity_kinds({"g02_probe.tested": entry})  # the same entry again is fine
    assert activity_of("g02_probe.tested") == entry
    with pytest.raises(ValueError, match="already has"):
        register_activity_kinds({"g02_probe.tested": CatalogueEntry("decision", "ok")})
    with pytest.raises(ValueError, match="already has"):
        register_activity_kinds({"ai_policy.approved": CatalogueEntry("change")})


def _reader() -> Reader:
    user = uuid.uuid4()
    ctx = AuthContext(TenantContext(uuid.uuid4(), "human", str(user)), user, user, None, None)
    return Reader(ctx, firm=False, walled=frozenset(), request_context=False)


def _row(
    actor_kind: str,
    actor_id: str,
    on_behalf: uuid.UUID | None,
    action: str = "ai_policy.approved",
) -> dict[str, object]:
    return {
        "seq": 7,
        "effective_at": datetime(2026, 9, 14, tzinfo=UTC),
        "action": action,
        "actor_kind": actor_kind,
        "actor_id": actor_id,
        "on_behalf_of_user_id": on_behalf,
        "policy_ref": None,
        "target_type": "ai_policy",
        "target_id": "4",
        "before_ref": None,
        "after_ref": {"version_no": 4, "content": "a" * 64},
        "engagement_of": None,
        "client_id": None,
        "office_id": None,
        "ip": "198.51.100.57",
    }


def test_ac3_no_agent_or_system_event_is_marked_as_an_approval() -> None:
    person = uuid.uuid4()
    labels = _Labels({}, {})
    human = row_of(_row("human", str(person), None), _reader(), labels)
    assert (human.mark, human.actor.kind) == ("ok", "person")
    agent = row_of(_row("agent", "agent:probe.agent:run", person), _reader(), labels)
    assert (agent.mark, agent.actor.kind) == ("pl", "via_agent")
    assert agent.actor.on_behalf_of is not None and agent.actor.agent_id == "probe.agent"
    system = row_of(_row("system", "system:probe", None), _reader(), labels)
    assert (system.mark, system.actor.kind) == ("pl", "system")


def test_m4_facts_are_identifiers_never_fingerprints_and_ip_is_null_for_others() -> None:
    row = row_of(
        _row("human", str(uuid.uuid4()), None, action="request_item.received"),
        _reader(),
        _Labels({}, {}),
    )
    assert row.detail_facts == {"version_no": 4}
    assert row.ip is None
