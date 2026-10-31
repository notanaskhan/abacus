// AUD-06 fixture scenarios (A-02-T05; TASK-1215): "/components/screens/AUD-06?st=a..h renders each
// artboard's persona, clock and figures, and footing assertions (six funds 14,895,000.00; AJE-1
// 48,600.00) pass on the fixtures." Each scenario's C9 v1 answers are checked against the OpenAPI
// document, every figure the handoff draws is footed from the fixture (re-adding the lines, never
// trusting a total), and the frame renders each artboard through the generated client.
import type {
  SnapshotOut,
  TbLayerViewOut,
  TbLeadsheetAreaOut,
  TieOutCheckOut,
  TrialBalancesOut,
} from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type FixtureRequest,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { validateResponse } from "../../fixtures/schema-check";
import { AJE1 } from "../../fixtures/seed/aud06";
import { cents, money } from "../../fixtures/seed/trial-balance";
import { newQueryClient } from "../../testing/support";
import { AUD06Frame } from "./artboard";
import { ARTBOARDS, type Aud06State, OPENS, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const P = "/v1/engagements/{engagement_id}/trial-balances";

/** Call a scenario's handler as the fixture router would. */
async function answer(
  state: Aud06State,
  route: string,
  params: Record<string, string>,
): Promise<{ status: number; body: unknown }> {
  const handlers: Record<string, FixtureHandler> = scenarios[state].handlers;
  const handler = handlers[`GET ${route}`];
  if (handler === undefined) throw new Error(`${state}: no handler for ${route}`);
  const request = {
    method: "GET",
    path: route,
    params,
    query: new URLSearchParams(),
    persona: scenarios[state].persona,
  } as unknown as FixtureRequest;
  const response = await Promise.race([
    Promise.resolve(handler(request)),
    new Promise<"pending">((resolve) => {
      setTimeout(() => {
        resolve("pending");
      }, 50);
    }),
  ]);
  if (response === "pending") return { status: 0, body: null };
  return { status: response.status, body: response.status === 200 ? await response.json() : null };
}

async function viewOf(state: Aud06State): Promise<TbLayerViewOut> {
  const o = OPENS[state];
  const { status, body } = await answer(state, `${P}/{tb_id}/layers/{layer}`, {
    engagement_id: o.engagementId,
    tb_id: o.tbId ?? "",
    layer: o.layer,
  });
  expect(status, state).toBe(200);
  expect(validateResponse("get", `${P}/{tb_id}/layers/{layer}`, body), state).toEqual([]);
  return body as TbLayerViewOut;
}

async function checksOf(state: Aud06State): Promise<TieOutCheckOut[]> {
  const o = OPENS[state];
  const { body } = await answer(state, `${P}/{tb_id}/checks`, {
    engagement_id: o.engagementId,
    tb_id: o.tbId ?? "",
  });
  expect(validateResponse("get", `${P}/{tb_id}/checks`, body), state).toEqual([]);
  return body as TieOutCheckOut[];
}

const lines = (v: TbLayerViewOut) => v.groups.flatMap((g) => g.lines);
const line = (v: TbLayerViewOut, code: string) => {
  const found = lines(v).find((l) => l.account_code === code);
  if (found === undefined) throw new Error(`no line ${code}`);
  return found;
};
const total = (v: TbLayerViewOut, key: string) => v.totals.find((t) => t.key === key)?.eoy;
const add = (values: readonly (string | null)[]) =>
  money(values.reduce((a, x) => a + (x === null ? 0n : cents(x)), 0n));
const FUNDS = ["1110", "1120", "1130", "1140", "1150", "1160"];

describe("AUD-06 scenarios (A-02-T05)", () => {
  it("covers a–h and the five added states with each artboard's persona and clock", () => {
    expect(ARTBOARDS).toEqual(["a", "b", "c", "d", "e", "f", "g", "h"]);
    expect(STATES).toEqual([
      ...ARTBOARDS,
      "empty",
      "newer",
      "loading",
      "error",
      "fs_line",
      "not_allowed",
    ]);
    const who = Object.fromEntries(
      STATES.map((s) => [s, [scenarios[s].persona, scenarios[s].clock]]),
    );
    expect(who).toMatchObject({
      a: ["hannah-leclerc", "2026-09-14T14:30:00-05:00"],
      b: ["hannah-leclerc", "2026-09-14T14:30:00-05:00"],
      c: ["hannah-leclerc", "2026-09-14T14:30:00-05:00"],
      d: ["hannah-leclerc", "2026-10-06T14:30:00-05:00"],
      e: ["hannah-leclerc", "2026-09-14T14:30:00-05:00"],
      f: ["hannah-leclerc", "2026-09-14T14:30:00-05:00"],
      g: ["caleb-dunn", "2026-09-14T16:05:00-05:00"],
      h: ["hannah-leclerc", "2026-11-09T10:15:00-06:00"],
      empty: ["simone-baptiste", "2026-09-14T09:24:00-05:00"],
      newer: ["simone-baptiste", "2026-09-14T09:24:00-05:00"],
      not_allowed: ["cole-hart", "2026-09-14T09:24:00-05:00"],
    });
  });

  it("a: six funds foot to 14,895,000.00; net assets 16,812,400.00; three ties with the loan rollforward", async () => {
    const v = await viewOf("a");
    expect(add(FUNDS.map((c) => line(v, c).eoy))).toBe("14895000.00");
    expect(total(v, "mutual_funds")).toBe("14895000.00");
    expect(total(v, "net_assets")).toBe("16812400.00");
    expect(v.balance).toMatchObject({
      debit: "17663450.00",
      credit: "17663450.00",
      balanced: true,
    });
    expect(line(v, "1130").eoy).toBe("2915330.00");
    const checks = await checksOf("a");
    expect(checks.map((c) => [c.label, c.result.status])).toEqual([
      ["Net assets ↔ trust report", "tie"],
      ["BOY ↔ PY2024 audited FS", "tie"],
      ["Loan rollforward", "tie"],
    ]);
    expect(checks[2]?.result.formula).toBe(
      "288,500.00 + 96,200.00 − 57,450.00 − 14,850.00 = 312,400.00",
    );
    expect(v.checks).toEqual({ tie: 3, off: 0, pending: 0, worst: "tie" });
  });

  it("b: the agent's ticks carry no initials and nothing is reviewed yet", async () => {
    const v = await viewOf("b");
    const ticks = lines(v).flatMap((l) => l.ticks ?? []);
    expect(ticks.length).toBe(6);
    for (const t of ticks) {
      expect(t.actor_kind).toBe("agent");
      expect(t.initials).toBeNull();
      expect(t.kind).toBe("agreed");
    }
  });

  it("c: BrokerWindow EOY 1,606,560.00 is off 1,560.00 against the trust report, flagged to an issue, and the pull balances", async () => {
    const v = await viewOf("c");
    expect(line(v, "1200").eoy).toBe("1606560.00");
    expect(line(v, "1200").flags?.[0]).toMatchObject({ kind: "does_not_tie" });
    expect(line(v, "1200").flags?.[0]?.issue_id).not.toBeNull();
    expect(v.balance.balanced).toBe(true);
    const checks = await checksOf("c");
    expect(checks[0]?.result).toMatchObject({ status: "off", difference: "1560.00" });
    expect(v.checks).toMatchObject({ tie: 2, off: 1, worst: "off" });
  });

  it("d: AJE-1 foots 33,540.00 + 15,060.00 = 48,600.00; Final net assets 16,861,000.00; every layer balances", async () => {
    const v = await viewOf("d");
    expect(add(AJE1.credits.map((c) => c.amount))).toBe(AJE1.debit.amount);
    expect(AJE1.debit.amount).toBe("48600.00");
    const receivable = line(v, "contributions_receivable");
    expect(receivable).toMatchObject({
      aje: "48600.00",
      final: "48600.00",
      adjustment_refs: ["AJE-1"],
    });
    expect(add(lines(v).map((l) => l.aje))).toBe("0.00");
    expect(total(v, "net_assets")).toBe("16861000.00");
    expect(v.layer).toBe("final");
    expect(v.balance.balanced).toBe(true);
    for (const l of lines(v)) expect(add([l.eoy, l.aje, l.rje])).toBe(l.final);
  });

  it("d: before an adjustment source registers (a), AJE · RJE · Final answer layer_unavailable", async () => {
    const o = OPENS.a;
    for (const layer of ["aje", "rje", "final"]) {
      const { status } = await answer("a", `${P}/{tb_id}/layers/{layer}`, {
        engagement_id: o.engagementId,
        tb_id: o.tbId ?? "",
        layer,
      });
      expect(status, layer).toBe(409);
    }
  });

  it("e: the Investments leadsheet reads the handoff's PY · CY · Δ · Δ% exactly", async () => {
    const o = OPENS.e;
    const { body } = await answer("e", `${P}/{tb_id}/leadsheets/{area}`, {
      engagement_id: o.engagementId,
      tb_id: o.tbId ?? "",
      area: "Investments",
    });
    expect(validateResponse("get", `${P}/{tb_id}/leadsheets/{area}`, body)).toEqual([]);
    const sheet = body as TbLeadsheetAreaOut;
    expect(sheet.rows.map((r) => [r.account_name, r.py, r.cy, r.change, r.change_pct])).toEqual([
      ["KRS 500 Index Fund", "5102300.00", "6120450.00", "1018150.00", "20.0"],
      ["KRS Target 2035 Fund", "2011640.00", "2384910.00", "373270.00", "18.6"],
      ["KRS Target 2045 Fund", "2388970.00", "2915330.00", "526360.00", "22.0"],
      ["KRS Bond Index Fund", "1276090.00", "1408220.00", "132130.00", "10.4"],
      ["KRS International Index Fund", "868000.00", "902610.00", "34610.00", "4.0"],
      ["Harborline Stable Value Fund", "1036000.00", "1163480.00", "127480.00", "12.3"],
      ["Self-directed brokerage (BrokerWindow)", "1257000.00", "1605000.00", "348000.00", "27.7"],
    ]);
    expect([sheet.py, sheet.cy, sheet.change, sheet.change_pct]).toEqual([
      "13940000.00",
      "16500000.00",
      "2560000.00",
      "18.4",
    ]);
    expect(add(sheet.rows.slice(0, 6).map((r) => r.cy))).toBe("14895000.00");
  });

  it("g: Harlow & Pike Manufacturing Interim 8/31/2026 balances at 86,000,000 with net income 3,400,000, whole dollars", async () => {
    const v = await viewOf("g");
    expect([v.label, v.display_unit, v.period_end]).toEqual([
      "interim",
      "whole_dollars",
      "2026-08-31",
    ]);
    expect(v.balance).toMatchObject({
      debit: "86000000.00",
      credit: "86000000.00",
      balanced: true,
    });
    expect(add(lines(v).map((l) => l.eoy))).toBe("0.00");
    expect(total(v, "total_assets")).toBe("29400000.00");
    expect(total(v, "net_income")).toBe("3400000.00");
    expect(lines(v)).toHaveLength(14);
  });

  it("h: Granite Peak FY2026 Final: total assets 26,410,000, debits = credits 71,910,000, pre-tax income 3,100,000", async () => {
    const v = await viewOf("h");
    expect(v.layer).toBe("final");
    expect(total(v, "total_assets")).toBe("26410000.00");
    expect(total(v, "net_income")).toBe("3100000.00");
    expect(v.balance).toMatchObject({
      debit: "71910000.00",
      credit: "71910000.00",
      balanced: true,
    });
  });

  it("empty: Granite Peak has a pulled snapshot and no trial balance of record", async () => {
    const { body } = await answer("empty", P, { engagement_id: OPENS.empty.engagementId });
    expect(validateResponse("get", P, body)).toEqual([]);
    const list = body as TrialBalancesOut;
    expect(list.trial_balances).toEqual([]);
    expect(list.snapshots[0]).toMatchObject({
      line_count: 14,
      total_debit: "71910000.00",
      total_credit: "71910000.00",
    });
  });

  it("newer: one adoptable pull with a code-computed change count (2 lines, net 0)", async () => {
    const v = await viewOf("newer");
    expect(v.newer_snapshots).toBe(1);
    const o = OPENS.newer;
    const { body } = await answer("newer", `${P}/{tb_id}/candidates`, {
      engagement_id: o.engagementId,
      tb_id: o.tbId ?? "",
    });
    expect((body as SnapshotOut[])[0]).toMatchObject({ lines_changed: 2, net_change: "0.00" });
  });

  it("loading, error and not allowed: never, 500 and a 404 with no hint", async () => {
    expect(
      (await answer("loading", P, { engagement_id: OPENS.loading.engagementId })).status,
    ).toBe(0);
    expect((await answer("error", P, { engagement_id: OPENS.error.engagementId })).status).toBe(
      500,
    );
    const o = OPENS.not_allowed;
    expect((await answer("not_allowed", P, { engagement_id: o.engagementId })).status).toBe(404);
    const v = await answer("not_allowed", `${P}/{tb_id}/layers/{layer}`, {
      engagement_id: o.engagementId,
      tb_id: o.tbId ?? "",
      layer: "unadjusted",
    });
    expect(v.status).toBe(404);
  });
});

describe("AUD-06 frames render each artboard's persona, clock and figures", () => {
  const FIGURE: Readonly<Record<string, [string, string]>> = {
    a: ["Hannah Leclerc · Sep 14, 2026 2:30 PM", "$14,895,000.00"],
    b: ["Hannah Leclerc · Sep 14, 2026 2:30 PM", "$14,895,000.00"],
    c: ["Hannah Leclerc · Sep 14, 2026 2:30 PM", "off 1,560.00"],
    d: ["Hannah Leclerc · Oct 6, 2026 2:30 PM", "$16,861,000.00"],
    e: ["Hannah Leclerc · Sep 14, 2026 2:30 PM", "18.4%"],
    f: ["Hannah Leclerc · Sep 14, 2026 2:30 PM", "?ov=signoff:trial_balance:"],
    g: ["Caleb Dunn · Sep 14, 2026 4:05 PM", "3,400,000"],
    h: ["Hannah Leclerc · Nov 9, 2026 10:15 AM", "$26,410,000.00"],
  };
  for (const state of ARTBOARDS) {
    it(`AUD-06${state}`, async () => {
      restore = installFixtureMode(scenarios[state]);
      render(
        <QueryClientProvider client={newQueryClient()}>
          <AUD06Frame state={state} />
        </QueryClientProvider>,
      );
      const [who, figure] = FIGURE[state] ?? ["", ""];
      await waitFor(() => {
        expect(document.querySelector("[data-aud06='who']")?.textContent).toContain(who);
      });
      await waitFor(() => {
        expect(document.querySelector("[data-screen='AUD-06']")?.textContent).toContain(figure);
      });
      expect(screen.queryByText(/\$\d[\d,]*\.\d{3}/u)).toBeNull();
      if (state === "b") {
        // The agent's draft: six outlined agent ticks on each amount column, never initials.
        const agent = document.querySelectorAll("[data-tick='agent']");
        expect(agent.length).toBe(12);
        expect(document.querySelectorAll("[data-tick='chip']")).toHaveLength(0);
      }
      if (state === "g") {
        expect(document.querySelector("[data-total='total_assets']")?.textContent).toContain(
          "29,400,000",
        );
      }
    });
  }
});
