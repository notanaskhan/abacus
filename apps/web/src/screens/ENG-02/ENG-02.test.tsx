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
import { type Eng02State, OPENS, STATES, TABS, scenarios } from "./scenarios";

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
  initialTab = "overview",
}: {
  engagementId: string;
  onNavigate?: (t: Eng02Target) => void;
  initialTab?: Eng02Tab;
}): JSX.Element {
  const [tab, setTab] = useState<Eng02Tab>(initialTab);
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
          initialTab={TABS[state]}
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
  it("defines a–g and the prospect state; Priya Raman at E0 except f (Margaret, Oct 6)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "prospect"]);
    for (const s of STATES.filter((st) => st !== "f")) {
      expect(scenarios[s].persona).toBe("priya-raman");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
    expect(scenarios.f.persona).toBe("margaret-okonkwo");
    expect(scenarios.f.clock).toBe("2026-10-06T11:20:00-05:00");
    expect(TABS.f).toBe("dashboard");
    expect(TABS.g).toBe("board");
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

describe("ENG-02 remaining (P-07-T28)", () => {
  const MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];

  it("ENG-02a CAS variant: Copperleaf 2026 Close, Active, the 12 closes and 7 of 12", async () => {
    show("a");
    expect(await screen.findByRole("heading", { name: /2026 Close/ })).toBeTruthy();
    expect(screen.getByText("Contracted Mar 3, 2026")).toBeTruthy();
    const group = await screen.findByRole("region", { name: "Monthly closes" });
    await waitFor(() => {
      expect(within(group).getAllByRole("listitem")).toHaveLength(12);
    });
    expect(within(group).getByText("7 of 12")).toBeTruthy();
    expect(
      within(group)
        .getAllByRole("listitem")
        .map((li) => li.querySelector("span.truncate")?.textContent),
    ).toEqual(MONTHS.map((m) => `${m} 2026 Close`));
    expect(within(rail()).getByText("Ben Ashby · Controller")).toBeTruthy();
    expect(within(rail()).getByText("Client accounting services (non-attest)")).toBeTruthy();
  });

  it('ENG-02 acceptance: "7 of 12" closes delivered equals the ✓ rows (January–July)', async () => {
    show("a");
    const group = await screen.findByRole("region", { name: "Monthly closes" });
    await waitFor(() => {
      expect(within(group).getAllByRole("listitem")).toHaveLength(12);
    });
    const rows = within(group).getAllByRole("listitem");
    const done = rows.filter((li) => li.querySelector("[role='img'][aria-label='Done']") !== null);
    expect(done.map((li) => li.querySelector("span.truncate")?.textContent)).toEqual(
      MONTHS.slice(0, 7).map((m) => `${m} 2026 Close`),
    );
    expect(within(group).getByText("7 of 12")).toBeTruthy();
  });

  it("ENG-02 acceptance: close rows use Delivered, Locked, In progress and Not started", async () => {
    show("a");
    const group = await screen.findByRole("region", { name: "Monthly closes" });
    await waitFor(() => {
      expect(within(group).getAllByRole("listitem")).toHaveLength(12);
    });
    const words = new Set(
      within(group)
        .getAllByRole("listitem")
        .map((li) => li.lastElementChild?.textContent ?? ""),
    );
    expect([...words].sort()).toEqual(["Delivered", "In progress", "Locked", "Not started"]);
  });

  it("ENG-02 acceptance: Approver of record is Ben Ashby with the SKE designation not required note", async () => {
    show("a");
    await screen.findByRole("heading", { name: /2026 Close/ });
    expect(
      within(rail()).getByText(
        "SKE designation not required — Copperleaf is not an attest client.",
      ),
    ).toBeTruthy();
    // The audit variant names an SKE designee instead: no such note.
    cleanup();
    restore?.();
    show("b");
    await screen.findByRole("heading", { name: /PY2025 EBP Audit/ });
    expect(screen.queryByText(/SKE designation not required/)).toBeNull();
  });

  it("ENG-02 acceptance (R2): tabs read Overview · Dashboard · Board · Work items 12 · Team 3 · Letter & terms · Budget, plus the gear (fixture build)", async () => {
    show("a");
    await screen.findByRole("heading", { name: /2026 Close/ });
    const list = screen.getByRole("tablist", { name: "Engagement sections" });
    await waitFor(() => {
      expect(within(list).getByRole("tab", { name: /Work items/ }).textContent).toBe(
        "Work items12",
      );
    });
    expect(
      within(list)
        .getAllByRole("tab")
        .map((t) => t.textContent),
    ).toEqual([
      "Overview",
      "Dashboard",
      "Board",
      "Work items12",
      "Team3",
      "Letter & terms",
      "Budget",
    ]);
    const gear = screen.getByRole("button", { name: "Engagement settings" });
    expect((gear as HTMLButtonElement).disabled).toBe(true);
  });

  it("ENG-02 acceptance (R2): the gear is disabled on the archived record", async () => {
    show("d");
    await screen.findByRole("heading", { name: /FY2025 FS Audit/ });
    const gear = screen.getByRole("button", { name: "Engagement settings" });
    expect((gear as HTMLButtonElement).disabled).toBe(true);
    expect(gear.getAttribute("data-gear")).toBe("archived");
  });

  it("ENG-02f Dashboard tab: Granite Peak FY2026 Financial Statement Audit, Active, hosting ENG-12", async () => {
    show("f");
    expect(
      await screen.findByRole("heading", { name: /FY2026 Financial Statement Audit/ }),
    ).toBeTruthy();
    const list = screen.getByRole("tablist", { name: "Engagement sections" });
    expect(
      within(list).getByRole("tab", { name: "Dashboard" }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(document.querySelector("[data-planned-tab='dashboard']")).not.toBeNull();
    expect(screen.getByText(/Opens ENG-12/)).toBeTruthy();
  });

  it("ENG-02g Board tab: Copperleaf hosting ENG-10", async () => {
    show("g");
    await screen.findByRole("heading", { name: /2026 Close/ });
    const list = screen.getByRole("tablist", { name: "Engagement sections" });
    expect(within(list).getByRole("tab", { name: "Board" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(
      screen.getByText("Opens ENG-10 · the board inside this record (see ENG-02g)."),
    ).toBeTruthy();
  });

  it("Team tab hosts the roster from GET …/team: Priya Raman, Raj Malhotra, Grace Holloway", async () => {
    const seen = show("a");
    await screen.findByRole("heading", { name: /2026 Close/ });
    fireEvent.click(screen.getByRole("tab", { name: /^Team/ }));
    const group = await screen.findByRole("list", { name: "Team" });
    await waitFor(() => {
      expect(within(group).getAllByRole("listitem")).toHaveLength(3);
    });
    expect(
      within(group)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([
      "Priya RamanEngagement partner",
      "Raj MalhotraSenior",
      "Grace HollowayClient service",
    ]);
    expect(seen.calls.some((c) => c.path.endsWith("/team"))).toBe(true);
  });

  it("Work items tab lists the work items from their kind providers", async () => {
    show("a");
    await screen.findByRole("heading", { name: /2026 Close/ });
    fireEvent.click(screen.getByRole("tab", { name: /^Work items/ }));
    const group = await screen.findByRole("region", { name: "Monthly closes" });
    await waitFor(() => {
      expect(within(group).getAllByRole("listitem")).toHaveLength(12);
    });
  });

  it("On hold with a reason (DEC-328, DEC-344): the status pill ⌄ asks for a reason, holds, shows it, and Active resumes", async () => {
    const seen = show("a");
    await screen.findByRole("heading", { name: /2026 Close/ });
    const trigger = document.querySelector<HTMLElement>("[data-status-menu]");
    if (trigger === null) throw new Error("no status menu");
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    let menu = screen.getByRole("menu", { name: "Status" });
    expect(
      within(menu).getByRole("menuitemradio", { name: "Active" }).getAttribute("aria-checked"),
    ).toBe("true");
    fireEvent.click(within(menu).getByRole("menuitemradio", { name: "On hold…" }));
    const dialog = await screen.findByRole("dialog", { name: "Put on hold" });
    const confirm = within(dialog).getByRole("button", { name: "Put on hold" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    expect(within(dialog).getAllByRole("radio")).toHaveLength(5);
    for (const name of [
      "Client unresponsive",
      "Fees outstanding",
      "Scope change",
      "Independence review",
      "Other",
    ]) {
      expect(within(dialog).getByRole("radio", { name })).toBeTruthy();
    }
    fireEvent.click(within(dialog).getByRole("radio", { name: "Fees outstanding" }));
    expect((confirm as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Engagement on hold");
    });
    const held = seen.calls.find((c) => c.method === "POST" && c.path.endsWith("/hold"));
    expect(held?.body).toEqual({ reason: "fees_outstanding" });
    expect(await screen.findByText("Fees outstanding")).toBeTruthy();
    expect(
      within(screen.getByRole("heading", { name: /2026 Close/ })).getByText("On hold"),
    ).toBeTruthy();

    const again = document.querySelector<HTMLElement>("[data-status-menu]");
    if (again === null) throw new Error("no status menu");
    again.focus();
    fireEvent.keyDown(again, { key: "ArrowDown" });
    menu = screen.getByRole("menu", { name: "Status" });
    fireEvent.click(within(menu).getByRole("menuitemradio", { name: "Active" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/resume"))).toBe(true);
    });
    await waitFor(() => {
      expect(document.querySelector("[data-hold-reason]")).toBeNull();
    });
  });

  it("the status menu is offered only with engagement.hold on an Active or On hold record (b, c, d read a plain pill)", async () => {
    for (const state of ["b", "c", "d"] as const) {
      show(state);
      await screen.findByRole("heading", { level: 1 });
      await waitFor(() => {
        expect(document.querySelector("[data-shell='record-header'] h1")).not.toBeNull();
      });
      expect(document.querySelector("[data-status-menu]")).toBeNull();
      cleanup();
      restore?.();
      restore = undefined;
    }
  });

  it("a hold the server refuses (409 illegal_transition) keeps the dialog open with the reason", async () => {
    show("a", {
      "POST /v1/engagements/{engagement_id}/hold": () =>
        json({ detail: "illegal_transition" }, 409),
    });
    await screen.findByRole("heading", { name: /2026 Close/ });
    const trigger = document.querySelector<HTMLElement>("[data-status-menu]");
    if (trigger === null) throw new Error("no status menu");
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(
      within(screen.getByRole("menu", { name: "Status" })).getByRole("menuitemradio", {
        name: "On hold…",
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Put on hold" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Other" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Put on hold" }));
    expect(await within(dialog).findByRole("alert")).toBeTruthy();
    expect(within(dialog).getByText("Only an active engagement can go on hold.")).toBeTruthy();
  });

  it("no control on the record is an agent-owned approve, sign-off, release, send, post or decide", async () => {
    show("a");
    await screen.findByRole("heading", { name: /2026 Close/ });
    for (const word of [/^Approve/, /^Sign off/, /^Release/, /^Send/, /^Post/, /^Decide/]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
    }
  });
});
