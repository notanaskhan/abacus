"""Firm policy overrides (F-03-T24; chapter 03 §4.4; DEC-127). PROTECTED.

The matrix is the ceiling: a firm may make a cell stricter, never looser. The only override is
`deny`, which narrows every decision and widens none; `apply_override` keeps the ceiling for
anything else, so a row that slipped past the writer and the CHECK still can't grant. The
property test (`tests/unit/identity/test_policy_overrides.py`) drives these functions.

Overrides apply in `authorise`, not in `visible()`, so the writer refuses them on reads: a list
filtered without the override would show what `authorise` denies. Platform roles (`system`,
`platform_support*`) are the platform's, not the firm's, and can't be overridden; nor can the
setting that sets overrides (`firm.manage_settings`), which would lock the firm out of undoing
one.
"""

from __future__ import annotations

from typing import Final

from abacus.modules.identity.authz.matrix import RULES, Decision

OVERRIDE_DECISIONS: Final = frozenset({"deny"})
PLATFORM_ROLES: Final = frozenset({"system", "platform_support", "platform_support_content"})
_SELF: Final = "firm.manage_settings"


def narrows(ceiling: Decision | None, override: str) -> bool:
    """Whether `override` is at least as strict as `ceiling` (no cell is already deny)."""
    return override in OVERRIDE_DECISIONS and ceiling is not None


def apply_override(ceiling: Decision | None, override: str | None) -> Decision | None:
    """The cell's decision under a firm override: the override when it narrows, else the
    ceiling."""
    if override is None or not narrows(ceiling, override):
        return ceiling
    return "deny"


def refusal(action: str, role: str, decision: str) -> str | None:
    """Why the writer refuses this override, or None when it's accepted."""
    rule = RULES.get(action)
    if rule is None:
        return "unknown_action"
    if rule.reads:
        return "read_action"
    if action == _SELF:
        return "locks_out"
    if role in PLATFORM_ROLES:
        return "platform_role"
    if role not in rule.decisions:
        return "no_cell"
    if not narrows(rule.decisions[role], decision):
        return "widens"
    return None
