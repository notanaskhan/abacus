// CLI-02 · Client record · Overview (P-07-T19). One test per artboard this task builds (a, a2, b,
// c, e, f) on its fixture scenario, the spec's and revision's acceptance checklists that the
// contract carries, P-07 Story 1.3 (Reveal), loading, error, the walled 404 and the metadata-only
// firm admin, the relationship-partner PATCH and the task's acceptance: "Scenarios a to f pass
// with axe, the reveal announces and re-masks, and production hides the dock and the
// responsiveness card."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import { getSeed } from "../../fixtures/seed";
import { clientIdOf } from "../../fixtures/seed/client-records";
import { renderRoutes } from "../../testing/support";
import { CLI02, type Cli02Tab } from ".";
import {
  type Cli02State,
  OCT_1,
  OPENS,
  STATES,
  metadataOnlyHandlers,
  scenarios,
} from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
  vi.useRealTimers();
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

function Harness({ clientId }: { clientId: string }): JSX.Element {
  const [tab, setTab] = useState<Cli02Tab>("overview");
  return <CLI02 clientId={clientId} tab={tab} onTab={setTab} />;
}

function show(
  state: Cli02State,
  over: Record<string, FixtureHandler> = {},
  clientId: string = OPENS[state],
): Seen {
  const seen = install(scenarios[state], over);
  renderRoutes([{ path: "/", component: () => <Harness clientId={clientId} /> }]);
  return seen;
}

/** Waits for the record's heading and the staff names its Team band reads. */
async function loaded(name: RegExp): Promise<void> {
  await screen.findByRole("heading", { name });
  await screen.findByRole("region", { name: "Summary" });
  await waitFor(() => {
    expect(within(rail()).queryAllByText("Details").length).toBeGreaterThan(0);
  });
}

function rail(): HTMLElement {
  return screen.getByRole("region", { name: "Summary" });
}

function kv(label: string): HTMLElement {
  const key = within(rail()).getAllByText(label)[0];
  const row = key?.closest<HTMLElement>("[data-record='kv']");
  if (row == null) throw new Error(`no row ${label}`);
  return row;
}

