"""C16 v1.1, the email half: the firm-editable template slot and `send_templated` (R-01-T16;
SPEC-345; R-01 §4.7). Contract: `docs/contracts/email-templates.md`.

Firm-editable keys register here, once, at import time; their text is content and lives in the
database (P-01-T05's tables, widened by R-01-T19), loaded by an admin screen or the import
endpoint, never by code (AGENTS 16). A key declares its audience, the whitelisted variables it
may use, its call-to-action targets and the screens that use it. R-01-T19 registers the six keys
(`invitation`, `reminder`, `signature_request`, `deliverable_ready`, `confirmation_request`,
`reconnect_request`); P-06 registers `request_sent` and `request_returned` through the same slot.

Every variable carries a kind and a classification. The kinds are a closed list without an
amount, an account number or a TIN, so no registration can make an email carry one (R-01-T17's
consumer suite fails if that ever changes); nothing Restricted is ever a variable.

`send_templated` is the only way module code sends a firm template to a person outside the firm.
It refuses rather than sends: `template_missing` (no published version), `template_lint_failed`,
`firm_not_client_facing` (the client-mail gate before a firm's M10 flip; staff recipients are
unaffected) and `suppressed` (a bounce or complaint). A refusal records the message `blocked`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from abacus.kernel._flags import FOLLOW_UPS_SCHEDULED_SEND
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotImplementedYet
from abacus.kernel.flags import flag_enabled

TemplateAudience = Literal["client", "third_party", "respondent", "staff"]
CtaTarget = Literal[
    "portal_home", "documents", "request", "room", "sign", "deliverables", "confirm", "connections"
]
# What a variable's value is. A closed list: an amount, an account number or a TIN is not a kind.
VariableKind = Literal[
    "person_name",  # a first or full name the recipient already knows
    "organisation_name",  # the firm, the client, the respondent's organisation
    "title",  # a work item, document, deliverable or connection title in client wording
    "item_list",  # request titles in client wording, at most 10, then "and n more"
    "date",
    "secure_link",  # a 14-day secure link (P-08-T21), never a query string
    "summary",  # a scope summary in words ("2 entities, 2025 returns")
]
VariableClass = Literal["public", "internal", "confidential"]
SendRefusal = Literal[
    "template_missing", "template_lint_failed", "firm_not_client_facing", "suppressed"
]
# The lint (Story 7.2): each violation names its block, never the offending text.
LintCode = Literal[
    "amount",
    "tin_shape",
    "account_number",
    "attachment",
    "second_button",
    "unregistered_variable",
    "foreign_link",
    "platform_name",
]
FollowUpMode = Literal["draft_for_person", "send_on_schedule"]


@dataclass(frozen=True)
class TemplateVariable:
    name: str
    kind: VariableKind
    classification: VariableClass
    block: bool = False  # several lines (one per item); never in a subject


def _var(
    name: str, kind: VariableKind, cls: VariableClass, *, block: bool = False
) -> tuple[str, TemplateVariable]:
    return name, TemplateVariable(name, kind, cls, block)


# R-01 §4.7: the general variables, then the per-key ones.
GENERAL_VARIABLES: Final = (
    "client_first_name",
    "firm_name",
    "work_item",
    "open_items",
    "due_date",
    "portal_link",
    "staff_name",
)
VARIABLES: Final[Mapping[str, TemplateVariable]] = dict(
    [
        _var("client_first_name", "person_name", "confidential"),
        _var("firm_name", "organisation_name", "public"),
        _var("work_item", "title", "confidential"),
        _var("open_items", "item_list", "confidential", block=True),
        _var("due_date", "date", "internal"),
        _var("portal_link", "secure_link", "confidential"),
        _var("staff_name", "person_name", "internal"),
        _var("inviter_name", "person_name", "confidential"),
        _var("organisation_name", "organisation_name", "confidential"),
        _var("scope_summary", "summary", "confidential"),
        _var("document_title", "title", "confidential"),
        _var("deliverable_title", "title", "confidential"),
        _var("respondent_org", "organisation_name", "confidential"),
        _var("connection_name", "title", "confidential"),
    ]
)
_KEY: Final = re.compile(r"[a-z][a-z0-9_]{1,49}")
_SCREEN: Final = re.compile(r"[A-Z]{2,4}-[0-9]{2}")


@dataclass(frozen=True)
class EmailTemplateRegistration:
    key: str
    audience: tuple[TemplateAudience, ...]
    variables: tuple[str, ...]
    cta_targets: tuple[CtaTarget, ...]
    used_by: tuple[str, ...]  # screen ids ("CLI-04", "SIG-01")
    firm_editable: bool


class TemplateRegistrationInvalid(ValueError):
    """A registration the slot refuses."""


_REGISTERED: dict[str, EmailTemplateRegistration] = {}


def register_email_template(
    key: str,
    audience: tuple[TemplateAudience, ...],
    variables: tuple[str, ...],
    cta_targets: tuple[CtaTarget, ...],
    used_by: tuple[str, ...],
    *,
    firm_editable: bool,
) -> EmailTemplateRegistration:
    """Register a template key, once, at import time: whitelisted variables only, at most one
    call-to-action target per audience (an email still renders one button), screens by id."""
    if not _KEY.fullmatch(key):
        raise TemplateRegistrationInvalid(f"{key!r} is not a template key")
    if key in _REGISTERED:
        raise TemplateRegistrationInvalid(f"{key} is registered twice")
    if not audience or len(set(audience)) != len(audience):
        raise TemplateRegistrationInvalid(f"{key}: name each audience once")
    unknown = [v for v in variables if v not in VARIABLES]
    if unknown:
        raise TemplateRegistrationInvalid(f"{key}: {unknown} are not whitelisted variables")
    if len(set(cta_targets)) != len(cta_targets) or len(cta_targets) > len(audience):
        raise TemplateRegistrationInvalid(f"{key}: one call-to-action target per audience")
    if not all(_SCREEN.fullmatch(s) for s in used_by):
        raise TemplateRegistrationInvalid(f"{key}: used_by names screen ids")
    if firm_editable and "staff" in audience:
        raise TemplateRegistrationInvalid(f"{key}: staff templates are platform-locked")
    registration = EmailTemplateRegistration(
        key, tuple(audience), tuple(variables), tuple(cta_targets), tuple(used_by), firm_editable
    )
    _REGISTERED[key] = registration
    return registration


def registered_templates() -> tuple[EmailTemplateRegistration, ...]:
    return tuple(_REGISTERED[k] for k in sorted(_REGISTERED))


@dataclass(frozen=True)
class RecipientRef:
    kind: Literal["contact", "third_party", "respondent", "user"]
    id: UUID


@dataclass(frozen=True)
class SendActor:
    """Who sends: a person, or the system for a scheduled reminder (DEC-74, INV-5). An agent
    never sends (ADR-005)."""

    kind: Literal["human", "system"]
    user_id: UUID | None


@dataclass(frozen=True)
class SendOutcome:
    message_id: UUID
    status: Literal["queued", "blocked"]
    blocked_reason: SendRefusal | None


async def send_templated(
    tenant: TenantContext,
    key: str,
    recipient: RecipientRef,
    variables: Mapping[str, str],
    *,
    actor: SendActor,
    idempotency_key: str,
) -> SendOutcome:
    """Render the key's published version for one recipient and queue it, or record it
    `blocked` with a `SendRefusal`. R-01-T19 builds it; until then it refuses to run."""
    raise NotImplementedYet


async def scheduled_send_enabled(tenant: TenantContext) -> bool:
    """Whether a `send_on_schedule` policy may send by itself for this firm (DEC-74). Off, every
    reminder is a draft a person sends, whatever the policy's mode."""
    return await flag_enabled(tenant, FOLLOW_UPS_SCHEDULED_SEND)
