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

The kinds keep template *text* safe; the *values* are another matter. A `title` or an
`item_list` is client-written (a document named "W-2 912-34-5678 $84,210.pdf"), so
`lint_values` runs the amount, TIN-shape and account-number rules on the filled values, at
preview and at send, and a finding refuses the send (`template_lint_failed`, naming the code and
the variable, never the value). Nothing is masked into a near-miss: fail closed (DEC-379).

`send_templated` is the only way module code sends a firm template to a person outside the firm.
It takes the caller's `AuthContext` (or the explicit `SystemSendContext` of a scheduled
reminder) and the engagement the message is about, and authorises inside: `message.send` on the
engagement for a person (independence, G2 on attest clients, walls), then the outbound scope
check (`check_scope`, ADR-065). It refuses rather than sends: `template_missing` (no published
version), `template_lint_failed` (text or values), `out_of_scope` (names another client, entity,
account or amount), `firm_not_client_facing` (the client-mail gate before a firm's M10 flip;
staff recipients are unaffected) and `suppressed` (a bounce or complaint). A refusal records the
message `blocked`; an authorisation failure raises as every `authorise` does.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from abacus.kernel._flags import FOLLOW_UPS_SCHEDULED_SEND
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AuthContext

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
    "template_missing",
    "template_lint_failed",
    "out_of_scope",
    "firm_not_client_facing",
    "suppressed",
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
    "banned_word",  # R-01-T23: the glossary's client-email bans and scope-guards' banned terms
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
    name: str = ""  # the list's label ("Signature request"); defaults to the key in words
    used_by_label: str = ""  # "Used by …" ("SIG-02 envelopes")
    designed: bool = False  # one of R-01's designed six: listed first (POR-20 a)


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
    name: str | None = None,
    used_by_label: str = "",
    designed: bool = False,
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
    label = name if name is not None else key.replace("_", " ").capitalize()
    if not 1 <= len(label) <= 60 or len(used_by_label) > 120:
        raise TemplateRegistrationInvalid(f"{key}: name and used-by label are short labels")
    registration = EmailTemplateRegistration(
        key,
        tuple(audience),
        tuple(variables),
        tuple(cta_targets),
        tuple(used_by),
        firm_editable,
        label,
        used_by_label,
        designed,
    )
    _REGISTERED[key] = registration
    return registration


def registered_templates() -> tuple[EmailTemplateRegistration, ...]:
    return tuple(_REGISTERED[k] for k in sorted(_REGISTERED))


def registration_of(key: str) -> EmailTemplateRegistration | None:
    return _REGISTERED.get(key)


@dataclass(frozen=True)
class RecipientRef:
    kind: Literal["contact", "third_party", "respondent", "user"]
    id: UUID


@dataclass(frozen=True)
class SendScope:
    """What the message is about: the engagement `message.send` and the scope check run on,
    and the request it concerns, if one."""

    engagement_id: UUID
    request_item_id: UUID | None = None


@dataclass(frozen=True)
class SystemSendContext:
    """The only non-person sender: a scheduled reminder under a `send_on_schedule` policy while
    `follow_ups.scheduled_send` is on (DEC-74). Only the `reminder` key, only its published
    version, attributed to that version's publisher (INV-5). An agent never sends (ADR-005)."""

    tenant: TenantContext
    reason: Literal["scheduled_follow_up"]
    policy_version: int


@dataclass(frozen=True)
class SendOutcome:
    message_id: UUID
    status: Literal["queued", "blocked"]
    blocked_reason: SendRefusal | None


async def send_templated(
    ctx: AuthContext | SystemSendContext,
    key: str,
    recipient: RecipientRef,
    variables: Mapping[str, str],
    *,
    scope: SendScope,
    idempotency_key: str,
) -> SendOutcome:
    """Authorise, render the key's published version for one recipient and queue it, or record
    it `blocked` with a `SendRefusal`. A person: `authorise(ctx, "message.send", engagement)`
    first, then `lint_values`, then the rendered text through `check_scope`. The system: the
    flag, the `reminder` key and a version the firm published, then the same checks (R-01-T19;
    the policy's mode joins with R-01-T24, the client-mail gate with R-01-T27)."""
    # Imported here: `template_send` imports this module.
    from abacus.modules.communications import template_send

    return await template_send.send(
        ctx, key, recipient, variables, scope=scope, idempotency_key=idempotency_key
    )


