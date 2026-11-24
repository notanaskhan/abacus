// Q-05-T23 (TASK-8933; DEC-5935): ADM-12 a–g render from their scenarios at their clocks. The
// tiles foot to the plan (2 planned + 1 in progress + 3 concluded = 6), the plan's nine columns sum
// to 1,104 px, every inspector differs from the EP / signer, the evaluation stays locked while
// inspections are open, and Decide on Dec 14, 2026 shows "Concluded Dec 14, 2026 · Margaret
// Okonkwo". No agent-owned control decides a finding or the evaluation.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode, never } from "../../app-core/fixture-mode";
import { inspections } from "../../fixtures/seed/adm12";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { ADM12, type ADM12Props } from "./index";
import { type Adm12ScenarioState, scenarios } from "./scenarios";

const hrefs = vi.hoisted(() => [] as string[]);
vi.mock("../../app-core/open", async (orig) => ({
  ...(await orig<typeof import("../../app-core/open")>()),
  useOpenHref: () => (href: string) => {
    hrefs.push(href);
  },
}));

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(sc: Scenario, props: ADM12Props = {}): void {
  restore = installFixtureMode(sc);
  renderRoutes([{ path: "/", component: () => <ADM12 {...props} /> }]);
}

function state(s: Adm12ScenarioState, props: ADM12Props = {}): void {
  show(scenarios[s], props);
}

async function plan(): Promise<HTMLElement> {
  const t = await screen.findByRole("table");
  await waitFor(() => {
    expect(t.querySelectorAll("[data-inspection]").length).toBe(6);
  });
  return t;
}

