"""The §7216 consent template kind (T-01-T17; T-01 §3.1 Story 1.1; DF-16; conflict C-03; SPEC-501
AC-28 to AC-31).

A consent's recipient block is never wording a firm types: it is the line the provider-terms
register gives on the day the document renders ("Amazon Web Services (Bedrock) · model inference
· US"), and the register's material-terms hash is stored on the consent (`provider_terms_version`). The
template places the `consent.recipients` variable exactly once where the block prints, and no
fixed text in it may name a model provider or sub-processor as a recipient: "Anthropic" in a
template is refused at import (only the register's eligible route ever carries client data,
ADR-113).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Final

from abacus.kernel.provider_terms import covering
from abacus.modules.reporting.contract import CONSENT_RECIPIENTS_KEY
from abacus.modules.reporting.render.head import RenderRefused

ROUTE: Final = "bedrock"  # the only eligible route (ADR-113)
# What the route does for a consent's purposes: the register lists the provider and region.
_SERVICE: Final = "model inference"
_COUNTRY: Final = {"us": "US"}
# Parties a consent's fixed text may never name as a recipient: model providers and the
# register's provider (whose line is rendered from the register, never typed). Word-bounded and
# case-insensitive.
NAMED_PARTIES: Final = (
    "Anthropic",
    "Claude",
    "OpenAI",
    "ChatGPT",
    "GPT-4",
    "Google",
    "Gemini",
    "Microsoft",
    "Azure",
    "Mistral",
    "Cohere",
    "Meta",
    "Llama",
    "Amazon Web Services",
    "AWS",
    "Bedrock",
)
_NAMED: Final = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in NAMED_PARTIES) + r")\b", re.IGNORECASE
)


class RecipientsUnavailable(RenderRefused):
    """No register entry covers the route on the render's day: a consent cannot name recipients
    it may not disclose to, so it does not render."""

    def __init__(self) -> None:
        super().__init__("recipients_unavailable")


@dataclass(frozen=True)
class Recipients:
    line: str
    # The covering entry's material-terms hash: what the consent gate compares a signed consent
    # with (a material change means re-consent; organisations.consent_gate).
    provider_terms_version: str


def names_a_party(text: str) -> bool:
    return _NAMED.search(text) is not None


def _country(region: str) -> str:
    return _COUNTRY.get(region.split("-", 1)[0], region.upper())


def recipients(on: date) -> Recipients:
    """The recipient line the register gives for `on`, with the register's version (DF-16)."""
    entry = covering(ROUTE, on)
    if entry is None:
        raise RecipientsUnavailable
    if not entry.material:
        raise RecipientsUnavailable
    line = f"{entry.provider} ({ROUTE.title()}) · {_SERVICE} · {_country(entry.region)}"
    return Recipients(line, entry.material)


def recipient_values(on: date) -> dict[str, str]:
    """The consent kind's register-sourced variables, merged into the values a render uses."""
    return {CONSENT_RECIPIENTS_KEY: recipients(on).line}
