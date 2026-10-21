// F-04-T05 · the interim seed: footings from the plan row ("46 of 46 seats, 184 clients, 27
// audits, Northwind PBC 11 of 24 and the Feld 2025 Binder"), SPEC-307 AC-1 to AC-4, determinism,
// the generated API types at run time, and the status registry (C2, DEC-122).
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateSchema } from "./schema-check";
import { buildSeed, getSeed } from "./seed";
import { SEATS } from "./seed/people";

const seed = getSeed();
const byType = (type: string) => seed.engagements.filter((e) => e.type === type).length;
const audits = seed.engagements.filter((e) => e.service_line === "audit");

function phaseOf(engagementId: string): string | null {
  return seed.workItems[engagementId]?.[0]?.phase ?? null;
}

function count<T>(rows: readonly T[], pick: (row: T) => string | null): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows) {
    const key = pick(row) ?? "none";
    out[key] = (out[key] ?? 0) + 1;
  }
  return out;
}

describe("firm and seats", () => {
  it("is Brightwater Hale LLP, synthetic, with no scenario name suffixed", () => {
    expect(seed.firm.name).toBe("Brightwater Hale LLP");
    expect(seed.firm.synthetic).toBe(true);
    expect(JSON.stringify(seed)).not.toContain("(Synthetic)");
    expect(seed.clock.instant).toBe("2026-09-14T09:24:00-05:00");
  });

  it("holds 46 of 46 seats: 14 named, 22 / 14 / 10 by office", () => {
    expect(seed.staff).toHaveLength(46);
    expect(seed.members).toHaveLength(46);
    expect(new Set(seed.staff.map((s) => s.user_id)).size).toBe(46);
    expect(SEATS.filter((s) => s.named)).toHaveLength(14);
    expect(count(SEATS, (s) => s.office)).toEqual({ Chicago: 22, Denver: 14, "New York": 10 });
    expect(
      count(
        SEATS.filter((s) => s.named),
        (s) => s.office,
      ),
    ).toEqual({
      Chicago: 7,
      Denver: 4,
      "New York": 3,
    });
  });

  it("matches the ADM-02 role templates and tallies", () => {
    expect(count(SEATS, (s) => s.role)).toEqual({
      Partner: 7,
      Manager: 4,
      "Tax Reviewer": 6,
      Senior: 8,
      Staff: 8,
      "Tax Preparer": 11,
      "Firm Admin": 1,
      "IT / Security": 1,
    });
    expect(SEATS.filter((s) => s.seasonal)).toHaveLength(5);
  });
});

describe("clients", () => {
  it("holds 184: 16 named, 66 roster, 102 filler", () => {
    expect(seed.clients).toHaveLength(184);
    expect(seed.firmClients).toHaveLength(184);
    expect(count(seed.clients, (c) => c.origin)).toEqual({ named: 16, roster: 66, filler: 102 });
    expect(new Set(seed.clients.map((c) => c.name.toLowerCase())).size).toBe(184);
    expect(new Set(seed.firmClients.map((c) => c.client_id)).size).toBe(184);
  });

  it("lists the 16 featured clients first, in CLI-01 order", () => {
    expect(seed.firmClients.slice(0, 3).map((c) => c.name)).toEqual([
      "Jonah & Claire Feld",
      "Copperleaf Coffee Roasters, Inc.",
      "Meera Shah",
    ]);
    expect(seed.clients.slice(0, 16).every((c) => c.origin === "named")).toBe(true);
  });

  it("flags attest only on the three featured audit and review clients", () => {
    const featured = seed.clients.slice(0, 16).filter((c) => c.attest);
    expect(featured.map((c) => c.name)).toEqual([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Lakeshore Literacy Alliance",
    ]);
  });

  it("gives Northwind, Granite Peak and the Thornbury estate two entities, everyone else one", () => {
    const two = seed.clients.filter((c) => c.entities.length === 2).map((c) => c.name);
    expect(two).toEqual([
      "Northwind Robotics, Inc.",
      "Granite Peak Outdoor Supply, Inc.",
      "Estate of Walter Thornbury",
    ]);
    expect(seed.clients.every((c) => c.entities.length >= 1 && c.entities.length <= 2)).toBe(true);
  });

  it("never reuses a canonical surname or word in a filler client", () => {
    const canonical = new Set<string>();
    const words = (text: string) =>
      text
        .toLowerCase()
        .split(/[^a-z]+/)
        .filter((w) => w.length >= 3);
    const generic = new Set(
      "inc llc llp pc lp the and plan trust family estate partners holdings foundation group company".split(
        " ",
      ),
    );
    for (const c of seed.clients.filter((x) => x.origin !== "filler")) {
      for (const w of words(c.name)) if (!generic.has(w)) canonical.add(w);
    }
    for (const s of SEATS) for (const w of words(s.name)) canonical.add(w);
    for (const c of seed.clients.filter((x) => x.origin === "filler")) {
      const clash = words(c.name).filter((w) => canonical.has(w));
      expect(clash, c.name).toEqual([]);
    }
  });

  it("holds out Fairhaven Foods and its engagement (183 clients, 26 audits) for J02-audit-core", () => {
    const held = buildSeed({ holdouts: ["fairhaven_ebp"] });
    expect(held.clients).toHaveLength(183);
    expect(held.engagements.filter((e) => e.service_line === "audit")).toHaveLength(26);
    expect(held.clients.some((c) => c.name.startsWith("Fairhaven"))).toBe(false);
    expect(buildSeed({ holdouts: ["copperleaf"] }).clients).toHaveLength(183);
  });

  it("has no client for the empty-state searches (Schwab, Harbor Lane)", () => {
    const names = seed.clients.map((c) => c.name.toLowerCase());
    expect(names.some((n) => n.includes("schwab") || n.includes("harbor lane"))).toBe(false);
  });
});