describe("ADM-12 Monitoring & inspections", () => {
  it("ADM-12a default: tiles, plan, findings and the locked evaluation", async () => {
    state("a");
    const t = await plan();
    const tiles = document.querySelector("[data-adm12='tiles']") as HTMLElement;
    for (const [n, w] of [
      ["2", "Planned"],
      ["1", "In progress"],
      ["3", "Concluded"],
      ["5", "Findings open"],
    ] as const) {
      expect(tiles.textContent).toContain(n);
      expect(tiles.textContent).toContain(w);
    }
    expect(screen.getByText("Inspection plan · 2026 cycle")).toBeTruthy();
    expect(t.textContent).toContain("Meridian Tool & Die, Inc.");
    expect(t.textContent).toContain("Concluded Aug 28");
    expect(
      screen.getByText(/6 inspections · 3 concluded · 1 in progress · 2 planned/),
    ).toBeTruthy();
    expect(screen.getByText(C.footerTax)).toBeTruthy();
    const list = document.querySelector("[data-adm12='findings']") as HTMLElement;
    expect(list.querySelectorAll("[data-finding]").length).toBe(5);
    const ev = await screen.findByRole("region", { name: C.evaluationTitle });
    expect(within(ev).getByText("Not started")).toBeTruthy();
    expect(within(ev).getByText("Inspections complete (3 of 6)")).toBeTruthy();
    const conclude = within(ev).getByRole("button", { name: C.conclude });
    expect((conclude as HTMLButtonElement).disabled).toBe(true);
  });

  it("ADM-12 the plan's nine columns sum to 1,104", async () => {
    state("a");
    const t = await plan();
    const cols = [...t.querySelectorAll("col")].map((c) => parseInt(c.style.width, 10));
    expect(cols.length).toBe(9);
    expect(cols.reduce((a, b) => a + b, 0)).toBe(1104);
    expect([...t.querySelectorAll("th")].map((h) => h.textContent)).toEqual(C.columns);
  });

  it("ADM-12 every inspector differs from the EP / signer (objectivity)", () => {
    for (const r of inspections(2026)) {
      expect(r.inspector.user_id).not.toBe(r.signer?.user_id);
    }
  });

  it("ADM-12b Select engagements: candidates with risk scores and the objectivity lines", async () => {
    state("b", { open: "select" });
    const sheet = await screen.findByRole("dialog", { name: C.sheetSelect });
    await waitFor(() => {
      expect(within(sheet).getAllByRole("checkbox").length).toBe(3);
    });
    expect(sheet.textContent).toContain("Risk score 0.82");
    expect(sheet.textContent).toContain("Celia Marsh — not on Sterling Freight ✓");
    expect(sheet.textContent).toContain(
      "Thomas Whitcombe — EP on Sterling Freight ✕ cannot inspect",
    );
  });

  it("ADM-12c Record finding: fields and the reserved evaluation", async () => {
    state("c", { open: "finding" });
    const sheet = await screen.findByRole("dialog", { name: C.sheetFinding });
    for (const f of Object.values(C.fields)) {
      expect(within(sheet).getAllByText(f).length).toBeGreaterThan(0);
    }
    expect(within(sheet).getByText(C.evaluationReserved)).toBeTruthy();
    fireEvent.click(within(sheet).getByRole("button", { name: C.cancel }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: C.sheetFinding })).toBeNull();
    });
  });

  it("ADM-12d Decide on Dec 14, 2026 shows Concluded Dec 14, 2026 · Margaret Okonkwo", async () => {
    state("d", { open: "decide" });
    const card = await screen.findByRole("region", {
      name: "Conclude the annual evaluation as of Dec 15, 2026?",
    });
    expect(card.textContent).toContain(C.decision.reserved);
    fireEvent.click(within(card).getByRole("button", { name: /Decide/ }));
    expect(await screen.findByText("Concluded Dec 14, 2026 · Margaret Okonkwo")).toBeTruthy();
  });

  it("ADM-12d the conclude button is enabled once no inspection is open", async () => {
    state("d");
    const ev = await screen.findByRole("region", { name: C.evaluationTitle });
    const conclude = await within(ev).findByRole("button", { name: C.conclude });
    expect((conclude as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(conclude);
    expect(
      await screen.findByRole("dialog", {
        name: "Conclude the annual evaluation as of Dec 15, 2026?",
      }),
    ).toBeTruthy();
  });

  it("ADM-12e empty 2027 cycle", async () => {
    state("e", { cycle: 2027 });
    expect(await screen.findByText(C.empty.title)).toBeTruthy();
    expect(screen.getByText(C.empty.body)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("ADM-12f concluded", async () => {
    state("f");
    expect(await screen.findByText("Concluded Dec 14, 2026 · Margaret Okonkwo")).toBeTruthy();
    expect(screen.queryByRole("button", { name: C.conclude })).toBeNull();
  });

  it("ADM-12g QM-F-02 detail with its actions", async () => {
    state("g", { finding: "QM-F-02" });
    await plan();
    const detail = await waitFor(() => {
      const d = document.querySelector("[data-adm12='finding-detail']");
      expect(d).not.toBeNull();
      return d as HTMLElement;
    });
    expect(detail.textContent).toContain(
      "SOC 1 bridge letter not obtained for the uncovered Oct–Dec period",
    );
    expect(detail.textContent).toContain("Methodology");
    expect(detail.textContent).toContain(
      "Deficiency · not severe, not pervasive (Margaret Okonkwo, Sep 11)",
    );
    expect(detail.textContent).toContain("Sep 30, 2026");
    const actions = detail.querySelector("[data-adm12='finding-actions']") as HTMLElement;
    expect(
      within(actions)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual([C.markRemediated, C.openStep, C.addTask]);
    fireEvent.click(screen.getByRole("button", { name: /QM-F-03/ }));
    await waitFor(() => {
      expect(
        detail.ownerDocument.querySelector("[data-adm12='finding-detail'] h3")?.textContent,
      ).toContain("1065 checklist C-22");
    });
  });

  it("ADM-12 no agent-owned control approves, signs off or decides", async () => {
    state("a");
    await plan();
    for (const b of screen.getAllByRole("button")) {
      expect(b.textContent).not.toMatch(/^(Approve|Sign off|Release|Send|Post|Decide)\b/);
    }
  });

  it("ADM-12 loading", async () => {
    show({
      ...scenarios.a,
      handlers: { ...scenarios.a.handlers, "GET /v1/quality/inspections": never },
    });
    await waitFor(() => {
      expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
    });
  });

  it("ADM-12 error", async () => {
    show({
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/quality/inspections": () => new Response("{}", { status: 503 }),
      },
    });
    expect(await screen.findByText(C.failed)).toBeTruthy();
  });

  it("ADM-12 a tax inspection opens its return (TAX-02); the settings nav opens ADM-08", async () => {
    state("a");
    await plan();
    fireEvent.click(screen.getByRole("button", { name: "Cedar Hollow Farms, LLC" }));
    const cedar = inspections(2026).find((r) => r.ref === "INS-26-04");
    expect(hrefs.at(-1)).toBe(`/tax-returns/${String(cedar?.work_item_id)}`);
    expect(screen.queryByRole("button", { name: "Meridian Tool & Die, Inc." })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Integrations/ }));
    expect(hrefs.at(-1)).toBe("/settings/integrations");
  });
});
