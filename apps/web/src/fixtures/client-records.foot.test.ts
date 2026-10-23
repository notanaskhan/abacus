// CLI-02's figures foot (P-07-T19; docs/screens/CLI-02.md, Figures): every figure the README and
// revision call out, from the seed's own records with bigint decimals, never floats.
import { describe, expect, it } from "vitest";
import { daysUntil, itemOf, sectionOf, sumFigures } from "../domain/clients";
import { getSeed } from "./seed";
import { FELD, GRANITE_PEAK, NORTHWIND, RIDGELINE, clientRecords } from "./seed/client-records";
import { DEMO_INSTANT } from "./seed/clock";

const records = clientRecords(getSeed());
const TZ = "America/Chicago";
const E0 = new Date(DEMO_INSTANT);

describe("CLI-02 figures", () => {
  const a = records[RIDGELINE];
  const k1 = sectionOf(a.overview, "k1_packages")?.items ?? [];
  const stats = sectionOf(a.overview, "stats");

  it("K-1 box 2 (a): 24,632 + 468,008 + 400,270 + 30,790 + 307,900 = 1,231,600 = Schedule K", () => {
    expect(k1.map((i) => i.figure)).toEqual(["24632", "468008", "400270", "30790", "307900"]);
    expect(sumFigures(k1.map((i) => i.figure ?? "0"))).toBe("1231600");
  });

  it("K-1s shared (a): 2 of 5 = the Feld and Shah hand-offs of the 5 packages", () => {
    const handedOff = k1.filter((i) => i.ref != null);
    expect(handedOff.map((i) => i.text)).toEqual(["Meera Shah", "Jonah Feld"]);
    expect(itemOf(stats, "k1_shared")?.figure).toBe(String(handedOff.length));
    expect(itemOf(stats, "k1_shared.of")?.figure).toBe(String(k1.length));
  });

  it("Requests (a): 5 pending = the 5 waiting on client", () => {
    const waiting = sectionOf(a.overview, "waiting_on_client");
    expect(itemOf(sectionOf(a.overview, "portal"), "requests")?.figure).toBe("5");
    expect(itemOf(stats, "waiting_on_client")?.figure).toBe("5");
    expect(waiting?.total).toBe(5);
  });

  it("Contacts (a): Contacts & access 5 = Portal 5 identities; engagements 2", () => {
    expect(a.record.tab_counts.contacts).toBe(5);
    expect(a.record.tab_counts.engagements).toBe(a.record.active_engagements?.length);
  });

  it("Due (a): 1 day from Mon Sep 14 to Sep 15; Feld (b): 31 days to Oct 15", () => {
    expect(daysUntil(itemOf(stats, "days_to_due")?.on ?? "", E0, TZ)).toBe(1);
    const b = sectionOf(records[FELD].overview, "stats");
    expect(daysUntil(itemOf(b, "days_to_due")?.on ?? "", E0, TZ)).toBe(31);
  });

  it("Northwind (c): PBC 11 of 24, from the seed's own request list (CLI-01 open 13 = 24 − 11)", () => {
    const c = sectionOf(records[NORTHWIND].overview, "stats");
    expect(itemOf(c, "pbc_received")?.figure).toBe("11");
    expect(itemOf(c, "pbc_received.of")?.figure).toBe("24");
  });

  it("Granite Peak (f): 48% against 63%, 3 overdue", () => {
    const f = sectionOf(records[GRANITE_PEAK].overview, "responsiveness");
    expect(itemOf(f, "on_time_rate")?.figure).toBe("48");
    expect(itemOf(f, "firm_rate")?.figure).toBe("63");
    expect(itemOf(f, "overdue_now")?.figure).toBe("3");
  });

  it("no TIN in any record payload beyond its last four (masked only)", () => {
    for (const r of Object.values(records)) {
      const text = JSON.stringify(r.record);
      expect(text).not.toContain("00-0000287");
      expect(text).not.toContain("000-00-2208");
    }
  });
});
