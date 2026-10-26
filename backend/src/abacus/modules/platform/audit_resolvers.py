"""The platform's audit labelers and value resolvers for identity-owned targets (G-02-T09;
SPEC-349 §5; DEC-435).

Identity depends on no module, so it cannot register into `platform`'s slots itself; the platform,
which may read `identity.api`, registers for it:

- `user`: a person's display name (Confidential), for labels and the label index.
- `ethical_wall`: the people a wall names, as the values section's rows (who is walled, who
  approved it). Display names only; the wall's client is named by its owner's labeler when one
  is registered, never here.

- `user` (membership events, G-02-T09 gap, DEC-459) and `support_session`: identity's own
  readers (`identity.api.membership_audit_facts`, `support_session_audit_facts`) say what the
  event pins; the item is the person's display name for a membership.

`evidence_version`, `pii_reveal` and `request_item` register from their owners (evidence,
requests) through `platform.api`. `ai_policy` and `security_policy` wait for G-02-T14/T15; until
then their values read `unavailable` ("Values not available").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from abacus.modules.identity.api import (
    AuditFact,
    AuthContext,
    membership_audit_facts,
    names_of,
    support_session_audit_facts,
)
from abacus.modules.platform.audit_slots import (
    AuditEventRef,
    AuditLabel,
    AuditValueRow,
    AuditValues,
    register_audit_labeler,
    register_audit_value_resolver,
)

_WALL_PEOPLE: tuple[tuple[str, str], ...] = (
    ("user_id", "Walled person"),
    ("approver_user_id", "Approver"),
)


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def label_users(_viewer: AuthContext | None, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
    wanted = {i: u for i in ids if (u := _uuid(i)) is not None}
    names = await names_of(sorted(set(wanted.values()), key=str)) if wanted else {}
    return {i: AuditLabel(names[u], "confidential") for i, u in wanted.items() if u in names}


async def wall_values(_viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """Who the wall names, before and after the change (identifiers resolved to names)."""
    before, after = event.before_ref or {}, event.after_ref or {}
    people = {
        u for refs in (before, after) for key, _ in _WALL_PEOPLE if (u := _uuid(refs.get(key)))
    }
    names = await names_of(sorted(people, key=str)) if people else {}

    def name(refs: Mapping[str, str | int], key: str) -> str | None:
        user = _uuid(refs.get(key))
        return names.get(user) if user is not None else None

    rows = tuple(
        AuditValueRow(
            field=key,
            item_label=label,
            before=name(before, key),
            after=name(after, key),
            classification="confidential",
        )
        for key, label in _WALL_PEOPLE
        if name(before, key) is not None or name(after, key) is not None
    )
    return AuditValues("resolved", rows=rows) if rows else AuditValues("unavailable")


def _answer(facts: Sequence[AuditFact], item: str = "") -> AuditValues:
    rows = tuple(
        AuditValueRow(
            field=f.field,
            item_label=item,
            before=f.before,
            after=f.after,
            classification=f.classification,
        )
        for f in facts
    )
    return AuditValues("resolved", rows=rows) if rows else AuditValues("unavailable")


async def membership_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """A membership event on a `user` target: what its references pin (DEC-459)."""
    user = _uuid(event.target_id)
    if user is None or not event.action.startswith("membership."):
        return AuditValues("unavailable")
    facts = await membership_audit_facts(viewer.tenant, event.action, user, event.after_ref)
    names = await names_of([user]) if facts else {}
    return _answer(facts, names.get(user, ""))


async def support_session_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """A support session's request, approval or close (DEC-459)."""
    session = _uuid(event.target_id)
    if session is None:
        return AuditValues("unavailable")
    return _answer(await support_session_audit_facts(viewer.tenant, event.action, session))


def register() -> None:
    register_audit_labeler("user", label_users)
    register_audit_value_resolver("ethical_wall", wall_values)
    register_audit_value_resolver("user", membership_values)
    register_audit_value_resolver("support_session", support_session_values)
