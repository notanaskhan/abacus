// SHL-23 and HOME-05 figures that must foot (I-02-T12; docs/screens/SHL-23.md, HOME-05.md), on the
// Today seed and through the scenarios' handlers, against HOME-01's one count source:
//   11 = 3 + 6 + 2   Daniel's items: decisions, sign-offs, approvals & sends (= HOME-01's 11)
//    9 = 1 + 6 + 2   due tomorrow: the §754 decision, six Ridgeline sign-offs, final approval and
//                    the Harborview 8879-PE
//    4 = 6 - 2       ready for sign-off: six sign-offs less the two blocked
//    4 = 2 + 2       Margaret's items: decisions and signatures (= HOME-01's 4)
import type { CountCell, TodayVm } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { Scenario } from "../app-core/fixture-mode";
import { countsOf, gatesFor } from "./handlers/human-gates";
import { scenarios as home05 } from "./scenarios/HOME-05";
import { scenarios as shl23 } from "./scenarios/SHL-23";
import { getSeed } from "./seed";
import { DANIEL_ROWS, danielToday, margaretToday } from "./seed/today";

const seed = getSeed();

async function today(scenario: Scenario): Promise<TodayVm> {
  const handler = scenario.handlers["GET /v1/me/today"];
  const response = await handler?.({
    method: "GET",
    path: "/v1/me/today",
    params: {},
    query: new URLSearchParams(),
    body: null,
    persona: scenario.persona,
  });
  if (response === undefined) throw new Error("no Today handler");
  return (await response.json()) as TodayVm;
}

const count = (vm: TodayVm, kind: CountCell["kind"]): number =>
  vm.cells.find((c) => c.kind === kind)?.count ?? 0;
const sum = (vm: TodayVm): number => vm.cells.reduce((a, c) => a + c.count, 0);
const group = (vm: TodayVm, key: string): number =>
  vm.groups.find((g) => g.key === key)?.count ?? 0;

describe("SHL-23 and HOME-05 foot (I-COUNT)", () => {
  it("11 = 3 + 6 + 2: Daniel's cells are HOME-01's items", async () => {
    const vm = await today(shl23["1"]);
    expect([count(vm, "decision"), count(vm, "sign_off"), count(vm, "approval_send")]).toEqual([
      3, 6, 2,
    ]);
    expect(count(vm, "overdue")).toBe(0);
    expect(sum(vm)).toBe(11);
    expect(vm.items).toBe(11);
    expect(countsOf(gatesFor(seed, "daniel-reyes")).total).toBe(11);
  });

  it("9 = 1 + 6 + 2: due tomorrow is the decision, the six sign-offs and two approvals", () => {
    const vm = danielToday();
    expect(group(vm, "due_tomorrow")).toBe(1 + 6 + 2);
    const lead = vm.lead_facts.find((f) => f.key === "lead.due_tomorrow");
    expect(lead?.values.due).toBe(9);
    expect(lead?.values.total).toBe(11);
  });

  it("4 = 6 - 2: ready for sign-off is the sign-offs less the two blocked", () => {
    const vm = danielToday();
    const blocked = vm.lead_facts.find((f) => f.key === "lead.blocked_signoffs");
    expect(blocked?.values.blocked).toBe(2);
    expect(group(vm, "ready_for_signoff")).toBe(count(vm, "sign_off") - 2);
    expect(group(vm, "ready_for_signoff")).toBe(4);
  });

  it("4 = 2 + 2: Margaret's cells are HOME-01's items, on SHL-23 4 and HOME-05 d", async () => {
    for (const scenario of [shl23["4"], home05.d]) {
      const vm = await today(scenario);
      expect([count(vm, "decision"), count(vm, "signature")]).toEqual([2, 2]);
      expect(sum(vm)).toBe(4);
    }
    expect(margaretToday().items).toBe(4);
    expect(countsOf(gatesFor(seed, "margaret-okonkwo")).total).toBe(4);
  });

  it("the quiet day reads 0 everywhere, for a viewer with no gates in E0", async () => {
    const vm = await today(shl23["6"]);
    expect(sum(vm)).toBe(0);
    expect(vm.needs_you_first).toEqual([]);
    expect(countsOf(gatesFor(seed, "felix-andersen")).total).toBe(0);
  });

  it("Late · 1 only on Dec 1 (the fixture Late provider), Nothing is late on Sep 14", async () => {
    expect(group(await today(shl23["5"]), "late")).toBe(1);
    expect(group(await today(shl23["4"]), "late")).toBe(0);
  });

  it("Needs you first is three of Daniel's rows; building keeps the counts", async () => {
    expect(danielToday().needs_you_first).toHaveLength(3);
    expect(DANIEL_ROWS.map((r) => r.kind)).toEqual(["decision", "sign_off", "approval_send"]);
    const building = await today(shl23["7"]);
    expect(building.status).toBe("building");
    expect(sum(building)).toBe(11);
  });

  it("HOME-05 f: the flag off answers 404 on Today; the layout fixture is by_engagement", async () => {
    const handler = home05.f.handlers["GET /v1/me/today"];
    const off = await handler?.({
      method: "GET",
      path: "/v1/me/today",
      params: {},
      query: new URLSearchParams(),
      body: null,
      persona: "daniel-reyes",
    });
    expect(off?.status).toBe(404);
    const layout = await today(home05["f-layout"]);
    expect(layout.layout).toBe("by_engagement");
    expect(layout.cards).toHaveLength(4);
    expect(sum(layout)).toBe(11);
  });
});
