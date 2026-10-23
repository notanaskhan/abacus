"""The `portal` slice (P-08-T14; P-08 §1 and §5.4; POR-01, POR-02; DEC-213): what the white-
labelled portal needs from the live seed, as events the loader replays.

- **Branding.** Brightwater Hale's `portal_branding` row, verbatim from POR-01: the name above the
  card ("Brightwater Hale"), the footer's `address_line` ("Brightwater Hale LLP · 311 West
  Brannock Street, Chicago, IL"), Grace Holloway as the person a locked card names (POR-01g), and
  no "Secured by" footer. No help, privacy or terms URL: no source gives one.
- **The portal host.** `brightwaterhale.<portal_base_domain>`, a `default` host, active. Only the
  label lives here; the neutral domain is the environment's setting (`portal_base_domain`), read
  by the loader, so no domain is written into the scenario.
- **Portal people and their grants** (F-03-T26 roles and scopes), each a client user on the sink
  domain with a client membership:
  - Claire Feld, `taxpayer` on the Feld household **client** (POR-01a, POR-02a; DEC-211 gives a
    client-scope taxpayer the client admin cells).
  - Tess Moreno, `owner` on Copperleaf Coffee Roasters, Inc. (its **client entity**; POR-01c,
    POR-02d).
  - Ben Ashby, `contributor` on the same entity (CLI-04e: read-only, "Only owners can invite
    people or change roles.").
  - Meera Shah, `taxpayer` on her own 2025 Form 1040 (**work item**, POR-02e).
  - Dana Kowalski stays `audit_core`'s (`audits.PORTAL_USERS`, owner on the Northwind audit).
- **Sam Ortiz's invitation**, pending from Wed Sep 2, 2026 (POR-01d): Keystone Retirement
  Services' recordkeeper, invited to the Northwind Robotics 401(k) Plan audit by Grace Holloway
  (CLI-04's viewer), with the 14-day link CLI-04 shows.

Waiting on later tasks (DEC-213), so not here: Meera's `k1_recipient` grant (no K-1 package
exists until T-02), Tess's TOTP factor (P-08-T17's tables), the invitation's kind, grant template
and 9-item delegation (P-08-T18's columns), and POR-02b's Feb 2, 2026 history (no epoch predates
the firm's setup). Claire's welcome has never been dismissed, so her home reads `first_visit`
at any snapshot (DEC-210).

The slice needs `binders` (Meera's return work item); the loader adds it. Opt-in like `shell`
(`--slice portal`); `build()` keeps its default, so SCENARIO_HASH is unchanged. Mirrors
apps/web/src/fixtures/seed/portal.ts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.audits import SINK_DOMAIN, on_date
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import COPPERLEAF, RETURN_BY_LABEL
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import slug_of_client
from abacus_tools.synthetic.scenarios.brightwater_hale.people import slug_of
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "portal"
NEEDS: Final = ("binders",)
# Grace Holloway (Firm Admin, client service) sets the branding, grants client-wide access and
# invites from CLI-04 (P-08 J02 step 5: "Grace Holloway invites Tess Moreno and Ben Ashby").
BY: Final = "GH"

# --- branding and host (POR-01) ----------------------------------------------------------------

BRANDING: Final[dict[str, str | bool | None]] = {
    "display_name": "Brightwater Hale",
    "address_line": "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL",
    "support_contact_name": "Grace Holloway",
    "secured_footer": False,
}
# POR-01a: `brightwaterhale.<neutral-portal-domain>`; the domain is configuration.
HOST_LABEL: Final = "brightwaterhale"

# --- portal people (POR-01, POR-02) -------------------------------------------------------------

GrantRole = Literal["owner", "contributor", "taxpayer"]
ScopeKind = Literal["client", "client_entity", "work_item"]
FELD: Final = "Jonah & Claire Feld"
MEERA: Final = "Meera Shah"


@dataclass(frozen=True)
class PortalPerson:
    name: str
    client: str  # the client the scope belongs to, as the clients module spells it
    role: GrantRole
    scope_kind: ScopeKind
    scope: str  # the client's name, the entity's name, or the return's label

    @property
    def slug(self) -> str:
        return slug_of(self.name)

    @property
    def email(self) -> str:
        return f"{self.slug.replace('-', '.')}@{SINK_DOMAIN}"

    @property
    def id(self) -> str:
        return stable_id(f"user:{self.slug}")

    @property
    def grant_id(self) -> str:
        return stable_id(f"grant:{self.slug}:{self.scope_kind}:{self.scope}")


PORTAL_PEOPLE: Final[tuple[PortalPerson, ...]] = (
    PortalPerson("Claire Feld", FELD, "taxpayer", "client", FELD),
    PortalPerson("Tess Moreno", COPPERLEAF, "owner", "client_entity", COPPERLEAF),
    PortalPerson("Ben Ashby", COPPERLEAF, "contributor", "client_entity", COPPERLEAF),
    PortalPerson("Meera Shah", MEERA, "taxpayer", "work_item", slug_of_client(MEERA)),
)
PERSON_BY_NAME: Final = {p.name: p for p in PORTAL_PEOPLE}

# --- Sam Ortiz's invitation (POR-01d) -----------------------------------------------------------


@dataclass(frozen=True)
class Invitation:
    name: str
    org: str
    engagement: str  # the audit label
    role: Literal["client_contributor"]  # the role the existing invitation table takes
    sent: date
    days: int  # CLI-04b: "the link expires in 14 days"
    items: int  # POR-01d: "has asked Keystone Retirement Services for 9 items" (P-08-T18)

    @property
    def slug(self) -> str:
        return slug_of(self.name)

    @property
    def email(self) -> str:
        return f"{self.slug.replace('-', '.')}@{SINK_DOMAIN}"

    @property
    def id(self) -> str:
        return stable_id(f"invitation:{self.slug}:{self.engagement}")


SAM_ORTIZ: Final = Invitation(
    "Sam Ortiz",
    "Keystone Retirement Services",
    "A1",
    "client_contributor",
    date(2026, 9, 2),
    14,
    9,
)
INVITATIONS: Final = (SAM_ORTIZ,)
INVITATION_BY_NAME: Final = {i.name: i for i in INVITATIONS}


def work_item_of(person: PortalPerson) -> str:
    """A work-item scope's id: the return the person's grant names."""
    return RETURN_BY_LABEL[person.scope].id


@register_slice(SLICE)
def portal_events() -> list[Event]:
    events = [
        Event("portal-branding", SETUP_AT, "portal.branding_set", BY, SLICE, dict(BRANDING)),
        Event(
            f"portal-host:{HOST_LABEL}",
            SETUP_AT,
            "portal.host_added",
            BY,
            SLICE,
            {"label": HOST_LABEL, "kind": "default"},
        ),
    ]
    events += [
        Event(
            f"portal-person:{p.slug}",
            SETUP_AT,
            "identity.portal_person_added",
            BY,
            SLICE,
            {"person": p.name, "role": p.role, "scope_kind": p.scope_kind},
            client=p.client,
        )
        for p in PORTAL_PEOPLE
    ]
    events += [
        Event(
            f"invitation:{i.slug}",
            on_date(i.sent),
            "identity.client_invitation_created",
            BY,
            SLICE,
            {"invitee": i.name, "org": i.org, "engagement": i.engagement, "items": i.items},
            client="Northwind Robotics, Inc.",
        )
        for i in INVITATIONS
    ]
    return events
