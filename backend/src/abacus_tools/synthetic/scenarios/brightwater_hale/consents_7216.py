"""Brightwater Hale's §7216 consents (T-01-T23; T-01 §3.1, §3.5; ADM-05, CLI-05; DEC-1366).

ADM-05 on Mon Sep 14, 2026 shows 218 consents: 212 signed, 2 expiring, 1 requested, 1 expired, 1
declined, 1 revoked. They are:

- one `use` + `ai_disclosure` set per TY2025 tax engagement (214 engagements, `binders`), signed
  for 211 of them; Morgan & Kai Ferris's is requested with Morgan signed Sep 9 and Kai pending
  (envelope due Sep 23); Harold Stein declined on Feb 10, 2026 (never re-solicited); the Estate of
  Walter Thornbury has none (executor consent follows acceptance). The handoff's named sets keep
  their dates; the rest are signed on a stable spread through Jan 13 to Feb 27, 2026. Every set
  expires Dec 31, 2026 except Ridgeline's (signed Feb 6, 2026 with the engagement letter, expires
  Feb 6, 2027), so 210 expire Dec 31.
- five disclosures to a named third party, each one purpose and one recipient, naming return
  information that existed when signed: the Iyers (expired Aug 1, 2026), the Raos and Benjamin
  Osterberg (expiring in 16 and 22 days), Delia Fortune (revoked Jun 2, 2026), the Okafors
  (signed, expires Mar 3, 2027).

The display status is derived at a date (`status_on`), as ADM-05 does: signed within 30 days of
expiry reads expiring, past expiry reads expired. Every value is synthetic (AGENTS 16): no consent
text is stored, only the template version and its hash, as record mode writes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.binders import TAX_ENGAGEMENTS
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "consents_7216"
NEEDS: Final = ("binders",)  # the tax engagements whose entities the sets name
SNAPSHOT: Final = date(2026, 9, 14)
TOTAL: Final = 218
TILES: Final = {
    "signed": 212,
    "expiring": 2,
    "requested": 1,
    "expired": 1,
    "declined": 1,
    "revoked": 1,
}
DEC_31: Final = date(2026, 12, 31)
FERRIS: Final = "Morgan & Kai Ferris"
STEIN: Final = "Harold Stein"
THORNBURY: Final = "Estate of Walter Thornbury"
RIDGELINE: Final = "Ridgeline Property Partners, LP"
AGENT_RECIPIENT: Final = "Accrued Agent sub-processors (US)"
Stored = Literal["requested", "signed", "declined", "revoked"]
Shown = Literal["signed", "expiring", "requested", "expired", "declined", "revoked"]

# The handoff's named sets (ADM-05 rows 8 to 14) keep their dates.
_NAMED_SIGNED: Final = {
    "Jonah & Claire Feld": date(2026, 2, 2),
    "Marcus & Dana Whitley": date(2026, 1, 20),
    "Meera Shah": date(2026, 1, 27),
    "Calloway Family Trust": date(2026, 2, 9),
    "Elena Varga": date(2026, 2, 16),
    RIDGELINE: date(2026, 2, 6),
    "Copperleaf Coffee Roasters, Inc.": date(2026, 1, 13),
}


@dataclass(frozen=True)
class Signer:
    role: Literal["taxpayer", "spouse", "officer", "fiduciary", "partner"]
    signed_on: date | None


@dataclass(frozen=True)
class ConsentRow:
    """One registry row: a set (`use` + `ai_disclosure`) or a single third-party disclosure."""

    label: str
    client: str
    entity: str
    purposes: tuple[str, ...]
    tax_years: tuple[int, ...]
    recipient: str
    status: Stored
    signers: tuple[Signer, ...]
    signed_on: date | None
    expires_on: date | None
    declined_on: date | None = None
    revoked_on: date | None = None

    @property
    def set_id(self) -> str:
        return stable_id(f"consent-set:{self.label}")

    def consent_id(self, purpose: str) -> str:
        return stable_id(f"consent:{self.label}:{purpose}")

    def status_on(self, on: date) -> Shown:
        if self.status != "signed":
            return self.status
        if self.expires_on is not None and self.expires_on <= on:
            return "expired"
        if self.expires_on is not None and self.expires_on - on <= timedelta(days=30):
            return "expiring"
        return "signed"


def _joint(client: str) -> bool:
    return " & " in client and not client.endswith(("Inc.", "LLP", "LLC"))


def _spread(rank: int) -> date:
    """A stable signing day through Jan 13 to Feb 27, 2026 for the unnamed sets."""
    return date(2026, 1, 13) + timedelta(days=rank % 46)


def _ai_sets() -> list[ConsentRow]:
    out: list[ConsentRow] = []
    unnamed = 0
    for e in TAX_ENGAGEMENTS:
        if e.client == THORNBURY:
            continue  # executor consent follows acceptance: no row
        joint = _joint(e.client)
        if e.client == FERRIS:
            status: Stored = "requested"
            signers = (Signer("taxpayer", date(2026, 9, 9)), Signer("spouse", None))
            signed, expires, declined = None, None, None
        elif e.client == STEIN:
            status, signers = "declined", (Signer("taxpayer", None),)
            signed, expires, declined = None, None, date(2026, 2, 10)
        else:
            status = "signed"
            signed = _NAMED_SIGNED.get(e.client)
            if signed is None:
                signed = _spread(unnamed)
                unnamed += 1
            expires = date(2027, 2, 6) if e.client == RIDGELINE else DEC_31
            declined = None
            signers = (
                (Signer("taxpayer", signed), Signer("spouse", signed))
                if joint
                else (Signer("taxpayer", signed),)
            )
        out.append(
            ConsentRow(
                f"ai:{e.label}",
                e.client,
                e.entity,
                ("use", "ai_disclosure"),
                (2025,),
                AGENT_RECIPIENT,
                status,
                signers,
                signed,
                expires,
                declined_on=declined,
            )
        )
    return out


def _third_party() -> list[ConsentRow]:
    def row(
        client: str,
        years: tuple[int, ...],
        recipient: str,
        signed: date,
        expires: date | None,
        *,
        revoked: date | None = None,
    ) -> ConsentRow:
        return ConsentRow(
            f"third-party:{stable_id(client)[:8]}",
            client,
            client,
            ("third_party_disclosure",),
            years,
            recipient,
            "revoked" if revoked else "signed",
            (Signer("taxpayer", signed),),
            signed,
            expires,
            revoked_on=revoked,
        )

    return [
        row(
            "Priyanka & Sam Iyer",
            (2023, 2024),
            "Lakeview Credit Union (mortgage underwriting)",
            date(2025, 8, 1),
            date(2026, 8, 1),
        ),
        row(
            "Sunil & Asha Rao",
            (2024,),
            "Halvard Securities (financial advisor)",
            date(2025, 9, 30),
            date(2026, 9, 30),
        ),
        row(
            "Benjamin Osterberg",
            (2023, 2024),
            "Ellery & Shaw LLP (estate attorney)",
            date(2025, 10, 6),
            date(2026, 10, 6),
        ),
        row(
            "Delia Fortune",
            (2025,),
            "Halvard Securities",
            date(2026, 3, 2),
            None,
            revoked=date(2026, 6, 2),
        ),
        row(
            "Daniel & Ruth Okafor",
            (2025,),
            "Lakeview Credit Union (refinance)",
            date(2026, 3, 3),
            date(2027, 3, 3),
        ),
    ]


ROWS: Final = (*_ai_sets(), *_third_party())
ROW_BY_LABEL: Final = {r.label: r for r in ROWS}


def tiles_on(on: date) -> dict[str, int]:
    out = dict.fromkeys(TILES, 0)
    for r in ROWS:
        out[r.status_on(on)] += 1
    return out


@register_slice(SLICE)
def _consents_slice() -> list[Event]:
    return [
        Event(
            f"consent:{r.label}",
            SETUP_AT,
            "organisations.consent_recorded",
            "system",
            SLICE,
            {"row": r.label},
            client=r.client,
        )
        for r in ROWS
    ]


__all__ = [
    "NEEDS",
    "ROWS",
    "ROW_BY_LABEL",
    "SLICE",
    "SNAPSHOT",
    "TILES",
    "TOTAL",
    "ConsentRow",
    "Signer",
    "tiles_on",
]
