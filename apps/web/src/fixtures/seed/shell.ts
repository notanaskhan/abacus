// The firm menu's data (SHL-03 a–f; P-01-T07): the firm row and the training sandbox membership,
// the four persona cards, job titles, offices and the default office filter, and each persona's
// capability nav. Copy is verbatim from the SHL-03 handoff (spec, README and the canvas's built
// frames); the person lines are what each card shows, not a role name the SPA compares.

import type {
  CapabilitiesV3Draft,
  CapabilityNavDraft,
  MeV3Draft,
  MembershipV3Draft,
  OfficeRefDraft,
} from "../contracts/shell";
import { DEMO_INSTANT } from "./clock";
import {
  DEFAULT_OFFICE_FILTERS,
  JOB_TITLES,
  OFFICES,
  type OfficeName,
  SEATS,
  slugOf,
} from "./people";
import { stableId } from "./prng";
import { type Seed, meFor } from "./index";

/** SHL-03a firm row sub-line. */
export const FIRM_FACTS_LINE = "US · Central Time · 46 seats";
export const SANDBOX_FIRM_NAME = "Brightwater Hale LLP — Training sandbox";
/** SHL-03e sandbox row sub-line, with the "Sandbox" soon pill. */
export const SANDBOX_FACTS_LINE = "Sandbox · seeded demo data only";
export const SWITCH_TOAST = `Switched to ${SANDBOX_FIRM_NAME}`;
/** The same label as the Python scenario's `SANDBOX_FIRM_ID`. */
export const SANDBOX_FIRM_ID = stableId("firm:brightwater-hale-training-sandbox");
/** The office submenu (SHL-03f) and the row value when no default is set. */
export const ALL_OFFICES = "All offices";

/** The same label as the Python loader's `office_id_of`, so fixture and live ids agree. */
export function officeIdOf(name: OfficeName): string {
  return stableId(`office:${name}`);
}

export const OFFICE_REFS: readonly OfficeRefDraft[] = OFFICES.map((o) => ({
  id: officeIdOf(o.name),
  name: o.name,
}));

const NONE: CapabilityNavDraft = {
  firm_settings: "none",
  users_roles: "none",
  audit_log: "none",
  security_center: "none",
  developer_api: "none",
};

export interface ShellPersona {
  slug: string;
  initials: string;
  /** The card's second line, verbatim. */
  cardLine: string;
  nav: CapabilityNavDraft;
  /** Holds the training sandbox membership (SHL-03e). */
  sandbox: boolean;
}

/**
 * SHL-03 a–d. Admin rows follow the matrix action behind each key (epic §4.3): `write` for the
 * manage actions (`firm.manage_settings`, `firm.manage_users`, `security.manage`), `read` for
 * `firm.read_settings` (Daniel's "View only"), `audit_event.read` and the fixture-only Developer &
 * API row (`developer_api` reads `none` in production until G-03).
 */
export const SHELL_PERSONAS: readonly ShellPersona[] = [
  {
    slug: "grace-holloway",
    initials: "GH",
    cardLine: "Firm Admin · Client Service Coordinator · Chicago",
    nav: { ...NONE, firm_settings: "write", users_roles: "write", audit_log: "read" },
    sandbox: true,
  },
  {
    slug: "hannah-leclerc",
    initials: "HL",
    cardLine: "Audit Senior Manager · Chicago",
    nav: NONE,
    sandbox: false,
  },
  {
    slug: "daniel-reyes",
    initials: "DR",
    cardLine: "Tax Partner · New York",
    nav: { ...NONE, firm_settings: "read", audit_log: "read" },
    sandbox: false,
  },
  {
    slug: "felix-andersen",
    initials: "FA",
    cardLine: "IT / Security · Qualified Individual · Chicago",
    nav: { ...NONE, security_center: "write", developer_api: "read", audit_log: "read" },
    sandbox: false,
  },
];

export function shellPersona(slug: string): ShellPersona | undefined {
  return SHELL_PERSONAS.find((p) => p.slug === slug);
}

const seatOf = (slug: string) => SEATS.find((s) => slugOf(s.name) === slug);

/** `GET /v1/me` v3 for a persona slug, or undefined when nobody has that slug. */
export function meV3For(
  seed: Seed,
  slug: string,
  options: { defaultOfficeId?: string | null } = {},
): MeV3Draft | undefined {
  const me = meFor(seed, slug);
  if (me === undefined) return undefined;
  const seat = seatOf(slug);
  const persona = shellPersona(slug);
  const preset = seat === undefined ? undefined : DEFAULT_OFFICE_FILTERS[seat.initials];
  const live: MembershipV3Draft[] = me.memberships.map((m) => ({
    ...m,
    firm: {
      region: "US",
      time_zone: seed.firm.timeZone,
      seats_total: seed.seats.length,
      is_sandbox: false,
      sandbox_of: null,
    },
  }));
  const sandbox: MembershipV3Draft[] =
    persona?.sandbox === true
      ? [
          {
            tenant_id: SANDBOX_FIRM_ID,
            firm_name: SANDBOX_FIRM_NAME,
            firm_role: live[0]?.firm_role ?? null,
            kind: "staff",
            firm: {
              region: "US",
              time_zone: seed.firm.timeZone,
              seats_total: null,
              is_sandbox: true,
              sandbox_of: seed.firm.id,
            },
          },
        ]
      : [];
  return {
    ...me,
    user: {
      initials: seat?.initials ?? null,
      job_title: seat === undefined ? null : (JOB_TITLES[seat.initials] ?? null),
    },
    default_office_id:
      options.defaultOfficeId !== undefined
        ? options.defaultOfficeId
        : preset === undefined
          ? null
          : officeIdOf(preset),
    offices: [...OFFICE_REFS],
    memberships: [...live, ...sandbox],
  };
}

/** `GET /v1/me/capabilities` with the nav keys; anyone not on SHL-03 a–d reads every key `none`. */
export function capabilitiesFor(seed: Seed, slug: string): CapabilitiesV3Draft {
  const seat = seatOf(slug);
  return {
    capabilities: [],
    clock_mode: "offset",
    engagement_id: null,
    entitlements: [],
    flags: {},
    mfa_recent_until: null,
    office_id: seat === undefined ? null : officeIdOf(seat.office),
    portal: null,
    roles: [],
    server_now: DEMO_INSTANT,
    tz: seed.firm.timeZone,
    nav: shellPersona(slug)?.nav ?? NONE,
  };
}

/** The office submenu's labels (SHL-03f), in order. */
export function officeMenu(): string[] {
  return [ALL_OFFICES, ...OFFICES.map((o) => o.name)];
}
