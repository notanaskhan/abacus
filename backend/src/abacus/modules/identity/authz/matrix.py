"""The permission matrix as typed rules, validated at import (ADR-027). PROTECTED.

Source: `docs/architecture/permission-matrix.yaml`, rendered into `_matrix.py` by
`abacus_tools.codegen.permission_matrix`. Anything this module doesn't understand is an import
error, so a matrix change can't silently mean something new.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

from abacus.modules.identity.authz._matrix import ACTIONS, ROLES

Decision = Literal[
    "allow",
    "deny",
    "assigned_only",
    "client_visible_only",
    "in_scope",
    "task_scope",
    "firm_setting",
]
_SIMPLE: frozenset[str] = frozenset(
    {"allow", "deny", "assigned_only", "client_visible_only", "in_scope", "task_scope"}
)
_FIRM_SETTING = re.compile(r"firm_setting\(([a-z_]+)\)")
_MODIFIERS = {
    "mfa_recent": "required",
    "requires": "reason",
    "notify": "engagement_team",
    # SPEC-025 (TASK-045): a staff member's engagement role counts only once they've confirmed
    # their independence for that engagement.
    "independence": "required",
}
_ACTION = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")
# Verbs that only read: archived engagements still allow them (`archived_write: deny`).
READ_VERBS = frozenset({"read", "read_metadata", "read_log"})


@dataclass(frozen=True)
class Rule:
    action: str
    decisions: dict[str, Decision]
    mfa_recent: bool
    requires_reason: bool
    # An obligation the platform can't discharge yet (engagement-team notification, ADR-024):
    # such actions deny until it can.
    notify: bool
    # SPEC-025 (TASK-045): client data; see `independence` in `authorise`.
    independence: bool = False

    @property
    def reads(self) -> bool:
        return self.action.split(".", 1)[1] in READ_VERBS


def _decision(action: str, role: str, value: str) -> Decision:
    if value in _SIMPLE:
        return cast(Decision, value)
    if _FIRM_SETTING.fullmatch(value):
        return "firm_setting"
    raise ValueError(f"permission matrix: {action}.{role}: unknown decision {value!r}")


def _rule(action: str, entries: dict[str, str]) -> Rule:
    if not _ACTION.fullmatch(action):
        raise ValueError(f"permission matrix: action {action!r} must look like 'entity.verb'")
    decisions: dict[str, Decision] = {}
    modifiers: set[str] = set()
    for key, value in entries.items():
        if key in _MODIFIERS:
            if value != _MODIFIERS[key]:
                raise ValueError(f"permission matrix: {action}.{key}: unknown value {value!r}")
            modifiers.add(key)
        elif key in ROLES:
            decisions[key] = _decision(action, key, value)
        else:
            raise ValueError(f"permission matrix: {action}: unknown role {key!r}")
    return Rule(
        action,
        decisions,
        mfa_recent="mfa_recent" in modifiers,
        requires_reason="requires" in modifiers,
        notify="notify" in modifiers,
        independence="independence" in modifiers,
    )


RULES: dict[str, Rule] = {action: _rule(action, entries) for action, entries in ACTIONS.items()}
