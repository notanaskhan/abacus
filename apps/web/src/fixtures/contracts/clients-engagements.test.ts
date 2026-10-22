// P-07-T06: consumer fixture assertions for the clients v1 and engagements v2 stubs (CLI-01, CLI-02,
// ENG-01, ENG-02, ENG-03). Each frame is typed with the generated client, so a removed or renamed
// field fails `tsc`, and checked against the OpenAPI document at run time, for what a type cannot
// say (uuid and date formats, patterns, closed enums, a field the schema does not have).
// Brightwater Hale, synthetic: names and figures from the screen contracts (docs/screens/) and the
// contract docs' §8; ids and period dates are placeholders. The pytest half lives in
// backend/tests/contracts/{clients,engagements_v2}/.
import type {
  ClientRecordOut,
  ClientRowOut,
  EngagementDraftIn,
  EngagementGateOut,
  EngagementIndexPage,
  EngagementTypeCatalogueOut,
  EngagementTypeEntryOut,
  ListPageClientRowOut,
  MaskedTinOut,
  TinRevealOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { validateSchema } from "../schema-check";

/** `true` only when T has none of the keys K. */
type Lacks<T, K extends PropertyKey> = [Extract<keyof T, K>] extends [never] ? true : false;
type TinKey = "tin" | "ssn" | "ein" | "itin" | "taxpayer_id" | "tin_last4";
type WallKey = "hidden_by_wall" | "hidden_count" | "walled_count";

// Compile-time contract: no TIN in a list row, no wall count anywhere in the envelopes, and no
// single_audit catalogue code (D10). Each line fails `tsc` if the generated types change.
const ROW_HAS_NO_TIN: Lacks<ClientRowOut, TinKey> = true;
const CLIENT_PAGE_HAS_NO_WALL: Lacks<ListPageClientRowOut, WallKey> = true;
const ENGAGEMENT_PAGE_HAS_NO_WALL: Lacks<EngagementIndexPage, WallKey> = true;
const NO_SINGLE_AUDIT: "single_audit" extends EngagementTypeEntryOut["code"] ? false : true = true;
const MASKED_KEYS: Lacks<MaskedTinOut, "value" | "tin" | "full"> = true;

const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

// ---- CLI-01 a: the first page, 184 clients at E0 (DEC-47) --------------------------------------

const ridgeline: ClientRowOut = {
  id: id(1),
  name: "Ridgeline Property Partners, LP",
  kind: "business",
  status: "active",
  entity_count: 1,
  service_lines: ["tax", "advisory"],
  is_attest_client: false,
  office_id: id(2),
  office_name: "New York",
  relationship_partner_id: id(3),
  relationship_partner_initials: "DR",
  portal_status: "active",
  open_request_count: 5,
  allowed_actions: [],
};
const northwind: ClientRowOut = {
  ...ridgeline,
  id: id(4),
  name: "Northwind Robotics, Inc.",
  entity_count: 2,
  service_lines: ["audit"],
  is_attest_client: true,
  open_request_count: 13, // 24 − 11 received
};
const CLI01_A: ListPageClientRowOut = {
  items: [ridgeline, northwind],
  next_cursor: "opaque",
  total: 184,
  total_capped: false,
  counts: { active: 184 },
  facets: {},
};
// CLI-01 c: Lena Park, walled from Ashford: the same keys, one fewer in the total.
const CLI01_C: ListPageClientRowOut = { ...CLI01_A, total: 183, counts: { active: 183 } };

// ---- CLI-02 a: the record, EIN masked XX-XXX0287 ------------------------------------------------

const EIN_0287: MaskedTinOut = { kind: "ein", presence: "on_file", last4: "0287" };
const CLI02_A: ClientRecordOut = {
  id: id(1),
  name: "Ridgeline Property Partners, LP",
  kind: "business",
  status: "active",
  is_attest_client: false,
  portal_status: "active",
  entities: [{ id: id(5), name: "Ridgeline Property Partners, LP", tin: EIN_0287 }],
  active_engagements: [],
  tab_counts: { engagements: 2, relationships: 0, contacts: 5, messages: 1 },
  version: 1,
  allowed_actions: [],
};
const REVEAL: TinRevealOut = {
  entity_id: id(5),
  kind: "ein",
  value: "00-0000287",
  remask_after_seconds: 10,
};

// ---- ENG-01 b: Letter │ Not signed, the Accepted tile ------------------------------------------

const ENG01_B: EngagementIndexPage = {
  items: [
    {
      id: id(10),
      name: "2026 Close (from Oct)",
      client_id: id(11),
      client_name: "Bluestem Analytics, LLC",
      client_entity_id: id(12),
      type: "cas_monthly_close",
      service_line: "cas",
      status: "accepted",
      fiscal_period_start: "2026-10-01",
      fiscal_period_end: "2026-12-31",
      letter: {
        status: "not_signed",
        last_event: "viewed",
        last_event_on: "2026-09-11",
        signed_count: 0,
        signer_count: 2,
      },
      allowed_actions: [],
    },
  ],
  next_cursor: null,
  total: 4,
  total_capped: false,
  counts: { accepted: 4 },
  facets: { service_line: [{ value: "cas", label: "CAS", n: 1 }] },
  summary: { prospect: 1, awaiting_letter: 4, past_due: 2 },
};

// ---- ENG-02 b: Northwind 401(k) PY2025 EBP Audit, G1–G3 met, G4 blocked ------------------------

const GATES: EngagementGateOut[] = [
  { gate: "G1", met: true, blockers: [] },
  { gate: "G2", met: true, blockers: [] },
  { gate: "G3", met: true, blockers: [] },
  { gate: "G4", met: false, blockers: [{ type: "work_item", id: id(20), reason_code: "open" }] },
];

// ---- ENG-03: the catalogue (Tax 8 · Audit & assurance 8 · CAS & Advisory 2) --------------------

const STEPS: EngagementTypeEntryOut["steps"] = [{ step: "client_type", field_codes: ["client"] }];
const entry = (
  code: EngagementTypeEntryOut["code"],
  engagement_type: EngagementTypeEntryOut["engagement_type"],
  family: EngagementTypeEntryOut["family"],
  work_item_kind: EngagementTypeEntryOut["work_item_kind"],
  label: string,
  standard_line: string,
  entitlement: EngagementTypeEntryOut["entitlement"] = null,
): EngagementTypeEntryOut => ({
  code,
  engagement_type,
  family,
  work_item_kind,
  label,
  standard_line,
  availability: entitlement === null ? "available" : "needs_entitlement",
  entitlement,
  steps: STEPS,
});
const CATALOGUE: EngagementTypeCatalogueOut = {
  items: [
    entry("form_1040", "tax_compliance", "tax", "tax_return", "Form 1040", "Individual"),
    entry("form_1041", "tax_compliance", "tax", "tax_return", "Form 1041", "Trust or estate"),
    entry("form_1065", "tax_compliance", "tax", "tax_return", "Form 1065", "Partnership"),
    entry("form_1120s", "tax_compliance", "tax", "tax_return", "Form 1120-S", "S corporation"),
    entry("form_1120", "tax_compliance", "tax", "tax_return", "Form 1120", "C corporation"),
    entry("form_990", "tax_compliance", "tax", "tax_return", "Form 990", "Exempt organization"),
    entry(
      "forms_706_709",
      "tax_compliance",
      "tax",
      "tax_return",
      "Forms 706 / 709",
      "Estate & gift",
    ),
    entry(
      "notice_response",
      "notice_response",
      "tax",
      "notice",
      "Notice response",
      "IRS or state notice",
    ),
    entry(
      "ebp_audit",
      "ebp_audit",
      "audit_assurance",
      "assurance",
      "EBP audit",
      "AU-C 703 · ERISA",
    ),
    entry("fs_audit", "fs_audit", "audit_assurance", "assurance", "FS audit", "GAAS nonissuer"),
    entry("review", "review", "audit_assurance", "assurance", "Review", "AR-C 90"),
    entry("compilation", "compilation", "audit_assurance", "assurance", "Compilation", "AR-C 80"),
    entry("preparation", "preparation", "audit_assurance", "assurance", "Preparation", "AR-C 70"),
    entry(
      "agreed_upon_procedures",
      "agreed_upon_procedures",
      "audit_assurance",
      "assurance",
      "Agreed-upon procedures",
      "AT-C 215",
    ),
    entry("soc1", "soc1", "audit_assurance", "assurance", "SOC 1", "AT-C 320", "attest"),
    entry("soc2", "soc2", "audit_assurance", "assurance", "SOC 2", "AT-C 205", "attest"),
    entry(
      "cas_monthly_close",
      "cas_monthly_close",
      "cas_advisory",
      "close",
      "Monthly close",
      "Client accounting services",
    ),
    entry(
      "advisory",
      "advisory",
      "cas_advisory",
      "advisory_project",
      "Advisory project",
      "Scoped project",
    ),
  ],
};
// A draft may name any code string; single_audit is the server's 422 unknown_engagement_type.
const SINGLE_AUDIT_DRAFT: EngagementDraftIn = { type_code: "single_audit", step: "client_type" };

describe("clients v1 consumer frames", () => {
  it("hold the compile-time rules", () => {
    expect([ROW_HAS_NO_TIN, CLIENT_PAGE_HAS_NO_WALL, ENGAGEMENT_PAGE_HAS_NO_WALL]).toEqual([
      true,
      true,
      true,
    ]);
    expect([NO_SINGLE_AUDIT, MASKED_KEYS]).toEqual([true, true]);
  });

  it("CLI-01 a and c are the P-36 envelope, with no wall count (DEC-43)", () => {
    expect(validateSchema("ListPage_ClientRowOut_", CLI01_A)).toEqual([]);
    expect(validateSchema("ListPage_ClientRowOut_", CLI01_C)).toEqual([]);
    expect(Object.keys(CLI01_C).sort()).toEqual(Object.keys(CLI01_A).sort());
    expect(CLI01_A.total - CLI01_C.total).toBe(1);
  });

  it("CLI-02 a masks the EIN to four digits and only the reveal carries the value", () => {
    expect(validateSchema("ClientRecordOut", CLI02_A)).toEqual([]);
    expect(validateSchema("TinRevealOut", REVEAL)).toEqual([]);
    expect(EIN_0287.last4).toMatch(/^[0-9]{4}$/); // the pattern itself is held by the pytest half
    expect(validateSchema("MaskedTinOut", { ...EIN_0287, value: "00-0000287" })).not.toEqual([]);
    expect(validateSchema("MaskedTinOut", { ...EIN_0287, kind: "tin" })).not.toEqual([]);
    expect(validateSchema("ClientRowOut", { ...ridgeline, tin: EIN_0287 })).not.toEqual([]);
  });
});

describe("engagements v2 consumer frames", () => {
  it("ENG-01 b is the envelope with the summary line", () => {
    expect(validateSchema("EngagementIndexPage", ENG01_B)).toEqual([]);
    expect(ENG01_B.items.every((row) => row.status === "accepted")).toBe(true);
    expect(validateSchema("EngagementIndexPage", { ...ENG01_B, hidden_by_wall: 1 })).not.toEqual(
      [],
    );
  });

  it("ENG-02 b gates are G1–G3 met and G4 blocked", () => {
    for (const gate of GATES) expect(validateSchema("EngagementGateOut", gate)).toEqual([]);
  });

  it("ENG-03 catalogue: 18 cards, 8 · 8 · 2, no single_audit", () => {
    expect(validateSchema("EngagementTypeCatalogueOut", CATALOGUE)).toEqual([]);
    const families = CATALOGUE.items.map((item) => item.family);
    expect(families.filter((f) => f === "tax")).toHaveLength(8);
    expect(families.filter((f) => f === "audit_assurance")).toHaveLength(8);
    expect(families.filter((f) => f === "cas_advisory")).toHaveLength(2);
    expect(CATALOGUE.items.map((item) => item.code)).not.toContain("single_audit");
    const singleAudit = { ...CATALOGUE.items[0], code: "single_audit" };
    expect(validateSchema("EngagementTypeEntryOut", singleAudit)).not.toEqual([]);
  });

  it("a single_audit draft passes the schema: the refusal is the server's 422", () => {
    expect(validateSchema("EngagementDraftIn", SINGLE_AUDIT_DRAFT)).toEqual([]);
  });
});
