// W-01-T03 (SPEC-659 AC-1 to AC-3, AC-6, AC-20, AC-23): the Connect fixtures foot, and the front
// end's catalogue copy is the scenario's (one content document, two readers).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { E2, cchDetail, connectCatalog } from "../seed/connect";
import { wb10Scenarios, wb11Scenarios } from "../scenarios/connect";

const here = dirname(fileURLToPath(import.meta.url));
const BACKEND_COPY = join(
  here,
  "../../../../../backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/files/connect_catalog.json",
);

describe("Connect fixtures", () => {
  it("AC-1: 53 = 9 + 38 + 6 with the category totals and the nine connected", () => {
    const a = connectCatalog();
    expect(a.counts).toEqual({ all: 53, connected: 9, available: 38, coming_soon: 6 });
    expect(Object.fromEntries(a.categories.map((c) => [c.code, c.count]))).toEqual({
      tax: 8,
      practice: 5,
      erp: 8,
      docs: 13,
      comms: 8,
      prod: 12,
      crm: 3,
      hris: 3,
      spend: 5,
    });
    expect(a.items.filter((t) => t.status === "connected").map((t) => t.name)).toEqual([
      "CCH Axcess Tax",
      "CCH Axcess Practice",
      "QuickBooks Online",
      "NetSuite",
      "Sage Intacct",
      "Xero",
      "Box",
      "Microsoft 365",
      "DocuSign",
    ]);
  });

  it("AC-2: ERP 8, Connected 9, Karbon 1; category counts stay catalogue totals", () => {
    expect(connectCatalog({ category: "erp" }).items).toHaveLength(8);
    expect(connectCatalog({ status: "connected" }).items).toHaveLength(9);
    const karbon = connectCatalog({ q: "Karbon" });
    expect(karbon.items.map((t) => t.name)).toEqual(["Karbon"]);
    expect(karbon.categories.find((c) => c.code === "tax")?.count).toBe(8);
  });

  it("AC-3: 55 = 9 + 40 + 6 at E2 with GRC & Compliance 2; neither row at E0", () => {
    const h = connectCatalog({ at: E2 });
    expect(h.counts).toEqual({ all: 55, connected: 9, available: 40, coming_soon: 6 });
    expect(connectCatalog({ at: E2, category: "grc" }).items.map((t) => t.name)).toEqual([
      "Drata",
      "Vanta",
    ]);
    expect(connectCatalog().items.some((t) => t.key === "drata")).toBe(false);
  });

  it("AC-6: Hannah sees firm tiles managed by Felix and her own personal tiles", () => {
    const d = connectCatalog({ viewer: "hannah-leclerc" });
    const ultratax = d.items.find((t) => t.key === "ultratax");
    expect(ultratax?.blocked_reason).toBe("Felix Andersen manages firm connections.");
    expect(ultratax?.allowed_actions).toEqual([]);
    expect(d.items.find((t) => t.key === "box")?.allowed_actions).toEqual([
      "integration.disconnect_personal",
    ]);
  });

  it("AC-20, AC-23: CCH detail has 5 events and 5 agents; file bridge has no token row", () => {
    const a = cchDetail("a");
    expect(a.health.events).toHaveLength(5);
    expect(a.dependents.count).toBe(5);
    expect(a.connection.linked_count).toBe(224);
    const bridge = cchDetail("file_bridge");
    expect(bridge.connection.auth_mode_label).toBe("File bridge · a person exports and imports");
    expect(bridge.connection.token_renews_at).toBeNull();
    expect(cchDetail("c").status_line).toBe(
      "Token expired at 9:00 AM · 1 run failed · 5 agents paused",
    );
  });

  it("every artboard has a scenario: WB-10 a–i and WB-11 a–f", () => {
    expect(Object.keys(wb10Scenarios).sort().join("")).toBe("abcdefghi");
    expect(Object.keys(wb11Scenarios).sort().join("")).toBe("abcdef");
  });

  it("the front end's catalogue is the scenario's document", () => {
    const front = readFileSync(join(here, "../seed/connect-catalog.json"), "utf8");
    expect(JSON.parse(front)).toEqual(JSON.parse(readFileSync(BACKEND_COPY, "utf8")));
  });
});
