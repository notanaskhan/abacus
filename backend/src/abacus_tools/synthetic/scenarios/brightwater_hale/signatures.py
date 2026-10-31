"""Brightwater Hale's signatures at E0 (N-02-T36; N-02 §9; SIG-01, SIG-02, POR-06, ENG-04;
blueprint 01 §9.7; DEC-1573).

SIG-01 on Mon Sep 14, 2026 shows 17 envelopes out for signature (E1 to E17: ten 8879-family
authorizations, four engagement letters, two representation letters, the Ferris consents), two to
send (Harborview's 8879-PE, E18, drafted by Grace Holloway at 9:40 AM; the agent's Form 2848 for
Aurelio Santos), six completed in the last 30 days and the Raos' expired offshore-preparer consent.
The tiles read 8 sent, 5 viewed, 4 partially signed; by type 10 e-file, 4 letters, 2 rep, 1
consent. Also on the timeline: Irene Kowal's three failed identity checks on Sun Sep 13 at
8:06, 8:10 and 8:14 PM (E2 reads "Identity check locked"), Copperleaf's 2026 Close letter signed by
Ben Ashby on Mar 2 and countersigned by Priya Raman on Mar 3, and the ERSD disclosure v1 imported
as database content (POR-06 shows it before a first signature). The Feld household's §7216
consents are `consents_7216`'s.

Each row mirrors `apps/web/src/fixtures/seed/signatures.ts` (T-02's hub fixtures, N-02-T10):
`hub_rows()` is what `make fixtures` writes to `seed/E0.signatures-hub.json`, which the TypeScript
scenarios are held to. Every name and date is the handoff's; every value is synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "signatures"
NEEDS: Final = ("binders", "consents_7216")
CT: Final = ZoneInfo("America/Chicago")
E0: Final = date(2026, 9, 14)
E18_AT: Final = datetime(2026, 9, 14, 9, 40, tzinfo=CT)
KOWAL_FAILURES: Final = (
    datetime(2026, 9, 13, 20, 6, tzinfo=CT),
    datetime(2026, 9, 13, 20, 10, tzinfo=CT),
    datetime(2026, 9, 13, 20, 14, tzinfo=CT),
)
ERSD_VERSION: Final = 1
# Synthetic: the firm's ERSD text is its own content, imported once (ESIGN Act §101(c)).
ERSD_BODY: Final = (
    "Brightwater Hale LLP · Consent to electronic records and signatures (version 1). "
    "Synthetic disclosure text for the demonstration firm: you may receive and sign documents "
    "electronically, request a paper copy at no charge, and withdraw this consent at any time "
    "by contacting the firm. You need a current browser and an email address to continue."
)

HubStatus = Literal["draft", "sent", "viewed", "partially_signed", "completed", "expired"]
HubPurpose = Literal["form_8879", "engagement_letter", "rep_letter", "consent_7216", "form_2848"]


@dataclass(frozen=True)
class HubSigner:
    """A signer as SIG-01 draws it: a client contact by name, or a firm user by initials."""

    name: str
    signed_on: date | None = None
    firm: bool = False  # `name` is a seat's initials (the countersigner)
    kba_locked: bool = False  # three failed identity checks (E2's Irene Kowal)

    @property
    def signed(self) -> bool:
        return self.signed_on is not None


@dataclass(frozen=True)
class HubEnvelope:
    key: str
    title: str
    client: str  # as SIG-01 writes it
    scenario_client: str  # the client row it belongs to
    purpose: HubPurpose
    stored_purpose: str  # C7's purpose code (8879-PE and 8879-F have their own)
    form_code: str | None
    signers: tuple[HubSigner, ...]
    sent: date | None
    viewed: date | None
    due: date | None
    work_item: str
    status: HubStatus
    note: str | None = None
    drafted_by: str = "GH"  # a seat, or "agent"
    outcome: str | None = None
    completed: date | None = None
    expired: date | None = None

    @property
    def id(self) -> str:
        return stable_id(f"envelope:{self.key}")

    @property
    def policy_family(self) -> str:
        if self.stored_purpose.startswith("form_8879"):
            return "efile_authorization"
        if self.purpose == "consent_7216":
            return "consent"
        if self.purpose == "engagement_letter":
            return "engagement_letter"
        return "general"


def _s(name: str, signed_on: date | None = None, **kw: bool) -> HubSigner:
    return HubSigner(name, signed_on, **kw)


def _d(month: int, day: int) -> date:
    return date(2026, month, day)


def _tax(
    key: str,
    form: str,
    client: str,
    signers: tuple[HubSigner, ...],
    sent: date,
    viewed: date | None,
    due: date,
    work_item: str,
    status: HubStatus,
    note: str | None = None,
) -> HubEnvelope:
    stored = {"8879-PE": "form_8879_pe", "8879-F": "form_8879_f"}.get(form, "form_8879")
    return HubEnvelope(
        key,
        f"Form {form} · TY2025 · {client}",
        client,
        client,
        "form_8879",
        stored,
        form,
        signers,
        sent,
        viewed,
        due,
        work_item,
        status,
        note,
    )


_TAX: Final = (
    _tax("E1", "8879", "Elena Varga", (_s("Elena"),), _d(9, 9), _d(9, 10), _d(10, 1),
         "TY2025 Form 1040 · Varga", "viewed"),
    _tax("E2", "8879", "Thomas & Irene Kowal",
         (_s("Thomas", _d(9, 12)), _s("Irene", kba_locked=True)), _d(9, 10), _d(9, 13),
         _d(10, 1), "TY2025 Form 1040 · Kowal", "partially_signed", "Identity check locked"),
    _tax("E3", "8879-PE", "Kestrel Ventures Fund I, LP", (_s("GP officer"),), _d(9, 11), None,
         _d(9, 15), "TY2025 Form 1065 · Kestrel", "sent"),
    _tax("E4", "8879-F", "Pryor Irrevocable Trust", (_s("Trustee"),), _d(9, 10), _d(9, 11),
         _d(9, 28), "TY2025 Form 1041 · Pryor", "viewed"),
    _tax("E5", "8879", "Corinne Abbott", (_s("Corinne"),), _d(9, 12), None, _d(10, 5),
         "TY2025 Form 1040 · Abbott", "sent"),
    _tax("E6", "8879", "Dev & Mira Kapoor", (_s("Dev", _d(9, 9)), _s("Mira")), _d(9, 8),
         _d(9, 8), _d(10, 5), "TY2025 Form 1040 · Kapoor", "partially_signed"),
    _tax("E7", "8879-S", "Larkspur Floral, Inc.", (_s("President"),), _d(9, 11), _d(9, 12),
         _d(9, 15), "TY2025 Form 1120-S · Larkspur", "viewed"),
    _tax("E8", "8879", "Hugo Brandvold", (_s("Hugo"),), _d(9, 13), None, _d(10, 5),
         "TY2025 Form 1040 · Brandvold", "sent"),
    _tax("E9", "8879", "Noor & Adam Farouk", (_s("Noor"), _s("Adam")), _d(9, 13), None,
         _d(10, 5), "TY2025 Form 1040 · Farouk", "sent"),
    _tax("E10", "8879-C", "Brightline Optics, Inc.", (_s("CFO"),), _d(9, 12), None, _d(10, 8),
         "TY2025 Form 1120 · Brightline", "sent"),
)  # fmt: skip


def _letter(
    key: str,
    title: str,
    client: str,
    scenario_client: str,
    purpose: HubPurpose,
    signers: tuple[HubSigner, ...],
    sent: date,
    viewed: date | None,
    due: date | None,
    work_item: str,
    status: HubStatus,
) -> HubEnvelope:
    return HubEnvelope(
        key,
        title,
        client,
        scenario_client,
        purpose,
        purpose,
        None,
        signers,
        sent,
        viewed,
        due,
        work_item,
        status,
    )


_LETTERS: Final = (
    _letter("E11", "Engagement letter · PY2025 EBP audit · Fairhaven Foods 401(k) Plan",
            "Fairhaven Foods 401(k) Plan", "Fairhaven Foods 401(k) Plan", "engagement_letter",
            (_s("Plan administrator"), _s("MO", firm=True)), _d(9, 8), None, _d(9, 18),
            "PY2025 EBP audit · Fairhaven", "sent"),
    _letter("E12", "Engagement letter · 2026 Close (from Oct) · Bluestem Analytics",
            "Bluestem Analytics", "Bluestem Analytics, LLC", "engagement_letter",
            (_s("Arjun Mehta"), _s("PR", firm=True)), _d(9, 11), _d(9, 12), _d(9, 25),
            "2026 Close · Bluestem", "viewed"),
    _letter("E13", "Engagement letter · Ridgeline cost segregation & §754 analysis", "Ridgeline",
            "Ridgeline Property Partners, LP", "engagement_letter",
            (_s("Owen Calder"), _s("DR", firm=True)), _d(9, 14), None, _d(9, 24),
            "Advisory project · Ridgeline", "sent"),
    _letter("E14", "Engagement letter · FY2026 FS audit · Granite Peak Outdoor Supply",
            "Granite Peak Outdoor Supply", "Granite Peak Outdoor Supply, Inc.",
            "engagement_letter", (_s("Luis Ferrante", _d(9, 3)), _s("MO", firm=True)),
            _d(9, 2), _d(9, 3), _d(9, 16), "FY2026 FS audit · Granite Peak", "partially_signed"),
    _letter("E15", "Rep letter · PY2025 EBP audit · Cobalt Ridge Manufacturing 401(k) Plan",
            "Cobalt Ridge Manufacturing 401(k) Plan", "Cobalt Ridge Manufacturing 401(k) Plan",
            "rep_letter", (_s("Plan administrator"),), _d(9, 11), None, None,
            "PY2025 EBP audit · Cobalt Ridge", "sent"),
    _letter("E16", "Rep letter · PY2025 EBP audit · Halden Health 403(b) Plan",
            "Halden Health 403(b) Plan", "Halden Health 403(b) Plan", "rep_letter",
            (_s("Plan administrator"),), _d(9, 12), _d(9, 13), None,
            "PY2025 EBP audit · Halden", "viewed"),
    _letter("E17", "§7216 consents (use · AI disclosure — 2 documents) · Morgan & Kai Ferris",
            "Morgan & Kai Ferris", "Morgan & Kai Ferris", "consent_7216",
            (_s("Morgan", _d(9, 9)), _s("Kai")), _d(9, 9), _d(9, 9), _d(9, 23),
            "TY2025 Form 1040 · Ferris", "partially_signed"),
)  # fmt: skip

OUT: Final = tuple(
    sorted(
        (*_TAX, *_LETTERS),
        key=lambda e: ((e.due or date.max).isoformat(), int(e.key[1:])),
    )
)

TO_SEND: Final = (
    HubEnvelope(
        "E18",
        "Form 8879-PE · TY2025 · Harborview Dental Properties, LP",
        "Harborview Dental Properties, LP",
        "Harborview Dental Properties, LP",
        "form_8879",
        "form_8879_pe",
        "8879-PE",
        (_s("Dr. Sofia Lindqvist"),),
        None,
        None,
        _d(9, 15),
        "TY2025 Form 1065 · Harborview",
        "draft",
    ),
    HubEnvelope(
        "D2",
        "Form 2848 · Aurelio Santos · IRS CP14 TY2024",
        "Aurelio Santos",
        "Aurelio Santos",
        "form_2848",
        "form_2848",
        "2848",
        (_s("Aurelio Santos"), _s("DR", firm=True)),
        None,
        None,
        None,
        "IRS CP14 TY2024 · Santos",
        "draft",
        note="Needs review — notice N5 blocked until filed",
        drafted_by="agent",
    ),
)


def _done(
    key: str,
    form: str,
    client: str,
    signers: tuple[HubSigner, ...],
    sent: date,
    work_item: str,
    outcome: str | None,
) -> HubEnvelope:
    stored = {"8879-PE": "form_8879_pe", "8879-F": "form_8879_f"}.get(form, "form_8879")
    return HubEnvelope(
        key,
        f"Form {form} · {client}",
        client,
        client,
        "form_8879",
        stored,
        form,
        signers,
        sent,
        None,
        None,
        work_item,
        "completed",
        outcome=outcome,
        completed=sent,
    )


COMPLETED: Final = (
    _done("C1", "8879", "Sunil & Asha Rao", (_s("Sunil", _d(9, 10)), _s("Asha", _d(9, 10))),
          _d(9, 10), "TY2025 Form 1040 · Rao", "Filed Sep 11"),
    _done("C2", "8879-S", "Summit Line Logistics, Inc.", (_s("President", _d(9, 11)),),
          _d(9, 11), "TY2025 Form 1120-S · Summit Line", "Filed Sep 12"),
    _done("C3", "8879-PE", "Vantage Point Realty, LLC", (), _d(9, 4),
          "TY2025 Form 1065 · Vantage Point", "Accepted"),
    _done("C4", "8879-PE", "Cedar Hollow Farms, LLC", (), _d(9, 2),
          "TY2025 Form 1065 · Cedar Hollow", "Accepted"),
    HubEnvelope("C5",
                "Engagement letter · 2025 Form 990 (FYE Jun 30, 2026) · "
                "Lakeshore Literacy Alliance",
                "Lakeshore Literacy Alliance", "Lakeshore Literacy Alliance", "engagement_letter",
                "engagement_letter", None,
                (_s("Monica Hale-Ruiz", _d(8, 28)), _s("CM", _d(8, 28), firm=True)), _d(8, 28),
                None, None, "2025 Form 990 · Lakeshore", "completed", completed=_d(8, 28)),
    _done("C6", "8879-S", "Two Rivers Brewing Co.", (), _d(8, 27),
          "TY2025 Form 1120-S · Two Rivers", "Accepted"),
)  # fmt: skip

EXPIRED: Final = (
    HubEnvelope(
        "X1",
        "§7216 consent (disclosure to offshore preparers) · Sunil & Asha Rao",
        "Sunil & Asha Rao",
        "Sunil & Asha Rao",
        "consent_7216",
        "consent_7216",
        None,
        (_s("Sunil"), _s("Asha")),
        _d(8, 16),
        None,
        _d(8, 30),
        "TY2025 Form 1040 · Rao",
        "expired",
        note=(
            "Not resent — no offshore staffing on this return; services are never conditioned "
            "on consent"
        ),
        expired=_d(8, 30),
    ),
)

# Copperleaf's 2026 Close letter (ENG-04 d): signed Mar 2 by Ben Ashby (approver of record),
# countersigned Mar 3 by Priya Raman; older than SIG-01's 30-day Completed list.
COPPERLEAF: Final = HubEnvelope(
    "L1",
    "Engagement letter · 2026 Close · Copperleaf Coffee Roasters, Inc.",
    "Copperleaf Coffee Roasters, Inc.",
    "Copperleaf Coffee Roasters, Inc.",
    "engagement_letter",
    "engagement_letter",
    None,
    (_s("Ben Ashby", _d(3, 2)), _s("PR", _d(3, 3), firm=True)),
    _d(2, 27),
    _d(3, 2),
    None,
    "2026 Close · Copperleaf",
    "completed",
    completed=_d(3, 3),
)

ALL: Final = (*OUT, *TO_SEND, *COMPLETED, *EXPIRED, COPPERLEAF)
BY_KEY: Final = {e.key: e for e in ALL}
# The firm's envelope numbers: E1 to E18 as the handoff numbers them, the rest after 100.
NUMBERS: Final = {
    e.key: int(e.key[1:]) if e.key.startswith("E") else 100 + n for n, e in enumerate(ALL)
}


def hub_counts(on: date = E0) -> dict[str, object]:
    """SIG-01's tab counts, tiles and by-type tile at `on` (code computes them)."""
    within = [e.key for e in OUT if e.due is not None and 0 <= (e.due - on).days <= 7]
    by_type = {"efile": 0, "letters": 0, "rep": 0, "consents": 0}
    kinds = {
        "form_8879": "efile",
        "engagement_letter": "letters",
        "rep_letter": "rep",
        "consent_7216": "consents",
    }
    for e in OUT:
        by_type[kinds[e.purpose]] += 1
    return {
        "toSend": len(TO_SEND),
        "out": len(OUT),
        "expired": len(EXPIRED),
        "tiles": {
            "sent": sum(1 for e in OUT if e.status == "sent"),
            "viewed": sum(1 for e in OUT if e.status == "viewed"),
            "partially_signed": sum(1 for e in OUT if e.status == "partially_signed"),
            "dueWithin7": len(within),
        },
        "byType": by_type,
        "dueWithin7": within,
    }


