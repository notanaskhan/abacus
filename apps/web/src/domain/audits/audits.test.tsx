// A-01-T06: the audit cockpit L3 (SPEC-330 AC-15): "The rail renders registered rows only, every
// disc carries text, and the TPL-02 specimen still passes" (the specimen's own suite,
// packages/ui/src/templates/tpl02.test.tsx, runs unchanged). Plus the sub-line and idle-pill
// grammars, "Begin…" only with its capability, planned targets that open nothing, the blocked card,
// the dock host and the audit bar without Auto mode, on Northwind's fixture projections.
import type { AuditCockpitOut, AuditSectionRowOut } from "@abacus/api-client";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { validateResponse } from "../../fixtures/schema-check";
import { getSeed } from "../../fixtures/seed";
import { type CockpitGrammar, northwindCockpit } from "../../fixtures/seed/audit-cockpit";
import { auditHandlers } from "../../fixtures/handlers/audits";
import { AuditBar, AuditCockpit, BlockedSectionCard, SectionRail, dockHost, railModel } from ".";

afterEach(cleanup);

const IDS = {
  workItemId: "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c0001",
  engagementId: "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c0002",
  clientId: "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c0003",
};
const cockpit = (grammar: CockpitGrammar): AuditCockpitOut =>
  northwindCockpit(IDS, grammar, 11, 24);

function rail(c: AuditCockpitOut): HTMLElement {
  const { container } = render(<SectionRail cockpit={c} />);
  return container;
}

const phaseRows = (el: HTMLElement) => [...el.querySelectorAll('[data-rail-row="phase"]')];
const phaseText = (el: HTMLElement, id: string): string =>
  el.querySelector(`[data-phase="${id}"]`)?.textContent ?? "";

describe("AUD-02 cockpit L3: registered rows only (DV-1)", () => {
  it("renders exactly the rows the projection holds, nothing invented", () => {
    const only: AuditCockpitOut = {
      ...cockpit("run"),
      bands: [
        cockpit("run").bands?.[0] ?? { key: "overview", rows: [] },
        { key: "planning", rows: (cockpit("run").bands?.[1]?.rows ?? []).slice(0, 1) },
      ],
    };
    const el = rail(only);
    expect(phaseRows(el).map((r) => r.getAttribute("data-phase"))).toEqual(["trial_balance"]);
    expect(el.textContent).not.toContain("Materiality");
    expect(el.textContent).not.toContain("Fieldwork");
  });

  it("an empty projection renders no phase row", () => {
    const el = rail({ ...cockpit("run"), bands: [] });
    expect(phaseRows(el)).toHaveLength(0);
  });

  it("the model keeps the projection's order and marks planned targets", () => {
    const model = railModel(cockpit("run"));
    expect(model.links.map((l) => l.title)).toEqual([
      "Client",
      "Methodology",
      "Standards set",
      "Source Documents",
      "Team",
      "Activity",
    ]);
    expect(model.links.find((l) => l.id === "source_documents")?.sub).toBe("11 of 24 received");
    expect(model.sections.map((s) => s.title)).toEqual([
      "Planning",
      "Fieldwork",
      "Completion",
      "Reporting",
    ]);
    expect(model.planned.has("methodology")).toBe(true);
    expect(model.planned.has("client")).toBe(false);
  });
});