describe("audits and assurance", () => {
  it("holds 27: EBP 14 · FS 6 · Review 4 · Compilation and preparation 3", () => {
    expect(audits).toHaveLength(27);
    expect(byType("ebp_audit")).toBe(14);
    expect(byType("fs_audit")).toBe(6);
    expect(byType("review")).toBe(4);
    expect(byType("compilation") + byType("preparation")).toBe(3);
  });

  it("stands at Planning 7 · Fieldwork 9 · In review 6 · Ready to release 2 · Released 3", () => {
    expect(count(audits, (e) => phaseOf(e.id))).toEqual({
      planning: 7,
      fieldwork: 9,
      in_review: 6,
      ready_to_release: 2,
      released: 3,
    });
  });

  it("holds four letters out at E0 across the firm; two sit in this slice, at Accepted with G3 unmet", () => {
    const accepted = audits.filter((e) => e.status === "accepted");
    expect(accepted.map((e) => e.client_name)).toEqual([
      "Granite Peak Outdoor Supply, Inc.",
      "Fairhaven Foods 401(k) Plan",
    ]);
    for (const e of accepted) {
      const g3 = e.gates?.find((g) => g.gate === "G3");
      expect(g3).toEqual({ gate: "G3", met: false, blockers: ["engagement_letter"] });
    }
    const unmet = seed.engagements.flatMap((e) => (e.gates ?? []).filter((g) => !g.met));
    expect(unmet).toHaveLength(2);
  });

  it("requires G1 to G3 on attest types, G1 and G3 on the others (gate_policy)", () => {
    for (const e of seed.engagements) {
      const gates = (e.gates ?? []).map((g) => g.gate);
      const attest = ["fs_audit", "ebp_audit", "review"].includes(e.type);
      expect(gates, e.name).toEqual(attest ? ["G1", "G2", "G3"] : ["G1", "G3"]);
    }
  });

  it("gives every audit one assurance work item, archived exactly when the engagement is", () => {
    for (const e of audits) {
      const items = seed.workItems[e.id] ?? [];
      expect(items).toHaveLength(1);
      expect(items[0]?.kind).toBe("assurance");
      expect(items[0]?.status).toBe(e.status === "archived" ? "archived" : "active");
    }
    expect(audits.filter((e) => e.status === "archived")).toHaveLength(2);
  });

  it("puts Northwind's team on the cockpit rail (MO · TW · HL · MD · AC)", () => {
    const northwind = seed.engagements.find((e) => e.id === seed.engagementIds.A1);
    expect(northwind?.client_entity_name).toBe("Northwind Robotics 401(k) Plan");
    expect(northwind?.team.map((m) => m.display_name)).toEqual([
      "Margaret Okonkwo",
      "Hannah Leclerc",
      "Marcus Delaney",
      "Ana Cruz",
      "Thomas Whitcombe",
    ]);
    expect(seed.workItems[seed.engagementIds.A1 ?? ""]?.[0]?.due_on).toBe("2026-10-09");
  });
});

