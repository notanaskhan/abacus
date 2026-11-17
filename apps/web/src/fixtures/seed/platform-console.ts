// PLT-01 Accrued tenant console (G-04-T14; handoff PLT-01): the six production tenants, Brightwater
// Hale's drawer, the provisioning wizard for Ainsley Ward Partners, Kessling Mott's support request,
// regions and library releases, verbatim from the handoff spec. Seats used 46 + 128 + 212 + 18 + 0 =
// 404 of 490 provisioned (the sandbox excluded). Tenant metadata only: no firm client name appears.

export type TenantHealth = "healthy" | "degraded" | "onboarding";

export interface ConsoleTenant {
  id: string;
  firm: string;
  region: string;
  seats: { used: number; of: number } | "sandbox";
  modules: string[];
  health: TenantHealth;
  healthNote?: string;
  channel: string;
  support: string | null;
  supportPending?: boolean;
  since: string;
}

const ALL = ["Tax", "Audit & assurance", "Client accounting", "Advisory"];

export const CONSOLE_TENANTS: ConsoleTenant[] = [
  {
    id: "tnt_bh01",
    firm: "Brightwater Hale LLP",
    region: "United States",
    seats: { used: 46, of: 46 },
    modules: ALL,
    health: "healthy",
    channel: "Stable · 2026.9",
    support: "No open session",
    since: "Jan 5, 2026",
  },
  {
    id: "tnt_bh01-sbx",
    firm: "Brightwater Hale LLP — Training sandbox",
    region: "United States",
    seats: "sandbox",
    modules: ALL,
    health: "healthy",
    channel: "Stable · 2026.9",
    support: null,
    since: "Jan 5, 2026",
  },
  {
    id: "tnt_tr07",
    firm: "Tidewell Rourke & Co. LLP",
    region: "United States",
    seats: { used: 128, of: 140 },
    modules: ["Tax", "Audit & assurance"],
    health: "healthy",
    channel: "Stable · 2026.9",
    support: null,
    since: "Mar 2, 2026",
  },
  {
    id: "tnt_km03",
    firm: "Kessling Mott LLP",
    region: "United States",
    seats: { used: 212, of: 220 },
    modules: ["Tax", "Audit & assurance", "Client accounting"],
    health: "degraded",
    healthNote: "tax-engine sync latency",
    channel: "Early access · 2026.10-rc1",
    support: "Requested 8:55 AM",
    supportPending: true,
    since: "Feb 9, 2026",
  },
  {
    id: "tnt_op12",
    firm: "Ostrander Pike CPAs",
    region: "United States",
    seats: { used: 18, of: 20 },
    modules: ["Tax"],
    health: "healthy",
    channel: "Stable · 2026.9",
    support: null,
    since: "Apr 20, 2026",
  },
  {
    id: "tnt_aw15",
    firm: "Ainsley Ward Partners",
    region: "United States",
    seats: { used: 0, of: 64 },
    modules: ["Tax", "Client accounting"],
    health: "onboarding",
    healthNote: "first admin invited",
    channel: "Stable · 2026.9",
    support: null,
    since: "Sep 10, 2026",
  },
]; // fmt: skip

/** b: Brightwater Hale's drawer. */
export const BH_DRAWER = {
  modules: ALL,
  modulesHelper: "Advisory added Mar 2, 2026",
  seats: 46,
  renewal: "Jan 1, 2027",
  region: "United States",
  regionHelper: "Storage Ohio, backup Oregon; inference US",
  channel: "Stable",
  channelHelper: "2026.9 · 28 agents · released Sep 1, 2026",
  policyPrincipal: true,
  policyHelper: "The firm decides in its AI policy; currently off.",
  supportNote: "The firm allows session requests (Security center).",
  history:
    "Aug 17, 2026 · Jordan Pryce · reason 'CCH Axcess token refresh failure (Season Progress Reporter run)' · scope Integration settings only · approved by Felix Andersen 10:12 AM · 2-hour window · closed 11:40 AM",
};

/** c: provisioning Ainsley Ward Partners (the Review step). */
export const AW_PROVISION = {
  firm: "Ainsley Ward Partners",
  region: "United States",
  plannedRegions: ["European Union", "United Kingdom"],
  modules: ["Tax", "Client accounting"],
  seats: 64,
  admins: "Firm Admin + IT/Security (emails from the signed order form)",
  channel: "Stable",
  toast: "Tenant created · invites sent to 2 first admins",
};

/** d: Kessling Mott's support session request (the console cannot approve it). */
export const KM_SUPPORT = {
  firm: "Kessling Mott LLP",
  requestedBy: "Jordan Pryce",
  reason: "Tax-engine sync latency since Sep 12",
  scope: "Integration settings and sync logs only",
  duration: "2 hours",
  status: "Awaiting firm approval (Kessling Mott IT/Security)",
};

/** e: library releases (fixture-only until W-03). */
export const LIBRARY_RELEASES = [
  {
    channel: "Stable",
    version: "2026.9",
    agents: "28 agents",
    released: "released Sep 1, 2026",
    tenants: "5 tenants",
  },
  {
    channel: "Early access",
    version: "2026.10-rc1",
    agents: "30 agents (+ Form 5500 Tie-out, + 1099 Readiness Checker)",
    released: "",
    tenants: "1 tenant",
  },
]; // fmt: skip

/** f: regions. */
export const CONSOLE_REGIONS = [
  { name: "United States", live: true },
  { name: "European Union", live: false },
  { name: "United Kingdom", live: false },
];