def _hub_row(e: HubEnvelope) -> dict[str, object]:
    row: dict[str, object] = {
        "key": e.key,
        "title": e.title,
        "client": e.client,
        "purpose": e.purpose,
        "signers": [{"name": s.name, "signed": s.signed} for s in e.signers],
        "sent": None if e.sent is None else e.sent.isoformat(),
        "viewed": None if e.viewed is None else e.viewed.isoformat(),
        "due": None if e.due is None else e.due.isoformat(),
        "workItem": e.work_item,
        "status": e.status,
    }
    if e.outcome is not None:
        row["outcome"] = e.outcome
    return row


def hub_rows() -> dict[str, object]:
    """The SIG-01 lists and counts as the TypeScript scenarios hold them (`make fixtures`)."""
    return {
        "out": [_hub_row(e) for e in OUT],
        "toSend": [_hub_row(e) for e in TO_SEND],
        "completed": [_hub_row(e) for e in COMPLETED],
        "expired": [_hub_row(e) for e in EXPIRED],
        "counts": {k: v for k, v in hub_counts().items() if k != "dueWithin7"},
    }


def at(day: date | None, hour: int = 9, minute: int = 0) -> datetime | None:
    return None if day is None else datetime.combine(day, time(hour, minute), CT)


@register_slice(SLICE)
def _signatures_slice() -> list[Event]:
    # The firm and its people exist from SETUP_AT (audit_core); each row keeps its own dates.
    first = SETUP_AT
    events = [
        Event(
            "esign-disclosure:v1",
            first,
            "signatures.disclosure_imported",
            "GH",
            SLICE,
            {"version": ERSD_VERSION},
        )
    ]
    for e in ALL:
        # A draft is on SIG-01 at E0 (9:24 AM), so it is recorded at 9:00 (E18_AT is SIG-02's
        # clock, when Grace opens it); the rest when they were sent.
        when = at(e.sent) or at(E0, 9, 0) or first
        events.append(
            Event(
                f"envelope:{e.key}",
                max(when, first + timedelta(minutes=1)),
                "signatures.envelope_recorded",
                "GH",
                SLICE,
                {"key": e.key},
                client=e.scenario_client,
            )
        )
    return sorted(events, key=lambda ev: (ev.at, ev.label))


__all__ = [
    "ALL",
    "BY_KEY",
    "COMPLETED",
    "COPPERLEAF",
    "ERSD_BODY",
    "EXPIRED",
    "KOWAL_FAILURES",
    "NEEDS",
    "NUMBERS",
    "OUT",
    "SLICE",
    "TO_SEND",
    "HubEnvelope",
    "HubSigner",
    "at",
    "hub_counts",
    "hub_rows",
]
