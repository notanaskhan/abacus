"""The outbound message scope checker (ADR-065; SPEC-006 AC-8, AC-9, Q2, Q3). Deterministic code,
never a model (ADR-050).

An engagement's scope is its client and that client's entities, and the account codes, names and
amounts in the ledger snapshots behind its evidence. A draft violates scope if it names another
client or entity of the firm, an account of the firm's other ledgers, or an amount the
engagement's ledger doesn't hold. Violations carry a kind and an identifier, never message text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from abacus.modules.engagements.api import EngagementRef
from abacus.modules.evidence.api import engagement_snapshots
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger.api import firm_accounts, scope_facts
from abacus.modules.organisations.api import firm_names

MIN_NAME = 4
MIN_ACCOUNT_NAME = 8
SMALL_AMOUNT_CENTS = 100 * 100  # under 100: usually counts or days (Q2)
STOPLIST = frozenset({"inc", "llc", "ltd", "plc", "group", "holdings", "company", "corp"})
_AMOUNT = re.compile(
    r"(?<![\w.])(?P<sign>[$€£])?\s?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d{1,2})?\s?(?P<unit>[kKmM])?\b"
)


@dataclass(frozen=True)
class Violation:
    kind: str  # client | entity | account | amount | checker_error
    ref: str  # an identifier: a client or entity id, an account code, or cents


def _word(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)


def _named(text: str, name: str, minimum: int) -> bool:
    clean = name.strip()
    if len(clean) < minimum or clean.lower() in STOPLIST:
        return False
    return bool(_word(clean).search(text))


def amounts_in(text: str) -> list[tuple[int, int]]:
    """(cents, rounding in cents) for each amount written in the text. Rounding is 1 for an
    exact amount with cents, a whole unit for one without, and a thousand or a million for
    `k`/`m`. Bare years (1900 to 2100, no symbol, no decimals) are not amounts."""
    found: list[tuple[int, int]] = []
    for m in _AMOUNT.finditer(text):
        raw = m.group("num").replace(",", "") + (m.group("dec") or "")
        try:
            value = Decimal(raw)
        except InvalidOperation:
            continue
        unit = (m.group("unit") or "").lower()
        if not m.group("sign") and not m.group("dec") and not unit and 1900 <= value <= 2100:
            continue
        scale = {"k": 1_000, "m": 1_000_000}.get(unit, 1)
        cents = int((value * scale * 100).to_integral_value())
        rounding = scale * 100 if (unit or not m.group("dec")) else 1
        if cents >= SMALL_AMOUNT_CENTS:
            found.append((cents, rounding))
    return found


def _in_scope(cents: int, rounding: int, amounts: frozenset[int]) -> bool:
    if rounding == 1:
        return cents in amounts
    return any(abs(a - cents) * 2 <= rounding for a in amounts)


async def check_scope(ctx: AuthContext, ref: EngagementRef, text: str) -> list[Violation]:
    """What in `text` is outside the engagement's scope (for a caller that has authorised)."""
    violations: list[Violation] = []
    for name in await firm_names(ctx.tenant):
        if name.client_id != ref.client_id and _named(text, name.name, MIN_NAME):
            kind = "client" if name.id == name.client_id else "entity"
            violations.append(Violation(kind, str(name.id)))
    facts = await scope_facts(ctx.tenant, await engagement_snapshots(ctx.tenant, ref.id))
    for code, account in await firm_accounts(ctx.tenant):
        if code in facts.codes or account in facts.names:
            continue
        # Purely numeric codes are indistinguishable from amounts; they're checked as amounts.
        code_hit = not code.isdigit() and _named(text, code, MIN_NAME)
        if code_hit or _named(text, account, MIN_ACCOUNT_NAME):
            violations.append(Violation("account", code))
    for cents, rounding in amounts_in(text):
        if not _in_scope(cents, rounding, facts.amounts_cents):
            violations.append(Violation("amount", str(cents)))
    return list(dict.fromkeys(violations))
