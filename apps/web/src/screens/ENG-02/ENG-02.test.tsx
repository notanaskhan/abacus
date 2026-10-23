// ENG-02 · Engagement record, core (P-07-T20). One test per state this task builds (b, c, d, e
// and the prospect banner) on its fixture scenario, the contract's acceptance bullets for them,
// P-07 Story 6.2 (the recorded letter and the G3 banner), loading, error, not found, and the
// task's acceptance: "The G3 banner clears only after a recorded letter dated after the
// acceptance decision, and every state passes axe" (axe: e2e/screens/ENG-02.spec.ts).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { ENG02, type Eng02Tab, type Eng02Target } from ".";
import { type Eng02State, OPENS, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function install(scenario: Scenario, over: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function Harness({
  engagementId,
  onNavigate,
}: {
  engagementId: string;
  onNavigate?: (t: Eng02Target) => void;
}): JSX.Element {
  const [tab, setTab] = useState<Eng02Tab>("overview");
  return (
    <ENG02
      engagementId={engagementId}
      tab={tab}
      onTab={setTab}
      {...(onNavigate === undefined ? {} : { onNavigate })}
    />
  );
}

function show(
  state: Eng02State,
  over: Record<string, FixtureHandler> = {},
  options: { id?: string; onNavigate?: (t: Eng02Target) => void } = {},
): Seen {
  const seen = install(scenarios[state], over);
  const id = options.id ?? OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <Harness
          engagementId={id}
          {...(options.onNavigate === undefined ? {} : { onNavigate: options.onNavigate })}
        />
      ),
    },
  ]);
  return seen;
}

function rail(): HTMLElement {
  return screen.getByRole("region", { name: "Summary" });
}

function gate(id: string): HTMLElement {
  const row = document.querySelector<HTMLElement>(`[data-gate='${id}']`);
  if (row === null) throw new Error(`no gate ${id}`);
  return row;
}

