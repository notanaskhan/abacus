// A-01-T03: audits family consumer fixture assertions for AUD-01, AUD-02 and AUD-03
// (docs/contracts/audits-cockpit.md). Each fixture is typed with the generated client, so a
// breaking change fails `tsc`, and checked against the OpenAPI document at run time. The index
// envelope foots its tiles to `total`, keeps the other tiles' counts while one is pressed (P-36
// counts minus the active tile), carries no hidden count and no amount, and uses only registry
// codes. Brightwater Hale, synthetic. The pytest half is backend/tests/contracts/audits/.
import type {
  AuditEngagementStatus,
  AuditIndexPage,
  AuditIndexRowOut,
  AuditSectionStatus,
  EvidenceScreeningStatus,
  RequestStatus,
  SourceDocumentsOut,
} from "@abacus/api-client";
import { type EnumCovered, STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";
import { buildSeed } from "../seed";
import { auditIndexPage, auditIndexRows, sourceDocuments } from "../seed/audits-index";

/** Every key of T and of every object type nested in it. */
type DeepKeys<T> = T extends readonly (infer U)[]
  ? DeepKeys<U>
  : T extends object
    ? { [K in keyof T & string]: K | DeepKeys<NonNullable<T[K]>> }[keyof T & string]
    : never;
// A hidden count, an amount, materiality or a severity, by field name (INV-3, AUD-01 AVOID).
type Forbidden =
  | `${string}hidden${string}`
  | `${string}walled${string}`
  | "amount"
  | `${string}_amount`
  | `${string}materiality${string}`
  | `${string}severity${string}`;
type Clean<T> = [Extract<DeepKeys<T>, Forbidden>] extends [never] ? true : false;
const indexClean: Clean<AuditIndexPage> = true;
const sourceClean: Clean<SourceDocumentsOut> = true;

// The generated enums are exactly the registry's objects (C2).
const phasesCovered: EnumCovered<"audit_engagement", AuditEngagementStatus> = true;
const sectionsCovered: EnumCovered<"audit_section", AuditSectionStatus> = true;
const requestsCovered: EnumCovered<"request", RequestStatus> = true;
const screeningCovered: EnumCovered<"evidence_screening", EvidenceScreeningStatus> = true;

const TODAY = "2026-09-14"; // E0, Mon Sep 14, 2026 (the demo clock's date)
const seed = buildSeed();
const rows = auditIndexRows(seed.engagements, seed.workItems, TODAY);
const byName = (name: string): AuditIndexRowOut => {
  const row = rows.find((r) => r.name === name);
  if (row === undefined) throw new Error(`no row ${name}`);
  return row;
};
const sum = (counts: Record<string, number>) => Object.values(counts).reduce((a, b) => a + b, 0);

describe("audits contract (A-01-T03): types", () => {
  it("covers the registry and carries no hidden count or amount", () => {
    expect([phasesCovered, sectionsCovered, requestsCovered, screeningCovered]).toEqual([
      true,
      true,
      true,
      true,
    ]);
    expect([indexClean, sourceClean]).toEqual([true, true]);
    expect(Object.keys(STATUS_REGISTRY)).toContain("engagement_export");
  });
});

describe("audits contract (A-01-T03): AUD-01 index envelope", () => {
  const a = auditIndexPage(rows, {}, TODAY);

  it("a: the tiles foot 7 + 9 + 6 + 2 + 3 = 27 and the schema accepts the page", () => {
    expect(validateResponse("get", "/v1/audits", a)).toEqual([]);
    expect(a.counts).toEqual({
      planning: 7,
      fieldwork: 9,
      in_review: 6,
      ready_to_release: 2,
      released: 3,
    });
    expect(sum(a.counts ?? {})).toBe(a.total);
    expect(a.total).toBe(27);
  });

  it("a: the caption is EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3", () => {
    expect(a.summary).toMatchObject({
      ebp: 14,
      fs_audit: 6,
      review: 4,
      compilation_preparation: 3,
    });
  });

  it("a: the segments read Financial statement 6 · EBP 14 · Review & compilation 7", () => {
    const n = Object.fromEntries((a.facets?.segment ?? []).map((f) => [f.value, f.n]));
    expect(n).toEqual({ fs: 6, ebp: 14, review: 7 });
  });

  it("b: pressing Ready to release shows 2 of 27 and keeps every tile's count", () => {
    const b = auditIndexPage(rows, { phase: "ready_to_release" }, TODAY);
    expect(b.items.map((r) => r.name)).toEqual([
      "Cobalt Ridge Manufacturing 401(k) Plan",
      "Halden Health 403(b) Plan",
    ]);
    expect(b.total).toBe(2);
    expect(b.counts).toEqual(a.counts);
    expect(sum(b.counts ?? {})).toBe(27);
  });

  it("c: Report due │ Next 14 days lists Sep 18, 21, 25 and 28 (Fenwick Sep 30 excluded)", () => {
    const c = auditIndexPage(rows, { due: "14d" }, TODAY);
    expect(c.items.map((r) => r.report_due_on).sort()).toEqual([
      "2026-09-18",
      "2026-09-21",
      "2026-09-25",
      "2026-09-28",
    ]);
    expect(sum(c.counts ?? {})).toBe(c.total);
  });

  it("e: a search that matches nothing answers an empty page that still foots", () => {
    const e = auditIndexPage(rows, { q: "Pinecrest" }, TODAY);
    expect(e.items).toEqual([]);
    expect(e.total).toBe(0);
    expect(sum(e.counts ?? {})).toBe(0);
  });

  it("rows: Northwind, Fairhaven (no PBC before G3), Bayside's clock and Meridian archived", () => {
    expect(byName("Northwind Robotics 401(k) Plan")).toMatchObject({
      ebp_plan_kind: "dc",
      limited_scope_103a3c: true,
      period_label: "PY2025",
      pbc: { received: 11, total: 24 },
      partner_initials: "MO",
      manager_initials: "HL",
      office_name: "Chicago",
      report_due_on: "2026-10-09",
    });
    const fairhaven = byName("Fairhaven Foods 401(k) Plan");
    expect(fairhaven.pbc).toBeNull();
    expect(fairhaven.tags?.map((t) => t.text)).toEqual(["Letter sent Sep 8"]);
    expect(byName("Bayside Electric Cooperative 401(k) Plan")).toMatchObject({
      phase: "released",
      released_on: "2026-07-29",
      archive: { state: "archiving", days_left: 13 },
    });
    expect(byName("Meridian Tool & Die, Inc.").archive).toMatchObject({
      state: "archived",
      firm_tool_ref: "CaseWare BH-2025-031",
    });
  });

  it("rows: report-due tones are from the clock and every phase is a tile code", () => {
    expect(byName("Cobalt Ridge Manufacturing 401(k) Plan").report_due_tone).toBe("within_7_days");
    expect(byName("Halden Health 403(b) Plan").report_due_tone).toBe("within_30_days");
    expect(byName("Riverbend Community Theater").report_due_tone).toBe("later");
    const codes = Object.keys(STATUS_REGISTRY.audit_engagement);
    for (const r of rows) expect(codes).toContain(r.phase);
  });

  it("d: the run badge is Run 1 by Marcus Delaney, 1 of 14 workpapers", () => {
    expect(byName("Northwind Robotics 401(k) Plan").run_badge).toMatchObject({
      run_number: 1,
      started_by_name: "Marcus Delaney",
      workpapers_complete: 1,
      workpapers_total: 14,
      blocked_on_role: "partner",
    });
  });

  it("a walled viewer's totals foot without the hidden rows (INV-3)", () => {
    const walled = rows.filter((r) => !r.client_name.startsWith("Granite Peak"));
    const page = auditIndexPage(walled, {}, TODAY);
    expect(page.total).toBe(25);
    expect(sum(page.counts ?? {})).toBe(25);
    expect(JSON.stringify(page)).not.toContain("Granite Peak");
  });
});

describe("audits contract (A-01-T03): AUD-02 and AUD-03 Source Documents", () => {
  const northwind = byName("Northwind Robotics 401(k) Plan");
  const requests = seed.requestItems[northwind.engagement_id] ?? [];
  const docs = sourceDocuments(
    northwind.work_item_id,
    "b0000000-0000-4000-8000-000000000001",
    requests,
    seed.requestOwners,
    TODAY,
  );

  it("foots 24 = 11 received + 1 needs review + 12 requested and the schema accepts it", () => {
    expect(validateResponse("get", "/v1/audits/{work_item_id}/source-documents", docs)).toEqual(
      [],
    );
    expect([docs.total, docs.received, docs.needs_review, docs.requested]).toEqual([
      24, 11, 1, 12,
    ]);
  });

  it("the groups read 3 of 5 · 4 of 6 · 3 of 7 · 1 of 4 · 0 of 1 · 0 of 1", () => {
    expect(docs.groups?.map((g) => `${String(g.received)} of ${String(g.total)}`)).toEqual([
      "3 of 5",
      "4 of 6",
      "3 of 7",
      "1 of 4",
      "0 of 1",
      "0 of 1",
    ]);
  });

  it("every open row names who owes it; requested rows carry no Linked count", () => {
    const open = (docs.groups ?? [])
      .flatMap((g) => g.rows ?? [])
      .filter((r) => r.status === "requested");
    expect(open).toHaveLength(12);
    for (const r of open) {
      expect(r.owed_by?.display).toBeTruthy();
      expect(r.linked_count ?? null).toBeNull();
    }
    expect(new Set(open.map((r) => r.owed_by?.display))).toEqual(
      new Set([
        "Dana Kowalski",
        "Sam Ortiz, Keystone",
        "Harborline Trust Company",
        "PayGrid Payroll",
        "Summit Plan Administrators",
      ]),
    );
  });

  it("g: on Sep 21 the rows due Sep 18 are derived overdue (nothing stored)", () => {
    const late = sourceDocuments(
      northwind.work_item_id,
      "b0000000-0000-4000-8000-000000000001",
      requests,
      seed.requestOwners,
      "2026-09-21",
    );
    const overdue = (late.groups ?? []).flatMap((g) => g.rows ?? []).filter((r) => r.overdue);
    expect(overdue).toHaveLength(9);
    expect(new Set(overdue.map((r) => r.status))).toEqual(new Set(["requested"]));
  });
});
