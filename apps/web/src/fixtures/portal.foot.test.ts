// P-08-T08 seed footing (P-08 §5 "seed footing tests"; POR-01 and POR-02 screen contracts): the
// portal figures from the seed, never restated: Upload 2 = Intake 2, 3 questions = 2 + 1, binder
// 19 of 21 with 37 sorted, Copperleaf 7 of 9, and Keystone's 9 items. Every portal fixture is
// white-label (no product name) and on the synthetic sink domain.
import { describe, expect, it } from "vitest";
import {
  KEYSTONE_DELEGATED,
  NORTHWIND_DELEGATIONS,
  SAM_INVITATION,
  scenarios as por01,
} from "./scenarios/POR-01";
import { feldOpenUploads, scenarios as por02 } from "./scenarios/POR-02";
import { getSeed } from "./seed";
import { COPPERLEAF_CLOSE } from "./seed/client-rows";
import {
  BRIGHTWATER_BRANDING,
  FELD_BINDER,
  PORTAL_SHELLS,
  TESSELLATE_SOC,
  claireHome,
  marisolHome,
  tessHome,
} from "./seed/portal-home";
import { PORTAL_USERS, SINK_DOMAIN } from "./seed/portal";

const seed = getSeed();

describe("POR-02 footing on the seed", () => {
  it("Upload 2 is the Feld binder's Intake 2: its two open requests", () => {
    expect(feldOpenUploads()).toBe(2);
    expect(claireHome(feldOpenUploads()).todos?.[0]).toMatchObject({ kind: "upload", count: 2 });
  });

  it("Answer 3 questions = 2 in the organizer + 1 from the team", () => {
    const answer = claireHome(2).todos?.find((t) => t.kind === "answer");
    expect(answer?.count).toBe(3);
    expect(answer?.facts).toEqual({ organizer_count: 2, from_team_count: 1 });
  });

  it("the binder card reads 19 of 21 requests done and 37 files sorted", () => {
    expect(claireHome(2).binder).toMatchObject({ done: 19, total: 21, sorted_count: 37 });
    expect(FELD_BINDER).toEqual({ done: 19, total: 21, sorted: 37 });
  });

  it("Copperleaf's August close: Requests 7 of 9, and the overdue upload is the 2 left", () => {
    const home = tessHome();
    const close = home.work_cards?.find((c) => c.kind === "close");
    expect(close?.stages?.[0]?.facts).toEqual({ done: 7, total: 9 });
    expect(home.todos?.[0]).toMatchObject({
      state: "overdue",
      count: 9 - 7,
      due_date: "2026-09-05",
    });
    expect(COPPERLEAF_CLOSE).toEqual({ requests: 9, received: 7 });
    // Red only on the past-due to-do (P-08 Story 6.4).
    expect(home.todos?.filter((t) => t.state === "overdue")).toHaveLength(1);
  });

  it("scenarios a, b, c, d, e, f, g, h and M exist with their personas and clocks", () => {
    expect(Object.keys(por02)).toEqual(["a", "b", "c", "d", "e", "f", "g", "h", "M"]);
    expect(por02.b.clock).toBe("2026-02-02T09:04:00-06:00");
    expect(por02.d.persona).toBe("tess-moreno");
    expect(por02.e.persona).toBe("meera-shah");
    expect(por02.g.persona).toBe("luis-ferrante");
    expect(por02.g.clock).toBe("2026-10-22T08:30:00-05:00");
    expect(por02.h.persona).toBe("marisol-vega");
  });

  it("Tessellate (h): 26 open control requests, 3 exceptions, description approved Sep 12 (§9.5)", () => {
    const todos = marisolHome().todos ?? [];
    const of = (kind: string) => todos.find((t) => t.kind === kind);
    expect(of("control_requests")?.count).toBe(TESSELLATE_SOC.openRequests);
    expect(TESSELLATE_SOC.openRequests).toBe(26);
    expect(of("exceptions")?.count).toBe(3);
    expect(of("exceptions")?.facts?.criteria).toBe("CC6.2 · CC8.1 · A1.2");
    expect(of("description_approved")?.facts?.approved_on).toBe("2026-09-12");
  });
});

describe("POR-01 footing on the seed", () => {
  it("d scopes Sam Ortiz to Keystone's 9 Northwind 401(k) requests (= CLI-04 and POR-14)", () => {
    const northwind = seed.requestItems[seed.engagementIds.A1 ?? ""] ?? [];
    expect(NORTHWIND_DELEGATIONS.reduce((a, b) => a + b, 0)).toBe(northwind.length);
    expect(northwind).toHaveLength(24);
    expect(KEYSTONE_DELEGATED).toBe(9);
    expect(SAM_INVITATION.access.item_count).toBe(9);
    expect(SAM_INVITATION.organisation_name).toBe("Keystone Retirement Services");
  });

  it("e's link is 25 days old on Sep 14: past the 14-day life", () => {
    const days =
      (Date.parse(por01.e.clock ?? "") - Date.parse("2026-08-20T14:00:00Z")) / 86_400_000;
    expect(Math.floor(days)).toBe(25);
  });

  it("the personas tess-moreno and marisol-vega exist, on the sink domain", () => {
    for (const slug of ["tess-moreno", "marisol-vega", "claire-feld", "sam-ortiz"]) {
      const person = seed.people.find((p) => p.slug === slug);
      expect(person?.email.endsWith(`@${SINK_DOMAIN}`), slug).toBe(true);
    }
    expect(PORTAL_USERS.find((u) => u.slug === "tess-moreno")?.title).toBe("Owner");
  });

  it("Tess Moreno's owner grant is an entity scope; Claire Feld's household is not", () => {
    expect(PORTAL_SHELLS["tess-moreno"]?.scopes[0]?.kind).toBe("client_entity");
    expect(PORTAL_SHELLS["claire-feld"]?.scopes[0]?.kind).toBe("client");
  });
});

describe("white label", () => {
  it("no portal fixture names the product", () => {
    const text = JSON.stringify([BRIGHTWATER_BRANDING, PORTAL_SHELLS, claireHome(2), tessHome()]);
    expect(text).not.toMatch(/accrued/i);
    expect(BRIGHTWATER_BRANDING.secured_footer).toBe(false);
  });
});