describe("ENG-02 states", () => {
  it("defines the states P-07-T20 builds, as Priya Raman at E0", () => {
    expect(STATES).toEqual(["b", "c", "d", "e", "prospect"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe("priya-raman");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("ENG-02b audit variant: Northwind PY2025 EBP Audit with gate rows", async () => {
    show("b");
    expect(await screen.findByRole("heading", { name: /PY2025 EBP Audit/ })).toBeTruthy();
    expect(screen.getByText("Contracted Jun 2, 2026")).toBeTruthy();
    expect(within(rail()).getByText("Northwind Robotics, Inc. (plan sponsor)")).toBeTruthy();
    expect(within(rail()).getByText("Northwind Robotics 401(k) Plan · PN 001")).toBeTruthy();
    expect(within(rail()).getByText("EBP DC · §103(a)(3)(C)")).toBeTruthy();
    expect(within(rail()).getByText("GAAS nonissuer · AU-C 703")).toBeTruthy();
    expect(within(rail()).getByText("BH Audit Methodology · EBP v3")).toBeTruthy();
    expect(within(rail()).getByText("Signed Jun 2, 2026")).toBeTruthy();
    expect(within(rail()).getByText("$32,000 fixed")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Gates" })).toBeTruthy();
    expect(within(gate("G1")).getByText("G1 Accept")).toBeTruthy();
    expect(await within(gate("G1")).findByText("MO · May 28")).toBeTruthy();
    expect(
      within(gate("G3")).getByText("Letter signed by Dana Kowalski and MO · Jun 2"),
    ).toBeTruthy();
    expect(within(gate("G4")).getByText("Blocked on a partner decision")).toBeTruthy();
    for (const g of ["G5", "G6", "G7", "G8", "G9"]) {
      expect(within(gate(g)).getByText("Not started")).toBeTruthy();
    }
    const work = screen.getByRole("region", { name: "Work items" });
    expect(await within(work).findByRole("list", { name: "Work items" })).toBeTruthy();
  });

  it("ENG-02c accepted, letter not signed: the G3 banner and no work items", async () => {
    show("c");
    expect(await screen.findByRole("heading", { name: /2026 Close \(from Oct\)/ })).toBeTruthy();
    expect(within(rail()).getByText("Accepted")).toBeTruthy();
    expect(
      screen.getByText(
        "Work items open when the letter is signed (G3). Letter viewed by Arjun Mehta · Sep 11.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open letter" })).toBeTruthy();
    expect(screen.getByText("No work items yet.")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Gates" })).toBeNull();
  });

  it("ENG-02d archived: locked read-only, every action disabled", async () => {
    show("d");
    expect(await screen.findByRole("heading", { name: /FY2025 FS Audit/ })).toBeTruthy();
    expect(within(rail()).getByText("Archived")).toBeTruthy();
    expect(within(rail()).getByText("Archive locked Jun 12, 2026 · WORM")).toBeTruthy();
    expect(within(rail()).getByText("Post-lock additions: 0")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Letter & terms" }));
    const record = await screen.findByRole("button", { name: "Record signed letter…" });
    expect((record as HTMLButtonElement).disabled).toBe(true);
  });

  it("ENG-02e loading: the record never answers", async () => {
    show("e");
    expect(await screen.findByRole("status", { name: "Loading" })).toBeTruthy();
  });

  it("ENG-02 prospect: the pre-acceptance banner names the partner", async () => {
    show("prospect");
    expect(await screen.findByRole("heading", { name: /Estate returns/ })).toBeTruthy();
    expect(await screen.findByText("Acceptance pending — Daniel Reyes")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open acceptance ›" })).toBeTruthy();
    expect(within(rail()).getByText("Prospect")).toBeTruthy();
  });

  it("ENG-02 error: the record answers 500", async () => {
    show("b", { "GET /v1/engagements/{engagement_id}/record": () => json({ detail: "x" }, 500) });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("ENG-02 not allowed: an unknown or walled engagement answers 404 (INV-3)", async () => {
    show("b", {}, { id: "00000000-0000-4000-8000-000000000000" });
    expect(await screen.findByText("You can’t open this record.")).toBeTruthy();
  });

  it("ENG-02 Client › opens CLI-02 for the record's client", async () => {
    const onNavigate = vi.fn();
    show("b", {}, { onNavigate });
    await screen.findByRole("heading", { name: /PY2025 EBP Audit/ });
    fireEvent.click(await within(rail()).findByRole("button", { name: /Client/ }));
    expect(onNavigate).toHaveBeenCalledWith(expect.objectContaining({ screen: "CLI-02" }));
  });
});

describe("ENG-02 acceptance", () => {
  it("ENG-02 acceptance: in the audit variant the gates read G1–G3 met and G4 blocked", async () => {
    show("b");
    await screen.findByRole("region", { name: "Gates" });
    expect(["G1", "G2", "G3"].map((g) => gate(g).dataset.met)).toEqual(["met", "met", "met"]);
    expect(gate("G4").dataset.met).toBe("blocked");
    expect(gate("G5").dataset.met).toBe("not-started");
  });

  it("ENG-02 acceptance: no status word outside §3.3.1 on the record states", async () => {
    for (const [s, word] of [
      ["b", "Active"],
      ["c", "Accepted"],
      ["d", "Archived"],
      ["prospect", "Prospect"],
    ] as const) {
      show(s);
      await screen.findByRole("heading", { level: 1 });
      expect(within(rail()).getByText(word)).toBeTruthy();
      cleanup();
      restore?.();
    }
  });

  it("ENG-02 acceptance: the G3 banner clears only after a recorded letter dated after the acceptance decision", async () => {
    const seen = show("c");
    await screen.findByText(/Work items open when the letter is signed \(G3\)/);
    fireEvent.click(screen.getByRole("button", { name: "Open letter" }));
    fireEvent.click(await screen.findByRole("button", { name: "Record signed letter…" }));
    const sheet = await screen.findByRole("dialog", { name: "Record signed letter" });
    const inputs = within(sheet).getAllByPlaceholderText("YYYY-MM-DD");
    const [clientOn, firmOn] = inputs;
    if (clientOn === undefined || firmOn === undefined) throw new Error("no date rows");
    const save = within(sheet).getByRole("button", { name: "Record letter" });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    // Dated before the acceptance decision (Sep 8): the server refuses and the banner stays.
    fireEvent.change(clientOn, { target: { value: "2026-09-01" } });
    fireEvent.change(firmOn, { target: { value: "2026-09-02" } });
    fireEvent.click(save);
    expect(
      await within(sheet).findByText(
        "The signature dates must fall after the acceptance decision.",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/Work items open when the letter is signed \(G3\)/)).toBeTruthy();
    // Dated after it: recorded, the engagement reads Letter signed and the banner clears.
    fireEvent.change(clientOn, { target: { value: "2026-09-12" } });
    fireEvent.change(firmOn, { target: { value: "2026-09-14" } });
    fireEvent.click(save);
    await waitFor(() => {
      expect(screen.queryByText(/Work items open when the letter is signed \(G3\)/)).toBeNull();
    });
    expect(await within(rail()).findByText("Letter signed")).toBeTruthy();
    const puts = seen.calls.filter((c) => c.method === "PUT");
    expect(puts).toHaveLength(2);
    expect(puts[1]?.body).toMatchObject({
      mode: "signed",
      client_signed_on: "2026-09-12",
      firm_signed_on: "2026-09-14",
    });
  });

  it("ENG-02 acceptance: d disables the recorded letter and the server answers 409 archived to a write", async () => {
    show("d");
    await screen.findByRole("heading", { name: /FY2025 FS Audit/ });
    const put = scenarios.d.handlers["PUT /v1/engagements/{engagement_id}/letter/record"];
    if (put === undefined) throw new Error("no handler");
    const res = await put({
      method: "PUT",
      path: "",
      params: { engagement_id: OPENS.d },
      query: new URLSearchParams(),
      body: { mode: "signed", client_signed_on: "2026-09-12", firm_signed_on: "2026-09-14" },
      persona: "priya-raman",
    });
    expect(res.status).toBe(409);
    expect(await res.json()).toMatchObject({ detail: "engagement_archived" });
  });
});
