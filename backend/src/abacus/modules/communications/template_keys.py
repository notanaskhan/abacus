"""R-01's six firm-editable email template keys, registered once at import (R-01-T19; R-01 §4.7;
POR-20 "Registry labels").

These are registrations, not content: the key, who it goes to, the whitelisted variables, its one
call-to-action target, the screens that use it and the list's labels. The words of each email are
the firm's, in the database (AGENTS 16), loaded through the editor or the import; until a key has
a published version every send of it fails closed (`template_missing`).
"""

from __future__ import annotations

from typing import Final

from abacus.modules.communications.template_registry import (
    EmailTemplateRegistration,
    register_email_template,
)

_GENERAL: Final = (
    "client_first_name",
    "firm_name",
    "work_item",
    "open_items",
    "due_date",
    "portal_link",
    "staff_name",
)

INVITATION: Final = register_email_template(
    "invitation",
    ("client", "third_party"),
    (
        "client_first_name",
        "firm_name",
        "inviter_name",
        "organisation_name",
        "scope_summary",
        "portal_link",
    ),
    ("portal_home",),
    ("CLI-04",),
    firm_editable=True,
    name="Invitation",
    used_by_label="CLI-04 invites, prospect intake",
    designed=True,
)
REMINDER: Final = register_email_template(
    "reminder",
    ("client", "third_party"),
    _GENERAL,
    ("documents",),
    (),
    firm_editable=True,
    name="Reminder",
    used_by_label="Binders, close requests, PBC",
    designed=True,
)
SIGNATURE_REQUEST: Final = register_email_template(
    "signature_request",
    ("client",),
    ("client_first_name", "firm_name", "document_title", "due_date", "portal_link"),
    ("sign",),
    ("SIG-01",),
    firm_editable=True,
    name="Signature request",
    used_by_label="SIG-02 envelopes",
    designed=True,
)
DELIVERABLE_READY: Final = register_email_template(
    "deliverable_ready",
    ("client",),
    ("client_first_name", "firm_name", "deliverable_title", "portal_link"),
    ("deliverables",),
    ("TXP-12",),
    firm_editable=True,
    name="Deliverable ready",
    used_by_label="Returns, K-1s, statements, reports",
    designed=True,
)
CONFIRMATION_REQUEST: Final = register_email_template(
    "confirmation_request",
    ("respondent",),
    ("respondent_org", "firm_name", "organisation_name", "due_date", "portal_link"),
    ("confirm",),
    ("AUD-14",),
    firm_editable=True,
    name="Confirmation request",
    used_by_label="AUD-14 · single-use link, no portal",
    designed=True,
)
RECONNECT_REQUEST: Final = register_email_template(
    "reconnect_request",
    ("client",),
    ("client_first_name", "firm_name", "portal_link", "connection_name"),
    ("connections",),
    ("CLS-11",),
    firm_editable=True,
    name="Reconnect request",
    used_by_label="CLS-11 · expired connections",
    designed=True,
)
# N-02-T24 (N-02 §4.8, DF-11): the signing emails beside `signature_request`. Registrations only:
# each firm's words are imported or written in the editor (database content); until a version is
# published every send fails closed (`template_missing`). No amount is a variable, so a reminder
# can never carry one.
SIGNATURE_REMINDER: Final = register_email_template(
    "signature_reminder",
    ("client",),
    ("client_first_name", "firm_name", "document_title", "due_date", "portal_link"),
    ("sign",),
    ("SIG-01",),
    firm_editable=True,
    name="Signature reminder",
    used_by_label="SIG-01 reminders",
)
SIGNED_COPY: Final = register_email_template(
    "signed_copy",
    ("client",),
    ("client_first_name", "firm_name", "document_title", "portal_link"),
    ("sign",),
    ("POR-06",),
    firm_editable=True,
    name="Signed copy",
    used_by_label="POR-06 · the ESIGN copy of a completed envelope",
)
REP_LETTER_SIGN_TODAY: Final = register_email_template(
    "rep_letter_sign_today",
    ("client",),
    ("client_first_name", "firm_name", "document_title", "portal_link"),
    ("sign",),
    ("POR-06",),
    firm_editable=True,
    name="Representation letter: sign today",
    used_by_label="POR-06 · a letter dated today",
)
PAPER_FORM_FOLLOWS: Final = register_email_template(
    "paper_form_follows",
    ("client",),
    ("client_first_name", "firm_name", "document_title", "staff_name"),
    (),
    ("POR-06",),
    firm_editable=True,
    name="Paper form follows",
    used_by_label="POR-06 · identity check failed (DF-11)",
)
SIGNING: Final[tuple[EmailTemplateRegistration, ...]] = (
    SIGNATURE_REMINDER,
    SIGNED_COPY,
    REP_LETTER_SIGN_TODAY,
    PAPER_FORM_FOLLOWS,
)
DESIGNED: Final[tuple[EmailTemplateRegistration, ...]] = (
    INVITATION,
    REMINDER,
    SIGNATURE_REQUEST,
    DELIVERABLE_READY,
    CONFIRMATION_REQUEST,
    RECONNECT_REQUEST,
)
