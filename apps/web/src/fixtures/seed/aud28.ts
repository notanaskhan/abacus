// AUD-28 fixture data (Q-05-T20, TASK-8826; handoff AUD-28): the firm's consultations log, Tue
// Oct 6, 2026, 11:30 AM CT, Margaret Okonkwo. Words and figures verbatim from the handoff.
import { stableId } from "./prng";

export type Aud28State = "a" | "b" | "c" | "d" | "e" | "f" | "g";
const ROWS = [
  [
    "C-01",
    "open",
    "Granite Peak: do DSCR covenant results (1.32× vs 1.25× minimum) raise a going-concern indicator?",
    "Granite Peak Outdoor Supply",
    "2026-09-09",
    null,
  ],
  [
    "C-05",
    "open",
    "Lakeshore: allocation of the shared literacy-center lease across functional expenses",
    "Lakeshore Literacy Alliance",
    "2026-09-10",
    null,
  ],
  [
    "C-02",
    "concluded",
    "Copperleaf: do August 2026 CAS statements need the AR-C 70 legend (SSARS 27 not early-adopted)?",
    "Copperleaf Coffee Roasters",
    "2026-09-04",
    null,
  ],
  [
    "C-03",
    "concluded",
    "Northwind: is the December 26 late remittance a deficiency or a significant deficiency?",
    "Northwind Robotics 401(k) Plan",
    "2026-09-25",
    "Treat it as a significant deficiency. The control has a design gap (no backup approver). The failure produced a prohibited transaction (late participant contributions) reported on Schedule H line 4a. The matter merits the benefits committee's attention. The exposure is limited to a single payroll, about $50,000 against overall materiality of $252,200, so a material misstatement is not reasonably possible and it is not a material weakness.",
  ],
  [
    "C-04",
    "concluded",
    "Oakline: revenue recognition for multi-year SaaS contracts with implementation services",
    "Oakline",
    "2026-09-22",
    "Implementation fees recognized over the subscription term; EQR concurs.",
  ],
] as const;

export const ENGAGEMENT_NAMES: Readonly<Record<string, string>> = Object.fromEntries(
  ROWS.map(([ref, , , name]) => [stableId(`engagement:${ref}`), name]),
);

export function log(state: Aud28State) {
  if (state === "e") return { counts: { open: 0, concluded: 0 }, items: [] };
  const rows = state === "d" ? ROWS.filter((r) => r[0] === "C-03") : ROWS;
  return {
    counts: {
      open: rows.filter((r) => r[1] === "open").length,
      concluded: rows.filter((r) => r[1] === "concluded").length,
    },
    items: rows.map(([ref, status, question, , created, conclusion]) => ({
      consultation_id: stableId(`consultation:${ref}`), ref, status, question, conclusion,
      engagement_id: stableId(`engagement:${ref}`), created_at: `${created}T10:00:00-05:00`,
      consulted_with_user_id: stableId("user:celia-marsh"), consulted_with_name: "Celia Marsh",
      raised_by_name: "Hannah Leclerc",
    })), // prettier-ignore
  };
}

export function detail(ref: string) {
  const c04 = ref === "C-04";
  return {
    consultation_id: stableId(`consultation:${ref}`),
    facts:
      ref === "C-03"
        ? "Deferrals of $33,540 and match of $15,060 ($48,600) from the December 26, 2025 payroll reached the trust on January 9, 2026, 9 business days after payday; the other 25 biweekly remittances took 2 business days. The remittance file has no backup approver. Lost earnings on the deferrals are $64.38; the sponsor is correcting under the VFCP Self-Correction Component."
        : null,
    consulted_role: "partner",
    implemented: ref === "C-03",
    implemented_reference: ref === "C-03" ? "F-01 concluded Sep 28, 4:12 PM" : null,
    reopened_at: null,
    links: ref === "C-03"
      ? [["finding", "F-01 · AUD-15"], ["decision_card", "Decision · deficiency severity"], ["document", "AU-C 265 letter · AUD-22"]]
          .map(([kind, label]) => ({ kind, target_id: stableId(`link:${label ?? ""}`), at: "2026-09-28T16:12:00-05:00", linked_by_name: label }))
      : [], // prettier-ignore
    positions: c04
      ? [
          { role: "engagement_partner", recorded_by_name: "Celia Marsh", position: "recognize implementation fees over the subscription term", agrees: true, at: "2026-09-29T10:00:00-05:00" },
          { role: "eqr_reviewer", recorded_by_name: "Thomas Whitcombe", position: "implementation is a distinct performance obligation", agrees: false, at: "2026-09-29T11:00:00-05:00" },
        ]
      : [], // prettier-ignore
    resolution: c04
      ? { resolved_by_name: "Margaret Okonkwo", resolution: "implementation fees recognized over the subscription term; EQR concurs.", before_release: true, at: "2026-09-30T10:00:00-05:00" }
      : null, // prettier-ignore
    difference_unresolved: false,
  };
}

export const SELECTED: Readonly<Record<Aud28State, string | null>> = {
  a: "C-03",
  b: "C-04",
  c: "C-01",
  d: "C-03",
  e: null,
  f: "C-03",
  g: "C-01",
};
export const CONSULTEES = [
  ["celia-marsh", "Celia Marsh · Audit Partner, technical reviewer"],
  ["priya-raman", "Priya Raman · CAS Partner"],
  ["thomas-whitcombe", "Thomas Whitcombe · Partner"],
] as const;