describe("CLI-02 artboards", () => {
  it("defines the artboards P-07-T19 builds: a–e at E0 as Daniel Reyes, f on Oct 1 as Margaret Okonkwo", () => {
    expect(STATES).toEqual(["a", "a2", "b", "c", "e", "f"]);
    for (const s of STATES.filter((x) => x !== "f")) {
      expect(scenarios[s].persona).toBe("daniel-reyes");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
    expect(scenarios.f.persona).toBe("margaret-okonkwo");
    expect(scenarios.f.clock).toBe(OCT_1);
  });

  it("CLI-02a default", async () => {
    show("a");
    expect(
      await screen.findByRole("heading", { name: /Ridgeline Property Partners, LP/ }),
    ).toBeTruthy();
    expect(screen.getByText("Partnership")).toBeTruthy();
    expect(screen.getByText("Moderate risk")).toBeTruthy();
    expect(await screen.findByText("Partner Daniel Reyes · New York")).toBeTruthy();
    expect(within(rail()).getByText("Real estate partnership · Form 1065")).toBeTruthy();
    expect(within(rail()).getByText("2 active engagements ⌄")).toBeTruthy();
    expect(await within(rail()).findByText("Open issues on the 2025 return")).toBeTruthy();
    expect(within(rail()).getByText("11")).toBeTruthy();
    expect(within(rail()).getByText("2 of 5")).toBeTruthy();
    expect(within(rail()).getByText("1 day")).toBeTruthy();
    expect(within(kv("Fiscal year end")).getByText("December 31")).toBeTruthy();
    expect(within(kv("Attest client")).getByText("No")).toBeTruthy();
    expect(
      await within(rail()).findByRole("button", { name: "Partner: Daniel Reyes" }),
    ).toBeTruthy();
    expect(within(kv("Manager")).getByText("Samuel Ito")).toBeTruthy();
    expect(within(kv("Preparer")).getByText("Olivia Brandt")).toBeTruthy();
    const work = screen.getByRole("region", { name: "Active work" });
    expect(within(work).getAllByText("2025 Form 1065").length).toBeGreaterThan(0);
    expect(within(work).getByText("Scoping")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Waiting on client · 5" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Key dates" })).toBeTruthy();
    expect(screen.getByText("Form 1065 extended due date")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Recent activity" })).toBeTruthy();
    expect(screen.getByText("8:40 AM")).toBeTruthy();
  });

  it("CLI-02a2 rail scrolled: the Client Portal and Links bands", async () => {
    show("a2");
    await loaded(/Ridgeline Property Partners, LP/);
    expect(await within(rail()).findByText("Client Portal")).toBeTruthy();
    expect(await within(kv("Contact")).findByText("Owen Calder")).toBeTruthy();
    expect(within(kv("Email")).getByText("owen.calder@ridgelinepp.com")).toBeTruthy();
    expect(within(kv("Status")).getByText("Active")).toBeTruthy();
    expect(within(kv("Requests")).getByText("5 pending")).toBeTruthy();
    expect(within(rail()).getByText("5 identities")).toBeTruthy();
    expect(within(kv("Entities")).getByText("1")).toBeTruthy();
    expect(within(kv("Relationships")).getByText("6 parties")).toBeTruthy();
    expect(within(kv("Binder")).getByText("2025 Binder")).toBeTruthy();
    expect(within(rail()).getByText("1 unread")).toBeTruthy();
    expect(within(rail()).getByText("Ridgeline Property Partners, LP's Files")).toBeTruthy();
  });

  it("CLI-02b household: Jonah & Claire Feld", async () => {
    show("b");
    expect(await screen.findByRole("heading", { name: /Jonah & Claire Feld/ })).toBeTruthy();
    expect(screen.getByText("Household")).toBeTruthy();
    expect(within(rail()).getByText("MFJ · Form 1040 · Brooklyn, NY")).toBeTruthy();
    expect(await within(rail()).findByText("•••-••-2208 (Claire)")).toBeTruthy();
    expect(within(kv("Filing status")).getByText("Married filing jointly")).toBeTruthy();
    expect(within(kv("Resident")).getByText("New York (incl. NYC)")).toBeTruthy();
    expect(
      within(kv("§7216 consents")).getByText("Use · AI disclosure (2 consents)"),
    ).toBeTruthy();
    expect(within(rail()).getByText("31 days")).toBeTruthy();
    expect(within(rail()).getByText("37")).toBeTruthy();
    const work = screen.getByRole("region", { name: "Active work" });
    expect(within(work).getByText("2025 Form 1040")).toBeTruthy();
    expect(within(work).getByText("Draft K-1 · pre-release")).toBeTruthy();
    expect(within(work).getByText("307,900")).toBeTruthy();
  });

  it("CLI-02c plan sponsor: Northwind Robotics, Inc.", async () => {
    show("c");
    expect(await screen.findByRole("heading", { name: /Northwind Robotics, Inc\./ })).toBeTruthy();
    expect(screen.getByText("Plan sponsor")).toBeTruthy();
    expect(screen.getByText("Attest")).toBeTruthy();
    expect(await within(rail()).findByText("11 of 24")).toBeTruthy();
    expect(within(rail()).getByText("Processing")).toBeTruthy();
    expect(within(rail()).getByText("Oct 9")).toBeTruthy();
    expect(within(rail()).getByText("Form 5500 due (5558)")).toBeTruthy();
    expect(
      within(kv("Plan")).getByText("Northwind Robotics 401(k) Plan · PN 001 · §103(a)(3)(C)"),
    ).toBeTruthy();
    expect(within(kv("SKE designee")).getByText("Dana Kowalski")).toBeTruthy();
    expect(within(kv("Independence")).getByText("4 of 5 confirmed")).toBeTruthy();
    // Northwind's record does not allow Daniel to edit it: the partner is text, not a picker.
    expect(within(kv("Partner")).queryByRole("button")).toBeNull();
  });

  it("CLI-02e empty canvas: Copperleaf before its first engagement", async () => {
    show("e");
    expect(await screen.findByText("No engagements yet.")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "+ New engagement" }).length).toBeGreaterThan(0);
    // The EIN is applied for: no masked value and no Reveal.
    expect(within(rail()).queryByText("Reveal (logged)")).toBeNull();
    expect(within(rail()).queryByText(/active engagements/)).toBeNull();
  });

  it("CLI-02f client responsiveness: Granite Peak", async () => {
    show("f");
    const card = await screen.findByRole("region", { name: "Client responsiveness" });
    expect(within(card).getByText("ON-TIME RATE")).toBeTruthy();
    expect(within(card).getByText("48%")).toBeTruthy();
    expect(within(card).getByText("63%")).toBeTruthy();
    expect(within(card).getByText("3")).toBeTruthy();
    expect(
      within(card).getByText(
        "Season to date Jan 1 – Sep 30, 2026 · on time = completed by its due date · compared with the firm rate",
      ),
    ).toBeTruthy();
    expect(
      within(card).getByText("Below the firm rate — noted for the FY2027 continuance."),
    ).toBeTruthy();
    expect(within(card).getByText("Open in Insights")).toBeTruthy();
    expect(within(card).getByText("Draft follow-ups…")).toBeTruthy();
  });

  it("CLI-02 loading: the record never answers", async () => {
    show("a", { "GET /v1/clients/{client_id}": () => never() });
    expect(await screen.findByRole("status", { name: "Loading" })).toBeTruthy();
  });

  it("CLI-02 error: the record answers 500", async () => {
    show("a", { "GET /v1/clients/{client_id}": () => json({ detail: "boom" }, 500) });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("CLI-02 not allowed: a walled client answers 404 and the record cannot be opened (INV-3)", async () => {
    const ashford = clientIdOf("Ashford Manufacturing Co.");
    expect(
      getSeed().walls.some((w) => w.clientId === ashford && w.personSlug === "lena-park"),
    ).toBe(true);
    install({ ...scenarios.a, persona: "lena-park" });
    renderRoutes([{ path: "/", component: () => <Harness clientId={ashford} /> }]);
    expect(await screen.findByText("You can’t open this record.")).toBeTruthy();
    expect(screen.queryByText("Ashford Manufacturing Co.")).toBeNull();
  });

  it("CLI-02 metadata only: the firm admin sees the record without content sections (ADR-024)", async () => {
    show("a", metadataOnlyHandlers());
    expect(
      await screen.findByRole("heading", { name: /Ridgeline Property Partners, LP/ }),
    ).toBeTruthy();
    expect(await screen.findByRole("region", { name: "Key dates" })).toBeTruthy();
    expect(screen.queryByText("K-1 packages · TY2025")).toBeNull();
    expect(screen.queryByRole("region", { name: /Waiting on client/ })).toBeNull();
    expect(within(rail()).queryByText("Open issues on the 2025 return")).toBeNull();
  });
});

