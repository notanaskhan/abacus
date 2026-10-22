"""The permission matrix as typed rules, validated at import (ADR-027). PROTECTED.

Source: `docs/architecture/permission-matrix/<module>.yaml`, rendered into `_matrix.py` by
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
# The firm settings a person's cell may name (F-03-T24; DEC-38). Migration 0081's CHECK on
# `firm_setting_values.key` lists the same keys. An agent's only one is the autonomy policy
# (SPEC-027), which the firm sets through its autonomy level, not here.
FIRM_SETTING_KEYS: frozenset[str] = frozenset(
    {
        "seniors_can_accept",
        "seniors_can_create",
        "seniors_can_publish",
        "client_service_can_publish",
        "staff_can_accept_evidence",
    }
)
AGENT_SETTING = "autonomy_policy"
_MODIFIERS = {
    "mfa_recent": "required",
    "requires": "reason",
    "notify": "engagement_team",
    # SPEC-025 (TASK-045): a staff member's engagement role counts only once they've confirmed
    # their independence for that engagement.
    "independence": "required",
}
# Conditions on an action (chapter 03 §4.4; F-03-T24), evaluated in `authorise` layer 4 against
# facts the owners register; a condition without its facts denies (fail closed).
LEVELS: frozenset[str] = frozenset({"partner", "manager", "senior", "staff", "seasonal", "admin"})
FUNCTIONS: frozenset[str] = frozenset(
    {
        "preparer",
        "first_level_reviewer",
        "detail_reviewer",
        "manager_reviewer",
        "signer",
        "eqr",
        "close_preparer",
        "close_reviewer",
        "project_lead",
        "specialist",
    }
)
GATES: tuple[str, ...] = tuple(f"G{n}" for n in range(1, 10))
CONDITION_KEYS: frozenset[str] = frozenset(
    {"level_in", "function_in", "not_offshore", "attest_client", "gates_met", "scope_only"}
)
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
    # F-03-T24 conditions (§4.4); empty or None when the action has none.
    level_in: frozenset[str] = frozenset()
    function_in: frozenset[str] = frozenset()
    not_offshore: bool = False
    attest_client: Literal["deny", "only"] | None = None
    gates_met: tuple[str, ...] = ()
    scope_only: bool = False
    # The firm setting each `firm_setting(<name>)` role decision names.
    firm_settings: tuple[tuple[str, str], ...] = ()

    @property
    def reads(self) -> bool:
        return self.action.split(".", 1)[1] in READ_VERBS


def _decision(action: str, role: str, value: str) -> Decision:
    if value in _SIMPLE:
        return cast(Decision, value)
    if _FIRM_SETTING.fullmatch(value):
        return "firm_setting"
    raise ValueError(f"permission matrix: {action}.{role}: unknown decision {value!r}")


def _listed(
    action: str, key: str, value: str, allowed: frozenset[str] | tuple[str, ...]
) -> list[str]:
    items = [v.strip() for v in value.split(",")]
    if not items or any(v not in allowed for v in items):
        raise ValueError(f"permission matrix: {action}.{key}: unknown value {value!r}")
    return items


def _rule(action: str, entries: dict[str, str]) -> Rule:
    if not _ACTION.fullmatch(action):
        raise ValueError(f"permission matrix: action {action!r} must look like 'entity.verb'")
    decisions: dict[str, Decision] = {}
    modifiers: set[str] = set()
    level_in: frozenset[str] = frozenset()
    function_in: frozenset[str] = frozenset()
    gates_met: tuple[str, ...] = ()
    attest_client: Literal["deny", "only"] | None = None
    flags: set[str] = set()
    settings: list[tuple[str, str]] = []
    for key, value in entries.items():
        if key == "level_in":
            level_in = frozenset(_listed(action, key, value, LEVELS))
        elif key == "function_in":
            function_in = frozenset(_listed(action, key, value, FUNCTIONS))
        elif key == "gates_met":
            gates_met = tuple(_listed(action, key, value, GATES))
        elif key == "attest_client":
            if value not in ("deny", "only"):
                raise ValueError(f"permission matrix: {action}.{key}: unknown value {value!r}")
            attest_client = value
        elif key in ("not_offshore", "scope_only"):
            if value != "required":
                raise ValueError(f"permission matrix: {action}.{key}: unknown value {value!r}")
            flags.add(key)
        elif key in _MODIFIERS:
            if value != _MODIFIERS[key]:
                raise ValueError(f"permission matrix: {action}.{key}: unknown value {value!r}")
            modifiers.add(key)
        elif key in ROLES:
            decisions[key] = _decision(action, key, value)
            setting = _FIRM_SETTING.fullmatch(value)
            if setting is not None:
                name = setting.group(1)
                known = {AGENT_SETTING} if key == "agent" else FIRM_SETTING_KEYS
                if name not in known:
                    raise ValueError(
                        f"permission matrix: {action}.{key}: unregistered firm setting {name!r}"
                    )
                settings.append((key, name))
        else:
            raise ValueError(f"permission matrix: {action}: unknown role {key!r}")
    return Rule(
        action,
        decisions,
        mfa_recent="mfa_recent" in modifiers,
        requires_reason="requires" in modifiers,
        notify="notify" in modifiers,
        independence="independence" in modifiers,
        level_in=level_in,
        function_in=function_in,
        not_offshore="not_offshore" in flags,
        attest_client=attest_client,
        gates_met=gates_met,
        scope_only="scope_only" in flags,
        firm_settings=tuple(settings),
    )


RULES: dict[str, Rule] = {action: _rule(action, entries) for action, entries in ACTIONS.items()}
