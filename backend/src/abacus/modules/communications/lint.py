"""The template text lint (R-01 Story 7.2), the part publish needs (R-01-T19).

Each finding names its rule and where it is (a block id, or `subject`, `preheader`,
`cta_label`), never the text. T19 runs the rules a published version must never break: a
variable the key does not register (or a block variable outside an item list), an amount, a
TIN-shaped number, an account number, the platform's name, and a link or domain in the text or
`{portal_link}` anywhere but the button (security review M3). R-01-T23 adds attachments, a
second button and the scope guards' banned words, and runs the lint at preview,
test send and import too. Deterministic: the same content gives the same findings in the same
order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from abacus.modules.communications.render import TemplateContent, used_variables
from abacus.modules.communications.template_registry import (
    ACCOUNT_SHAPE,
    AMOUNT_SHAPE,
    TIN_SHAPE,
    VARIABLES,
    EmailTemplateRegistration,
    LintCode,
    normalised,
)
from abacus.modules.communications.templates import TemplateInvalid

_PLATFORM: Final = re.compile(r"accrued", re.IGNORECASE)
_PLACEHOLDER: Final = re.compile(r"\{[a-z][a-z0-9_]{0,39}\}")
# Security review M3: firm text carries no address of its own; the one link is the button's.
_FOREIGN_LINK: Final = re.compile(
    r"(?i)\b(?:https?://|www\.)|[a-z0-9](?:[a-z0-9-]{0,62})(?:\.[a-z0-9-]{1,63})*\.[a-z]{2,24}\b"
)


@dataclass(frozen=True)
class LintFinding:
    code: LintCode
    where: str  # a block id, or subject / preheader / cta_label

    def fact(self) -> str:
        return f"{self.code}:{self.where}"


def _text_findings(where: str, text: str) -> list[LintFinding]:
    bare = normalised(_PLACEHOLDER.sub(" ", text))
    found: list[LintFinding] = []
    if TIN_SHAPE.search(bare):
        found.append(LintFinding("tin_shape", where))
    if ACCOUNT_SHAPE.search(bare):
        found.append(LintFinding("account_number", where))
    if AMOUNT_SHAPE.search(TIN_SHAPE.sub(" ", bare)):
        found.append(LintFinding("amount", where))
    if _PLATFORM.search(bare):
        found.append(LintFinding("platform_name", where))
    if _FOREIGN_LINK.search(bare) or "{portal_link}" in text:
        found.append(LintFinding("foreign_link", where))  # the link goes only in the button
    return found


def lint_template(
    content: TemplateContent, registration: EmailTemplateRegistration
) -> list[LintFinding]:
    allowed = set(registration.variables)
    found: list[LintFinding] = []
    parts: list[tuple[str, str, bool]] = [
        ("subject", content.subject, False),
        ("preheader", content.preheader, False),
    ]
    if content.cta_label is not None:
        parts.append(("cta_label", content.cta_label, False))
    parts.extend((b.id, b.text, b.kind == "item_list") for b in content.blocks)
    for where, text, takes_blocks in parts:
        try:
            names = used_variables(text)
        except TemplateInvalid:
            found.append(LintFinding("unregistered_variable", where))
            names = []
        for name in names:
            variable = VARIABLES.get(name)
            if name not in allowed or variable is None or (variable.block and not takes_blocks):
                found.append(LintFinding("unregistered_variable", where))
                break
        found.extend(_text_findings(where, text))
    return found