# --- the value lint (DEC-379): client-written values never carry these shapes ------------------

_AMOUNT_VALUE: Final = re.compile(
    r"[$€£]\s?\d|\b\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b|\b\d+\.\d{2}\b"
    r"|(?i:\b(?:usd|us\$)\s?\d|\d(?:[\d,]*\d)?(?:\.\d+)?\s?(?:usd|dollars?)\b)"
)
# Security review L2: a TIN separated by spaces or dots as well as dashes, or not at all.
_TIN_VALUE: Final = re.compile(
    r"\b\d{3}[\s.\-]?\d{2}[\s.\-]?\d{4}\b|\b\d{2}[\s.\-]\d{7}\b|(?<!\d)\d{9}(?!\d)"
)
_ACCOUNT_VALUE: Final = re.compile(r"(?:••|\*{2,}|[xX]{2,}|#)\s?\d{4}\b|(?<!\d)\d{10,}(?!\d)")
# The same shapes for the template text lint (`lint.py`).
AMOUNT_SHAPE: Final = _AMOUNT_VALUE
TIN_SHAPE: Final = _TIN_VALUE
ACCOUNT_SHAPE: Final = _ACCOUNT_VALUE


@dataclass(frozen=True)
class ValueFinding:
    """A lint finding on a filled value: the rule and the variable, never the value."""

    code: LintCode
    variable: str


# The re-review: dash-like characters (hyphens, en and em dashes, minus, slashes) read as "-".
_DASHES: Final = str.maketrans(
    dict.fromkeys("\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u2043/\uff0f\\", "-")
)
# A link a mail client would make clickable: a scheme, `www.`, or an address (the re-review M).
_VALUE_LINK: Final = re.compile(r"(?i)\b(?:https?|ftp)://|\bwww\.|[^\s@]+@[^\s@]+\.[a-z]{2,}")


def folded(text: str) -> str:
    """NFKC-folded (full-width digits, ligatures), accents and other combining marks dropped,
    format characters (zero-width spaces and joiners, direction marks) removed."""
    decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text))
    kept = "".join(ch for ch in decomposed if unicodedata.category(ch) not in ("Cf", "Mn"))
    return unicodedata.normalize("NFC", kept)


def normalised(text: str) -> str:
    """What the shape rules read (security review L2 and its re-review): `folded`, with
    dash-like characters and slashes read as "-", so a value can't slip a TIN or the platform's
    name past a rule. Links are looked for in the `folded` text, where `://` is still itself."""
    return folded(text).translate(_DASHES)


def lint_values(values: Mapping[str, str]) -> list[ValueFinding]:
    """The amount, TIN-shape, account-number and link rules over every filled value (each line of
    a block variable); `portal_link` is the platform's secure link, never linted. Deterministic;
    run at preview (shown as findings) and at send (refused as `template_lint_failed`). A
    masked last four ("••4436") counts as an account number."""
    found: list[ValueFinding] = []
    for name in sorted(values):
        if name == "portal_link":
            continue
        value = normalised(values[name])
        if _TIN_VALUE.search(value):
            found.append(ValueFinding("tin_shape", name))
        if _ACCOUNT_VALUE.search(value):
            found.append(ValueFinding("account_number", name))
        if _AMOUNT_VALUE.search(_TIN_VALUE.sub(" ", value)):
            found.append(ValueFinding("amount", name))
        if _VALUE_LINK.search(folded(values[name])):
            found.append(ValueFinding("foreign_link", name))  # a bare domain is defanged instead
    return found


async def scheduled_send_enabled(tenant: TenantContext) -> bool:
    """Whether a `send_on_schedule` policy may send by itself for this firm (DEC-74). Off, every
    reminder is a draft a person sends, whatever the policy's mode."""
    return await flag_enabled(tenant, FOLLOW_UPS_SCHEDULED_SEND)
