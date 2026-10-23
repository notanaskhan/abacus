"""The portal's client codes (POR-02): the frontend's copy registry words each one (ADR P-36).

Kept apart from `contract.py` so the read model (`home.py`, `stages.py`) can use them without
importing the routes.
"""

from __future__ import annotations

from typing import Literal

# Identifier-only facts (ADR-139): codes, identifiers, counts and flags; never prose.
Facts = dict[str, str | int | bool]

# The kinds of to-do POR-02 shows (a to h). A kind whose source module has not shipped is hidden in
# production and rendered in fixture builds (P-08 §2.2). New kinds are additive.
TodoKind = Literal[
    "upload",
    "answer",
    "sign",
    "deliverables",
    "approve",
    "reconnect",
    "review_statements",
    "control_requests",
    "exceptions",
    "description_approved",
]
TodoState = Literal["open", "none", "overdue"]
# The screen a to-do or row opens: manifest IDs, never URLs.
PortalScreen = Literal[
    "POR-03",
    "POR-04",
    "POR-05",
    "POR-06",
    "POR-07",
    "POR-08",
    "POR-09",
    "POR-11",
    "POR-12",
    "POR-13",
    "POR-16",
    "POR-21",
]
# Client stage codes (P-08-T12 `stages.py` over C2), never firm statuses (POR-02 Copy table).
StageCode = Literal[
    "gather_documents",
    "prepare",
    "review",
    "sign_form_8879",
    "file",
    "requests",
    "reconcile",
    "statements",
    "planning",
    "fieldwork",
    "statements_review",
    "report",
    "scoping",
    "system_description",
    "testing",
    "exceptions",
]
StageState = Literal["done", "current", "upcoming"]
PillCode = Literal[
    "getting_started",
    "preparing_return",
    "reviewing_return",
    "reconciling_accounts",
    "filed_and_accepted",
    "finishing_audit",
    "testing_under_way",
]
PillVariant = Literal["state", "success", "neutral"]
NoteCode = Literal["waiting_on_k1", "waiting_on_your_k1"]
# Client-facing team roles (OQ-5: the day-to-day contact is derived per work-item kind).
TeamRoleCode = Literal[
    "partner_signs_return",
    "partner",
    "engagement_partner",
    "manager_reviews_return",
    "manager",
    "preparer_day_to_day",
    "preparer",
    "close_preparer",
    "day_to_day_contact",
    "client_service",
]
EarlierKind = Literal[
    "return_filed", "extension_filed", "engagement_letter_signed", "deliverable_released"
]
NoticeCode = Literal["agency_notice_in_review"]