describe("AUD-02 cockpit L3: grammars, and every disc carries text", () => {
  it("a: the run sub-lines read exactly as the acceptance checklist says", () => {
    const el = rail(cockpit("run"));
    expect(phaseText(el, "trial_balance")).toContain("Complete · 9:26 AM");
    expect(phaseText(el, "materiality")).toContain("Blocked on a partner decision");
    expect(phaseText(el, "risk_assessment")).toContain("Running");
    expect(phaseText(el, "general_audit_planning")).toContain("Waiting on inputs");
    expect(phaseText(el, "service_organizations")).toContain("Queued");
    expect(phaseText(el, "testing")).toContain("Not started");
    expect(el.querySelector('[data-phase="materiality"]')?.getAttribute("data-disc")).toBe("warn");
    expect(el.querySelector('[data-phase="trial_balance"]')?.getAttribute("data-disc")).toBe(
      "done",
    );
  });

  it("b: no run, every phase row reads Not started", () => {
    const el = rail(cockpit("idle"));
    for (const row of phaseRows(el)) expect(row.textContent).toContain("Not started");
  });

  it("g: idle pills Ready / In progress replace the sub-lines", () => {
    const el = rail(cockpit("pills"));
    expect(phaseText(el, "trial_balance")).toContain("Ready");
    expect(phaseText(el, "materiality")).toContain("In progress");
    expect(phaseText(el, "trial_balance")).not.toContain("Complete · 9:26 AM");
  });

  it.each(["run", "idle", "pills"] as const)("%s: every disc has an accessible name", (g) => {
    const el = rail(cockpit(g));
    const discs = [...el.querySelectorAll('[data-rail-row="phase"] [role="img"]')];
    expect(discs.length).toBe(phaseRows(el).length);
    for (const disc of discs) expect(disc.getAttribute("aria-label")).toBeTruthy();
  });

  it("Begin… renders only on a row whose actions grant the run engine's start", () => {
    const el = rail(cockpit("run"));
    const begins = screen.queryAllByRole("button", { name: "Begin…" });
    expect(begins).toHaveLength(1);
    expect(el.querySelector('[data-phase="testing"]')?.textContent).toContain("Begin…");
    cleanup();
    rail(cockpit("idle"));
    expect(screen.queryAllByRole("button", { name: "Begin…" })).toHaveLength(0);
  });

  it("the overview card reads Processing during a run and the phase otherwise (DV-11)", () => {
    const { container } = render(<SectionRail cockpit={cockpit("run")} processing />);
    const card = container.querySelector('[data-record="overview-card"]');
    expect(card?.textContent).toContain("Northwind Robotics 401(k) Plan");
    expect(card?.textContent).toContain("PY2025 · Northwind Robotics, Inc.");
    expect(card?.textContent).toContain("Processing");
    cleanup();
    const idle = render(<SectionRail cockpit={cockpit("idle")} />).container;
    expect(idle.querySelector('[data-record="overview-card"]')?.textContent).toContain("Planning");
  });
});

describe("AUD-02 cockpit L3: links", () => {
  it("a planned target opens nothing; a built one hands its row to the screen", () => {
    const opened: AuditSectionRowOut[] = [];
    const { container } = render(
      <SectionRail cockpit={cockpit("run")} onOpen={(row) => opened.push(row)} />,
    );
    fireEvent.click(within(container).getByText("Methodology"));
    fireEvent.click(within(container).getByText("Client"));
    expect(opened.map((r) => [r.key, r.route])).toEqual([["client", "CLI-02"]]);
  });
});

describe("AUD-02 d: BlockedSectionCard", () => {
  it("names the decider, and its planned action is announced unavailable", () => {
    render(
      <BlockedSectionCard
        person="Margaret Okonkwo"
        body="Planning materiality is reserved to the engagement partner."
      />,
    );
    expect(screen.getByText("Waiting on Margaret Okonkwo")).toBeTruthy();
    expect(
      screen.getByText("Planning materiality is reserved to the engagement partner."),
    ).toBeTruthy();
    const action = screen.getByRole("button", { name: "Open decision" });
    expect((action as HTMLButtonElement).disabled).toBe(true);
    expect(action.getAttribute("aria-description")).toBe("Not built yet");
  });

  it("opens the decision when its target is built", () => {
    const open = vi.fn();
    render(<BlockedSectionCard person="Margaret Okonkwo" body="…" onOpenDecision={open} />);
    fireEvent.click(screen.getByRole("button", { name: "Open decision" }));
    expect(open).toHaveBeenCalledOnce();
  });
});

