"""The platform's audit labelers and value resolvers for identity-owned targets (G-02-T09;
SPEC-349 §5; DEC-435).

Identity depends on no module, so it cannot register into `platform`'s slots itself; the platform,
which may read `identity.api`, registers for it:

- `user`: a person's display name (Confidential), for labels and the label index.
- `ethical_wall`: the people a wall names, as the values section's rows (who is walled, who
  approved it). Display names only; the wall's client is named by its owner's labeler when one
  is registered, never here.

The other v1 target types register from their owners as they land: `ai_policy` (G-02-T23/T24),
`security_policy` and `support_session` (G-02-T14), `membership`, `evidence_version`,
`request_item` and `pii_reveal` (their modules, through `platform.api`). Until then their values
read `unavailable` ("Values not available").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from abacus.modules.identity.api import AuthContext, names_of
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


def register() -> None:
    register_audit_labeler("user", label_users)
    register_audit_value_resolver("ethical_wall", wall_values)
