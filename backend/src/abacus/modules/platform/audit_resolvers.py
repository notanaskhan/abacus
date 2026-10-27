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

- `security_policy` and `portal_security_policy` (G-02-T14, DEC-529): the values the event's own
  references pin (minutes, switches as `true`/`false`, the exempt account's name); nothing is read
  from the policy's current row, so a value never shows what changed since.

`evidence_version`, `pii_reveal` and `request_item` register from their owners (evidence,
requests) through `platform.api`. `ai_policy` waits for G-02-T23/T24 (versions do not exist yet);
until then its values read `unavailable` ("Values not available").
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


# The policy fields an event's references carry: (reference key, field name, kind).
_POLICY_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("require_sso", "require_sso", "bool"),
    ("session_absolute_minutes", "session_absolute_minutes", "int"),
    ("session_idle_minutes", "session_idle_minutes", "int"),
    ("idp_mfa_attested", "idp_mfa_attested", "bool"),
    ("allow", "allow_support_requests", "bool"),
    ("session_minutes", "portal_session_minutes", "int"),
)


def _ref_text(refs: Mapping[str, str | int], key: str, kind: str) -> str | None:
    value = refs.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return ("true" if value else "false") if kind == "bool" else str(value)


async def security_policy_values(_viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """G-02-T14 (DEC-529): a sign-in, portal or support-switch change, or the exempt account's
    designation, clearing or sign-in: only what the event's references pin."""
    before, after = event.before_ref or {}, event.after_ref or {}
    rows: list[AuditValueRow] = []
    for key, name, kind in _POLICY_FIELDS:
        old, new = _ref_text(before, key, kind), _ref_text(after, key, kind)
        if old is not None or new is not None:
            rows.append(
                AuditValueRow(field=name, before=old, after=new, classification="internal")
            )
    if event.action.startswith("sso_exempt_account."):
        people = {u for refs in (before, after) if (u := _uuid(refs.get("user_id")))}
        names = await names_of(sorted(people, key=str)) if people else {}
        old_user, new_user = _uuid(before.get("user_id")), _uuid(after.get("user_id"))
        rows.append(
            AuditValueRow(
                field="sso_exempt_account",
                before=names.get(old_user) if old_user is not None else None,
                after=names.get(new_user) if new_user is not None else None,
                classification="confidential",
            )
        )
    return AuditValues("resolved", rows=tuple(rows)) if rows else AuditValues("unavailable")


def register() -> None:
    register_audit_labeler("user", label_users)
    register_audit_value_resolver("ethical_wall", wall_values)
    register_audit_value_resolver("user", membership_values)
    register_audit_value_resolver("support_session", support_session_values)
    register_audit_value_resolver("security_policy", security_policy_values)
    register_audit_value_resolver("portal_security_policy", security_policy_values)