describe("request lists", () => {
  const northwind = seed.requestItems[seed.engagementIds.A1 ?? ""] ?? [];

  it("reads Northwind's PBC as 11 of 24 received, 1 to review, 12 requested", () => {
    expect(northwind).toHaveLength(24);
    expect(count(northwind, (r) => r.status)).toEqual({
      received: 11,
      uploaded: 1,
      requested: 12,
    });
    // CLI-01: Northwind's 13 open requests = 24 - 11 received.
    expect(northwind.filter((r) => r.status !== "received")).toHaveLength(13);
  });

  it("reads Northwind's PBC groups as 3 of 5 · 4 of 6 · 3 of 7 · 1 of 4 · 0 of 1 · 0 of 1", () => {
    const groups: Record<string, [number, number]> = {};
    for (const r of northwind) {
      const g = groups[r.audit_area] ?? [0, 0];
      groups[r.audit_area] = [g[0] + (r.status === "received" ? 1 : 0), g[1] + 1];
    }
    expect(Object.values(groups)).toEqual([
      [3, 5],
      [4, 6],
      [3, 7],
      [1, 4],
      [0, 1],
      [0, 1],
    ]);
  });

  it("leaves a client-assignee on the requests the portal users answer", () => {
    const dana = seed.portalUsers.find((u) => u.name === "Dana Kowalski");
    const sam = seed.portalUsers.find((u) => u.name === "Sam Ortiz");
    expect(northwind.filter((r) => r.client_assignee_user_id === dana?.id).length).toBeGreaterThan(
      0,
    );
    expect(northwind.filter((r) => r.client_assignee_user_id === sam?.id).length).toBeGreaterThan(
      0,
    );
  });

  it("holds Granite Peak's FS PBC at 41 requests, all draft until the letter is signed", () => {
    const granite = seed.requestItems[seed.engagementIds.A2 ?? ""] ?? [];
    expect(granite).toHaveLength(41);
    expect(granite.every((r) => r.status === "draft" && r.client_visible === false)).toBe(true);
  });

  it("holds the Feld 2025 Binder at 7 requests: 5 of 7 received, 2 open", () => {
    const feld = seed.requestItems[seed.engagementIds.feld ?? ""] ?? [];
    expect(feld).toHaveLength(7);
    expect(count(feld, (r) => r.status)).toEqual({ received: 5, requested: 2 });
    expect(feld.filter((r) => r.status === "requested").map((r) => r.audit_area)).toEqual([
      "Health & Medical",
      "Other Activity",
    ]);
    const engagement = seed.engagements.find((e) => e.id === seed.engagementIds.feld);
    expect(engagement?.client_name).toBe("Jonah & Claire Feld");
    expect(seed.workItems[engagement?.id ?? ""]?.[0]).toMatchObject({
      kind: "tax_return",
      phase: null,
    });
  });
});

describe("determinism", () => {
  it("builds the same seed twice, byte for byte", () => {
    expect(JSON.stringify(buildSeed())).toBe(JSON.stringify(buildSeed()));
    expect(buildSeed()).toEqual(buildSeed());
  });

  it("derives ids from labels, so a holdout does not reshuffle the others", () => {
    const held = buildSeed({ holdouts: ["fairhaven_ebp"] });
    expect(held.engagementIds.A1).toBe(seed.engagementIds.A1);
    expect(held.firmClients.find((c) => c.name === "Meera Shah")?.client_id).toBe(
      seed.firmClients.find((c) => c.name === "Meera Shah")?.client_id,
    );
  });

  it("reads neither Math.random nor the wall clock", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    const sources = [
      ...readdirSync(join(dir, "seed")).map((f) => join(dir, "seed", f)),
      join(dir, "handlers.ts"),
      join(dir, "scenario.ts"),
      join(dir, "install.ts"),
    ].filter((f) => !f.endsWith(".test.ts"));
    for (const file of sources) {
      const text = readFileSync(file, "utf8");
      expect(text, file).not.toMatch(/Math\.random|Date\.now|performance\.now|new Date\(\)/);
    }
  });
});

