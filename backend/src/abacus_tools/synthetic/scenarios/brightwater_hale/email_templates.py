"""The `email_templates` slice (R-01-T22; POR-20 "Seeded template content"; ADM-10 a): Brightwater
Hale's six email templates, as events the loader replays through communications' editor service
(save a draft, publish), signed in as Grace Holloway, the firm admin. Synthetic and Brightwater
Hale's own: this is the one place their words live (AGENTS 16; R-01-T22's acceptance: no
template text in a migration, a constant or a fixture outside the scenario package).

Versions as POR-20's figures give them ("6 of 6 published · 1 with draft changes"): Invitation v3,
Reminder v3 published and a v4 draft, Signature request v2, Deliverable ready v2, Confirmation
request v1, Reconnect request v1. Only the version each artboard renders has copy in the handoff,
so each earlier version is published with that same copy (DEC-451): the history is a count, not
invented wording. The Reminder's v4 draft is the copy POR-20 a to d render.

Each email's words are POR-20's, verbatim. Where a word is one of the key's whitelisted
variables it is written as the variable; the firm's own words (its legal name, its phone line)
are literal, as a firm's template would have them. Where the handoff's sentence names something
the key has no variable for (the Reminder's count, the plan an invitation is about, a contact
named on a key without `staff_name`, the confirmation's date and reference, the close month), the
words stay literal so the artboards render verbatim, and the gap is recorded (DEC-451): those
rows are demo content until the whitelist grows. The address line of the footer comes from
branding (P-08) and is not part of a template.

Not seeded here, because their tables arrive with later tasks: the portal settings draft
(R-01-T26), the follow-up policy (T24) and the sending domain verified on the sink (T27).

Opt-in (`--slice email_templates`); `build()` keeps its default, so SCENARIO_HASH is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "email_templates"
EDITOR_FLAG: Final = "portal.settings_editor"
GRACE: Final = "GH"
_FOOTER: Final = (
    "You're receiving this because you're a client of {firm_name}. We never include account "
    "numbers or tax amounts in email."
)


@dataclass(frozen=True)
class SeededTemplate:
    key: str
    published: int  # how many versions are published
    draft: bool  # whether the last entry is left as a draft (Reminder v4)
    subject: str
    preheader: str
    blocks: tuple[tuple[str, str, str], ...]  # (id, kind, text)
    cta_label: str
    cta_target: str

    def content(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "preheader": self.preheader,
            "blocks": [{"id": i, "kind": k, "text": t} for i, k, t in self.blocks],
            "cta_label": self.cta_label,
            "cta_target": self.cta_target,
        }


TEMPLATES: Final = (
    SeededTemplate(
        "reminder",
        3,
        True,
        "2 items still needed for your {work_item}",
        "",
        (
            ("headline", "heading", "We still need 2 items"),
            (
                "intro",
                "paragraph",
                "Hi {client_first_name}, we're working on your {work_item}. To keep it on "
                "track, please upload:",
            ),
            ("items", "item_list", "{open_items}"),
            ("drop", "paragraph", "Drop the files in your portal and they'll be sorted for you."),
            ("questions", "note", "Questions? Message {staff_name} in your portal."),
            ("footer", "footer", _FOOTER),
        ),
        "Open your portal",
        "documents",
    ),
    SeededTemplate(
        "invitation",
        3,
        False,
        "{firm_name} invited you to upload documents",
        "",
        (
            ("headline", "heading", "You've been asked for {scope_summary}"),
            (
                "intro",
                "paragraph",
                "Hi {client_first_name}, Brightwater Hale LLP is auditing the Northwind Robotics "
                "401(k) Plan and has asked {organisation_name} for {scope_summary}. Sign in to "
                "upload them securely.",
            ),
            ("questions", "note", "Questions? Message {inviter_name} in your request room."),
            (
                "footer",
                "footer",
                "You're receiving this because {firm_name} asked {organisation_name} for "
                "documents. We never include account numbers or tax amounts in email. This "
                "link expires in 14 days.",
            ),
        ),
        "Open requests",
        "portal_home",
    ),
    SeededTemplate(
        "signature_request",
        2,
        False,
        "Please sign: {document_title}",
        "",
        (
            ("headline", "heading", "Ready for your signature"),
            (
                "intro",
                "paragraph",
                "Hi {client_first_name}, please review and sign your {document_title}.",
            ),
            ("due", "paragraph", "Due {due_date}."),
            ("questions", "note", "Questions? Message Daniel Reyes in your portal."),
            ("footer", "footer", _FOOTER),
        ),
        "Review and sign",
        "sign",
    ),
    SeededTemplate(
        "deliverable_ready",
        2,
        False,
        "Your {deliverable_title} is ready",
        "",
        (
            ("headline", "heading", "Ready to view"),
            (
                "intro",
                "paragraph",
                "Hi {client_first_name}, your {deliverable_title} is in your portal. Sign in "
                "to view or download it.",
            ),
            ("questions", "note", "Questions? Message Olivia Brandt in your portal."),
            ("footer", "footer", _FOOTER),
        ),
        "View your K-1",
        "deliverables",
    ),
    SeededTemplate(
        "confirmation_request",
        1,
        False,
        "Confirmation request — balance at June 30, 2026 (reference C2)",
        "",
        (
            ("headline", "heading", "Please confirm a balance"),
            (
                "intro",
                "paragraph",
                "Hi Rachel, as auditors of {organisation_name}, we're asking {respondent_org} to "
                "confirm the balance it owed Granite Peak at June 30, 2026. Please respond "
                "directly to us using the secure link.",
            ),
            (
                "genuine",
                "note",
                "This link works once and expires on {due_date}. To check it's genuine, call "
                "Brightwater Hale using the number on our website.",
            ),
            (
                "footer",
                "footer",
                "You're receiving this because {organisation_name} authorized us to confirm a "
                "balance with you. We never include account numbers or tax amounts in email.",
            ),
        ),
        "Respond securely",
        "confirm",
    ),
    SeededTemplate(
        "reconnect_request",
        1,
        False,
        "Please reconnect {connection_name} for your monthly close",
        "",
        (
            ("headline", "heading", "Reconnect {connection_name}"),
            (
                "intro",
                "paragraph",
                "Hi {client_first_name}, {connection_name} asks you to sign in again every 90 "
                "days, so new card transactions aren't reaching us for your August 2026 close. "
                "Reconnecting in your portal restarts the feed.",
            ),
            ("questions", "note", "Questions? Message Raj Malhotra in your portal."),
            ("footer", "footer", _FOOTER),
        ),
        "Reconnect",
        "connections",
    ),
)


@register_slice(SLICE)
def email_template_events() -> list[Event]:
    events = [
        Event(
            f"flag:{EDITOR_FLAG}",
            SETUP_AT,
            "platform.flag_set",
            "system",
            SLICE,
            {"flag": EDITOR_FLAG},
        )
    ]
    for template in TEMPLATES:
        for version in range(1, template.published + 1):
            events.append(
                Event(
                    f"email-template:{template.key}:v{version}",
                    SETUP_AT,
                    "communications.email_template_published",
                    GRACE,
                    SLICE,
                    {"key": template.key, "content": template.content()},
                )
            )
        if template.draft:
            events.append(
                Event(
                    f"email-template:{template.key}:draft",
                    SETUP_AT,
                    "communications.email_template_draft_saved",
                    GRACE,
                    SLICE,
                    {"key": template.key, "content": template.content()},
                )
            )
    return events