describe("CLI-02 acceptance", () => {
  it("CLI-02 acceptance: the rail copies close-overview: Summary header, the ⌄ pill, stat rows, Details and Client Portal bands", async () => {
    show("a");
    await loaded(/Ridgeline Property Partners, LP/);
    expect(await within(rail()).findByRole("heading", { name: "Summary" })).toBeTruthy();
    expect(within(rail()).getByText("2 active engagements ⌄")).toBeTruthy();
    expect(
      within(rail())
        .getAllByRole("button")
        .some((b) => b.dataset.record === "stat"),
    ).toBe(true);
    expect(within(rail()).getByText("Details")).toBeTruthy();
    expect(within(rail()).getByText("Client Portal")).toBeTruthy();
    expect(await within(kv("Requests")).findByText("5 pending")).toBeTruthy();
  });

  it("CLI-02 acceptance: K-1 box 2 rows sum to 1,231,600 (= Schedule K), all five Draft K-1 · pre-release", async () => {
    show("a");
    const table = (await screen.findByText("K-1 packages · TY2025")).parentElement;
    if (table === null) throw new Error("no K-1 table");
    for (const v of ["24,632", "468,008", "400,270", "30,790", "307,900"]) {
      expect(within(table).getByText(v)).toBeTruthy();
    }
    expect(within(table).getAllByText("Draft K-1 · pre-release")).toHaveLength(5);
    expect(within(table).getByText("Total = Schedule K")).toBeTruthy();
    expect(table.querySelector("[data-total='schedule-k']")?.textContent).toBe("1,231,600");
    // Feld and Shah carry their internal hand-offs; the other three have none.
    expect(within(table).getAllByText("Opens TAX-02 · return overview")).toHaveLength(2);
  });

  it("CLI-02 acceptance: Ridgeline status words are §3.3.1 (In review; the project reads Scoping)", async () => {
    show("a");
    const work = await screen.findByRole("region", { name: "Active work" });
    expect(within(work).getByText("In review")).toBeTruthy();
    expect(within(work).getByText("Scoping")).toBeTruthy();
  });

  it("CLI-02 acceptance: the EIN is masked XX-XXX0287; Reveal is logged", async () => {
    show("a");
    await loaded(/Ridgeline Property Partners, LP/);
    expect(await within(kv("EIN")).findByText("XX-XXX0287")).toBeTruthy();
    expect(within(kv("EIN")).getByRole("button", { name: "Reveal (logged)" })).toBeTruthy();
  });

  it("CLI-02 acceptance: Reveal asks for a reason, shows the value for 10 seconds, announces it, re-masks and returns focus", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const seen = show("a");
    await loaded(/Ridgeline Property Partners, LP/);
    const reveal = await within(kv("EIN")).findByRole("button", { name: "Reveal (logged)" });
    fireEvent.click(reveal);
    const dialog = await screen.findByRole("dialog", { name: "Reveal taxpayer ID" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reveal" }));
    expect(await within(kv("EIN")).findByText("00-0000287")).toBeTruthy();
    expect(within(kv("EIN")).getByText("Taxpayer ID shown for 10 seconds.")).toBeTruthy();
    const call = seen.calls.find((c) => c.path.endsWith("/tin/reveal"));
    expect(call?.method).toBe("POST");
    expect(call?.body).toEqual({ reason: "prepare_return" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    await waitFor(() => {
      expect(within(kv("EIN")).getByText("XX-XXX0287")).toBeTruthy();
    });
    expect(within(kv("EIN")).queryByText("00-0000287")).toBeNull();
    expect(within(kv("EIN")).getByText("Taxpayer ID masked again.")).toBeTruthy();
    await waitFor(() => {
      expect(document.activeElement).toBe(
        within(kv("EIN")).getByRole("button", { name: "Reveal (logged)" }),
      );
    });
  });

  it("CLI-02 acceptance: a record that does not allow tin.reveal never gets the button", async () => {
    show("b", {
      "GET /v1/clients/{client_id}": async (request) => {
        const base = scenarios.b.handlers["GET /v1/clients/{client_id}"];
        if (base === undefined) throw new Error("no handler");
        const body = (await (await base(request)).json()) as { allowed_actions: string[] };
        return json({ ...body, allowed_actions: ["client.read"] });
      },
    });
    await loaded(/Jonah & Claire Feld/);
    expect(await within(rail()).findByText("•••-••-2208 (Claire)")).toBeTruthy();
    expect(within(rail()).queryByRole("button", { name: "Reveal (logged)" })).toBeNull();
  });

  it("CLI-02 acceptance: the relationship partner picker PATCHes with the version seen", async () => {
    const seen = show("a");
    await loaded(/Ridgeline Property Partners, LP/);
    const picker = await within(rail()).findByRole("button", { name: "Partner: Daniel Reyes" });
    picker.focus();
    fireEvent.keyDown(picker, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu");
    fireEvent.click(within(menu).getByText("Priya Raman"));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    const patch = seen.calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toMatchObject({ seen_version: 7 });
    expect(
      await within(rail()).findByRole("button", { name: "Partner: Priya Raman" }),
    ).toBeTruthy();
  });

  it("CLI-02 acceptance: no dock in this build until P-09 registers the SHL-13 host", async () => {
    show("a");
    await screen.findByRole("heading", { name: /Ridgeline Property Partners, LP/ });
    expect(document.querySelector("[data-cockpit='dock']")).toBeNull();
  });

  it("CLI-02 acceptance (R2): frames a–e show no Client responsiveness card", async () => {
    for (const s of ["a", "b", "c"] as const) {
      show(s);
      await screen.findByRole("region", { name: "Active work" });
      expect(screen.queryByRole("region", { name: "Client responsiveness" })).toBeNull();
      cleanup();
      restore?.();
    }
  });

  it("CLI-02 acceptance (R2): frame f shows 48% against the firm's 63% and 3 overdue, and no other client's figures", async () => {
    show("f");
    const card = await screen.findByRole("region", { name: "Client responsiveness" });
    expect(within(card).getByText("48%").className).toContain("text-red-ink");
    expect(within(card).getByText("63%").className).not.toContain("text-red-ink");
    expect(screen.queryByText("Ridgeline Property Partners, LP")).toBeNull();
  });

  it("CLI-02 acceptance (R2): follow-ups are a person's link to BND-04, never sent from the record", async () => {
    show("f");
    const card = await screen.findByRole("region", { name: "Client responsiveness" });
    expect(within(card).queryByRole("button", { name: /^Send/ })).toBeNull();
    expect(within(card).getByText("Draft follow-ups…").getAttribute("title")).toBe(
      "Opens BND-04 · 3 overdue requests",
    );
  });

  it("CLI-02 acceptance: the Relationships tab lists the record's edges", async () => {
    show("a");
    fireEvent.click(await screen.findByRole("tab", { name: "Relationships" }));
    const list = await screen.findByRole("list", { name: "Relationships" });
    expect(within(list).getByText("Ridgeline GP LLC")).toBeTruthy();
    expect(within(list).getAllByRole("listitem")).toHaveLength(6);
  });
});