describe("generated types at run time", () => {
  it("validates every engagement, summary, work item and request against its schema", () => {
    for (const e of seed.engagements)
      expect(validateSchema("EngagementOut", e), e.name).toEqual([]);
    for (const s of seed.summaries)
      expect(validateSchema("EngagementSummaryOut", s), s.name).toEqual([]);
    for (const items of Object.values(seed.workItems)) {
      for (const w of items) expect(validateSchema("WorkItemOut", w), w.name).toEqual([]);
    }
    for (const items of Object.values(seed.requestItems)) {
      for (const r of items)
        expect(validateSchema("RequestItemOut", r), r.description).toEqual([]);
    }
  });

  it("validates the people, clients and contacts too", () => {
    for (const s of seed.staff)
      expect(validateSchema("StaffMemberOut", s), s.display_name).toEqual([]);
    for (const m of seed.members)
      expect(validateSchema("FirmMemberOut", m), m.display_name).toEqual([]);
    for (const c of seed.firmClients)
      expect(validateSchema("FirmClientOut", c), c.name).toEqual([]);
    for (const list of Object.values(seed.contacts)) {
      for (const c of list) expect(validateSchema("ClientContactOut", c)).toEqual([]);
    }
  });

  it("makes the validator able to fail (a bad status, a bad uuid, a field the schema lacks)", () => {
    const first = seed.engagements[0];
    if (first === undefined) throw new Error("no engagement");
    expect(validateSchema("EngagementOut", { ...first, status: "open" })).not.toEqual([]);
    expect(validateSchema("EngagementOut", { ...first, id: "not-a-uuid" })).not.toEqual([]);
    expect(validateSchema("EngagementOut", { ...first, office: "Chicago" })).not.toEqual([]);
  });
});

describe("status words come from the registry", () => {
  it("uses only current engagement, request and phase words", () => {
    const engagement = Object.keys(STATUS_REGISTRY.engagement);
    const request = Object.entries(STATUS_REGISTRY.request)
      .filter(([, word]) => !(word as { derived: boolean }).derived)
      .map(([code]) => code);
    const phases = Object.keys(STATUS_REGISTRY.audit_engagement);
    for (const e of seed.engagements) expect(engagement).toContain(e.status);
    for (const items of Object.values(seed.requestItems)) {
      for (const r of items) expect(request).toContain(r.status);
    }
    for (const items of Object.values(seed.workItems)) {
      for (const w of items) if (w.phase !== null) expect(phases).toContain(w.phase);
    }
  });

  it("uses none of the retired request words", () => {
    const statuses = new Set(
      Object.values(seed.requestItems).flatMap((l) => l.map((r) => r.status)),
    );
    for (const retired of ["open", "needs_revision", "ready_for_review", "accepted"]) {
      expect(statuses.has(retired as never)).toBe(false);
    }
  });
});

describe("reserved ranges and the sink", () => {
  const text = JSON.stringify(seed);

  it("carries no SSN-, EIN- or nine-digit-shaped value", () => {
    expect(text).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/);
    expect(text).not.toMatch(/\b\d{2}-\d{7}\b/);
    // Ids are random-looking hex; they are not identifiers, so leave them out of the digit scan.
    const withoutIds = text.replace(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g,
      "",
    );
    expect(withoutIds).not.toMatch(/(?<!\d)\d{9}(?!\d)/);
  });

  it("puts every mailbox on the firm domain or the synthetic sink", () => {
    const emails = text.match(/[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+/g) ?? [];
    expect(emails.length).toBeGreaterThan(46);
    for (const email of emails) {
      expect(email, email).toMatch(/@(brightwaterhale\.com|sink\.brightwaterhale\.test)$/);
    }
  });

  it("holds money as decimal strings", () => {
    for (const value of Object.values(seed.figures.northwind)) {
      expect(typeof value).toBe("string");
      expect(value).toMatch(/^\d+\.\d{2}$/);
    }
    expect(seed.figures.northwind.netAssetsUnadjusted).toBe("16812400.00");
  });
});