describe("AUD-02 cockpit L3: dock host (DV-2) and audit bar (DV-11)", () => {
  it("offers the projection's tabs, Agent first", () => {
    const dock = dockHost(cockpit("run"), { agent: <p>activity</p>, viewer: <p>page</p> });
    expect(dock?.views).toEqual(["Agent", "Viewer"]);
    expect(dock?.view).toBe("Agent");
    expect(dockHost(cockpit("run"), { tab: "viewer" })?.view).toBe("Viewer");
    expect(dockHost({ dock_tabs: [] })).toBeUndefined();
  });

  it("the Agent tab reads DF-04's words when the data boundary refuses AI", () => {
    const dock = dockHost(cockpit("run"), { aiUnavailable: true, agent: <p>activity</p> });
    render(<>{dock?.children}</>);
    expect(screen.getByText("AI isn't available for real client data yet")).toBeTruthy();
    expect(screen.queryByText("activity")).toBeNull();
  });

  it("without the auto-mode capability the bar has no Auto mode toggle", () => {
    render(<AuditBar cockpit={cockpit("run")} />);
    expect(screen.getByText("PY2025 Employee Benefit Plan Audit")).toBeTruthy();
    expect(screen.getByText("BH Audit Methodology · EBP v3")).toBeTruthy();
    expect(screen.getByText("All Audits")).toBeTruthy();
    expect(screen.getByText("Started 9:24 AM")).toBeTruthy();
    expect(screen.queryByText("Auto mode")).toBeNull();
    expect(screen.getByRole("button", { name: "Layout" })).toBeTruthy();
  });

  it("with the capability the toggle renders, and no run means no Started time", () => {
    const c = cockpit("idle");
    render(<AuditBar cockpit={{ audit_bar: { ...c.audit_bar, auto_mode: false } }} />);
    expect(screen.getByText("Auto mode")).toBeTruthy();
    expect(screen.queryByText(/^Started/)).toBeNull();
  });

  it("the cockpit composes the bar, the rail, the canvas and the dock; the layout chip hides it", () => {
    const { container } = render(
      <AuditCockpit
        cockpit={cockpit("run")}
        canvas={{ title: "Source Documents", children: <p>rows</p> }}
        dock={{ agent: <p>activity</p> }}
      />,
    );
    expect(container.querySelector('[data-cockpit="rail"]')).not.toBeNull();
    expect(container.querySelector('[data-cockpit="dock"]')).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Layout" }));
    expect(container.querySelector('[data-cockpit="dock"]')).toBeNull();
  });
});

describe("audits fixture handlers (fixture mode)", () => {
  const seed = getSeed();
  const handlers = auditHandlers(seed);
  const request = (path: string, params: Record<string, string>, persona?: string) =>
    ({
      method: "GET",
      path,
      params,
      query: new URLSearchParams(),
      body: undefined,
      persona,
    }) satisfies FixtureRequest;
  const northwind = () => {
    const nw = seed.engagements.find(
      (e) => e.client_entity_name === "Northwind Robotics 401(k) Plan",
    );
    const item = (seed.workItems[nw?.id ?? ""] ?? []).find((w) => w.kind === "assurance");
    if (item === undefined) throw new Error("no Northwind work item");
    return item.id;
  };

  it("the cockpit answers the schema with 11 of 24 counted from the seed", async () => {
    const id = northwind();
    const handler = handlers["GET /v1/audits/{work_item_id}/cockpit"];
    const res = await handler?.(request(`/v1/audits/${id}/cockpit`, { work_item_id: id }));
    const body = (await res?.json()) as AuditCockpitOut;
    expect(validateResponse("get", "/v1/audits/{work_item_id}/cockpit", body)).toEqual([]);
    expect(railModel(body).links.find((l) => l.id === "source_documents")?.sub).toBe(
      "11 of 24 received",
    );
  });

  it("an unknown work item answers 404", async () => {
    const handler = handlers["GET /v1/audits/{work_item_id}/cockpit"];
    const res = await handler?.(request("/v1/audits/x/cockpit", { work_item_id: "x" }));
    expect(res?.status).toBe(404);
  });
});
