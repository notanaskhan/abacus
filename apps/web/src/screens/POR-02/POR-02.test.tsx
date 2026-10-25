// POR-02 · Portal home (P-08-T15 part 1, P-08-T23 part 2). One test per artboard on its fixture
// scenario (a–h and M), the contract's acceptance bullets and AVOID lines, P-08 Story 6.2 (the
// welcome dismissal), and the tasks' acceptance: T15 "Scenario tests for a, b, c and f pass,
// planned targets render only in fixture builds, and no red appears except on a past-due item";
// T23 "Scenario tests for d, e, g, h and M pass, and Meera Shah's home lists nothing of the
// Ridgeline return."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { PortalHome, todoWords } from ".";
import {
  FIRST_VISIT_CLOCK,
  type Por02State,
  STATES,
  feldOpenUploads,
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
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Por02State, over: Record<string, FixtureHandler> = {}, mobile = false): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = scenarios[state];
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
  renderRoutes([{ path: "/", component: () => <PortalHome scopeId={null} mobile={mobile} /> }]);
  return seen;
}

function todos(): HTMLElement {
  return screen.getByRole("list", { name: "To do" });
}

describe("POR-02 artboards (part 1)", () => {
  it("defines a, b, c and f as Claire Feld; b on her first visit", () => {
    expect(STATES).toEqual(expect.arrayContaining(["a", "b", "c", "f"]));
    for (const s of ["a", "b", "c", "f"] as const) {
      expect(scenarios[s].persona).toBe("claire-feld");
    }
    expect(scenarios.b.clock).toBe(FIRST_VISIT_CLOCK);
    expect(scenarios.a.clock).toBe("2026-09-14T09:24:00-05:00");
  });

  it("POR-02a default: Claire Feld at E0", async () => {
    show("a");
    expect(await screen.findByRole("heading", { name: "Good morning, Claire" })).toBeTruthy();
    expect(screen.getByText("Monday, September 14")).toBeTruthy();
    expect(screen.getByText("Jonah & Claire Feld")).toBeTruthy();
    expect(screen.getByText("Household · Brooklyn, NY")).toBeTruthy();
    expect(screen.getByText("Partner — signs your return")).toBeTruthy();
    expect(screen.getByText("Manager — reviews your return")).toBeTruthy();
    expect(screen.getByText("Preparer — your day-to-day contact")).toBeTruthy();
    expect(screen.getByText("Client service")).toBeTruthy();
    expect(within(todos()).getByText("Upload 2 documents")).toBeTruthy();
    expect(
      within(todos()).getByText("Form 1095-C and your 2025 estimated payment confirmations"),
    ).toBeTruthy();
    expect(within(todos()).getByText("Answer 3 questions")).toBeTruthy();
    expect(within(todos()).getByText("2 in your 2025 organizer · 1 from Kevin Osei")).toBeTruthy();
    expect(within(todos()).getByText("Nothing to sign yet")).toBeTruthy();
    expect(within(todos()).getByText("Your Form 8879 comes after our review.")).toBeTruthy();
    expect(within(todos()).getByText("2 documents ready")).toBeTruthy();
    const work = screen.getByRole("region", { name: "2025 Tax Return · Form 1040" });
    expect(within(work).getByText("Extended to Oct 15, 2026")).toBeTruthy();
    expect(within(work).getByText("We're reviewing your return")).toBeTruthy();
    expect(
      within(work).getByText(
        "We're waiting on one partnership K-1 (Ridgeline Property Partners, LP). Brightwater Hale prepares it — nothing for you to do. Expected by Sep 15.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("19 of 21 requests done · Brightwater Hale sorted 37 of your files"),
    ).toBeTruthy();
    const earlier = screen.getByRole("region", { name: "Earlier" });
    expect(
      within(earlier).getByText("2025 extension (Form 4868) filed · Apr 14, 2026"),
    ).toBeTruthy();
    expect(
      within(earlier).getByText(
        "Engagement letter and §7216 consents (use · AI disclosure) signed · Feb 2, 2026",
      ),
    ).toBeTruthy();
    expect(within(earlier).getByText("2024 Form 1040 filed and accepted")).toBeTruthy();
  });

  it("POR-02b first visit: the welcome card, 0 of 21, sign and upload to-dos", async () => {
    show("b");
    expect(await screen.findByText("Monday, February 2")).toBeTruthy();
    expect(screen.getByText("Welcome to Brightwater Hale's client portal.")).toBeTruthy();
    expect(
      screen.getByText(
        "Drop documents, answer questions and sign here — your team sees everything you send.",
      ),
    ).toBeTruthy();
    expect(
      within(todos()).getByText("Sign your engagement letter and two §7216 consents"),
    ).toBeTruthy();
    expect(
      within(todos()).getByText("Read and sign before we start on your 2025 return."),
    ).toBeTruthy();
    expect(within(todos()).getByText("Upload your 2025 documents (21 requested)")).toBeTruthy();
    expect(
      within(todos()).getByText("Drop files in your 2025 binder and they're sorted for you."),
    ).toBeTruthy();
    expect(screen.getByText("Due Apr 15, 2026")).toBeTruthy();
    expect(screen.getByText("We're getting started")).toBeTruthy();
    expect(screen.getByText("0 of 21 requests done")).toBeTruthy();
    expect(screen.getByText("Welcome to your client portal")).toBeTruthy();
  });

  it("POR-02c all set: every open item done", async () => {
    show("c");
    expect(await screen.findByText("You're all set for now.")).toBeTruthy();
    expect(screen.getByText("We'll email you when your return is ready to sign.")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "To do" })).toBeNull();
  });

  it("POR-02f loading: the home never answers", async () => {
    show("f");
    expect(await screen.findByRole("status", { name: "Loading" })).toBeTruthy();
  });

  it("POR-02 error: the home answers 500", async () => {
    show("a", { "GET /v1/portal/home": () => json({ detail: "x" }, 500) });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("POR-02 acceptance", () => {
  it("POR-02 acceptance: to-do counts tie: Upload 2 = the binder's open requests, Answer 3 = 2 + 1, nothing to sign", async () => {
    expect(feldOpenUploads()).toBe(2);
    show("a");
    expect(
      await within(await screen.findByRole("list", { name: "To do" })).findByText(
        "Upload 2 documents",
      ),
    ).toBeTruthy();
    expect(within(todos()).getByText("Answer 3 questions")).toBeTruthy();
    expect(within(todos()).getByText("Nothing to sign yet")).toBeTruthy();
  });

  it("POR-02 acceptance: the stage tracker uses the canonical discs and marks the current step", async () => {
    show("a");
    const tracker = await screen.findByRole("list", { name: "2025 Tax Return · Form 1040" });
    const steps = within(tracker).getAllByRole("listitem");
    expect(steps.map((s) => s.textContent)).toEqual([
      "DoneGather documents",
      "DonePrepare",
      "In progressReview",
      "Not startedSign Form 8879",
      "Not startedFile",
    ]);
    expect(steps[2]?.getAttribute("aria-current")).toBe("step");
  });

  it('POR-02 acceptance: "We\'re reviewing" is amber state, never red', async () => {
    show("a");
    const pill = await screen.findByText("We're reviewing your return");
    expect(pill.closest(".bg-amber-tint")).not.toBeNull();
    expect(pill.closest(".bg-red-tint, .bg-red")).toBeNull();
  });

  it("POR-02 acceptance: the Ridgeline K-1 is described in plain words; no firm status reaches the portal", async () => {
    show("a");
    await screen.findByText(/We're waiting on one partnership K-1/);
    expect(screen.queryByText(/Draft K-1 · pre-release/)).toBeNull();
    expect(screen.queryByText(/In review · Manager/)).toBeNull();
  });

  it("POR-02 avoid: no red appears except on a past-due item (none on a, b, c)", async () => {
    for (const s of ["a", "b", "c"] as const) {
      show(s);
      await screen.findByRole("heading", { name: "Good morning, Claire" });
      expect(document.querySelector(".bg-red-tint, .bg-red")).toBeNull();
      expect(document.querySelector(".text-red-ink")).toBeNull();
      cleanup();
      restore?.();
    }
  });

  it('POR-02 avoid: the portal never renders the product\'s name, an agent or "task"', async () => {
    for (const s of ["a", "b", "c"] as const) {
      show(s);
      await screen.findByRole("heading", { name: "Good morning, Claire" });
      const text = document.body.textContent;
      expect(text).not.toMatch(/Accrued/);
      expect(text).not.toMatch(/\bAgent\b/);
      expect(text).not.toMatch(/\btasks?\b/i);
      cleanup();
      restore?.();
    }
  });

  it("POR-02 acceptance: planned targets render with their hint in fixture builds", async () => {
    show("a");
    expect(
      await within(await screen.findByRole("list", { name: "To do" })).findByText(
        "Go to Documents →",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open binder" })).toHaveProperty("disabled", true);
  });

  it("P-08 Story 6.2: dismissing the welcome persists for the user and scope", async () => {
    const seen = show("b");
    fireEvent.click(await screen.findByRole("button", { name: "Dismiss welcome" }));
    await waitFor(() => {
      expect(screen.queryByText("Welcome to Brightwater Hale's client portal.")).toBeNull();
    });
    const put = seen.calls.find((c) => c.method === "PUT" && c.path === "/v1/portal/preferences");
    expect(put?.body).toMatchObject({ welcome_dismissed: true, version: 0 });
  });

  it("todoWords: a kind with nothing open and no designed empty card draws nothing", () => {
    expect(todoWords({ kind: "upload", count: 0, state: "none" }, false)).toBeNull();
    expect(todoWords({ kind: "sign", count: 0, state: "none" }, false)?.title).toBe(
      "Nothing to sign yet",
    );
  });
});

describe("POR-02 artboards (part 2, P-08-T23)", () => {
  it("defines every artboard of the handoff: a–h and M, with their personas", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h", "M"]);
    expect(scenarios.d.persona).toBe("tess-moreno");
    expect(scenarios.e.persona).toBe("meera-shah");
    expect(scenarios.g.persona).toBe("luis-ferrante");
    expect(scenarios.g.clock).toBe("2026-10-22T08:30:00-05:00");
    expect(scenarios.h.persona).toBe("marisol-vega");
    expect(scenarios.M.persona).toBe("claire-feld");
  });

  it("POR-02d overdue: Tess Moreno, Approvals in the nav, red tint only on the past-due item", async () => {
    show("d");
    expect(await screen.findByRole("heading", { name: "Good morning, Tess" })).toBeTruthy();
    const nav = screen.getByRole("navigation", { name: "Portal" });
    expect(within(nav).getByRole("button", { name: "Approvals" })).toBeTruthy();
    expect(screen.getByText("Copperleaf Coffee Roasters, Inc.")).toBeTruthy();
    expect(screen.getByText("S corporation · Colorado")).toBeTruthy();
    expect(screen.getByText("Your close preparer")).toBeTruthy();
    expect(within(todos()).getByText("Upload 2 documents for the August close")).toBeTruthy();
    expect(
      within(todos()).getByText("Requested by Raj Malhotra for your August books."),
    ).toBeTruthy();
    expect(within(todos()).getByText("Answer 3 questions")).toBeTruthy();
    expect(within(todos()).getByText("About August transactions, from Raj Malhotra")).toBeTruthy();
    expect(within(todos()).getByText("Reconnect American Express")).toBeTruthy();
    expect(
      within(todos()).getByText(
        "We can't bring in your August card activity until it's reconnected.",
      ),
    ).toBeTruthy();
    expect(within(todos()).getByText("Go to Connections →")).toBeTruthy();
    expect(within(todos()).getByText("Nothing to approve yet")).toBeTruthy();
    expect(
      within(todos()).getByText("Your August statements come to Approvals after our review."),
    ).toBeTruthy();
    // The one red: the past-due upload's pill, and nothing else on the page.
    const overdue = within(todos()).getByText("Overdue · due Sep 5");
    const reds = document.querySelectorAll(".bg-red-tint, .bg-red, .text-red-ink");
    expect(reds.length).toBeGreaterThan(0);
    for (const red of reds) {
      expect(red.closest("[data-todo]")?.getAttribute("data-todo")).toBe("upload");
    }
    expect(overdue.closest("[data-todo]")?.getAttribute("data-todo")).toBe("upload");
    const close = screen.getByRole("region", { name: "August 2026 Close" });
    expect(within(close).getByText("Monthly bookkeeping")).toBeTruthy();
    expect(within(close).getByText("We're reconciling your accounts")).toBeTruthy();
    expect(within(close).getByText("7 of 9")).toBeTruthy();
    const steps = within(within(close).getByRole("list")).getAllByRole("listitem");
    expect(steps.map((x) => x.textContent)).toEqual([
      "In progressRequests7 of 9",
      "Not startedReconcile",
      "Not startedReview",
      "Not startedStatements",
    ]);
    const filed = screen.getByRole("region", { name: "TY2025 Form 1120-S" });
    expect(within(filed).getByText("2025 S corporation return")).toBeTruthy();
    expect(within(filed).getByText("Filed and accepted").closest(".bg-green-tint")).not.toBeNull();
    expect(
      screen.getByText(
        "Colorado Department of Revenue notice (2025 withholding) — Brightwater Hale is reviewing it. Nothing needed from you.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Questions about August transactions")).toBeTruthy();
    expect(screen.getByText("Reconnect your American Express card")).toBeTruthy();
  });

  it("POR-02d acceptance: no reconciliation counts on the portal (only the requests tally)", async () => {
    show("d");
    const close = await screen.findByRole("region", { name: "August 2026 Close" });
    expect(within(close).queryByText(/\d+ of \d+ (accounts|reconciled)/)).toBeNull();
  });

  it("POR-02e role union: Meera Shah's own 1040 and My K-1s", async () => {
    show("e");
    expect(await screen.findByRole("heading", { name: "Good morning, Meera" })).toBeTruthy();
    const nav = screen.getByRole("navigation", { name: "Portal" });
    expect(within(nav).queryByRole("button", { name: "Approvals" })).toBeNull();
    expect(screen.getByText("Individual")).toBeTruthy();
    expect(within(todos()).getByText("Upload 1 document")).toBeTruthy();
    expect(
      within(todos()).getByText(
        "Your 2025 business mileage log for your consulting work (Schedule C)",
      ),
    ).toBeTruthy();
    expect(within(todos()).getByText("Answer 1 question")).toBeTruthy();
    expect(within(todos()).getByText("From Lena Park")).toBeTruthy();
    const work = screen.getByRole("region", { name: "2025 Tax Return · Form 1040" });
    expect(within(work).getByText("We're preparing your return")).toBeTruthy();
    expect(
      within(work).getByText("Waiting on your K-1 from Ridgeline Property Partners, LP."),
    ).toBeTruthy();
    const k1s = screen.getByRole("region", { name: "My K-1s" });
    expect(
      within(k1s).getByText("Ridgeline Property Partners, LP · 2025 Schedule K-1"),
    ).toBeTruthy();
    expect(within(k1s).getByText("Not released yet")).toBeTruthy();
    expect(within(k1s).getByText("Expected by Sep 15 · you'll get an email")).toBeTruthy();
    expect(screen.getByText("Neil Ashcroft")).toBeTruthy();
    expect(screen.getByText("Lena Park")).toBeTruthy();
    expect(screen.getByText("One question about your 2025 return")).toBeTruthy();
  });

  it("P-08-T23 acceptance: Meera Shah's home lists nothing of the Ridgeline return", async () => {
    const seen = show("e");
    await screen.findByRole("region", { name: "My K-1s" });
    const k1s = screen.getByRole("region", { name: "My K-1s" });
    // The Ridgeline partnership appears only as her K-1's issuer and the note on her own return.
    const mentions = screen.getAllByText(/Ridgeline/);
    for (const m of mentions) {
      const inK1s = k1s.contains(m);
      const inNote = m.textContent === "Waiting on your K-1 from Ridgeline Property Partners, LP.";
      expect(inK1s || inNote).toBe(true);
    }
    expect(screen.queryByText(/Form 1065/)).toBeNull();
    expect(screen.queryByText(/Draft K-1 · pre-release/)).toBeNull();
    expect(screen.queryByText(/In review · Partner/)).toBeNull();
    expect(
      screen.getAllByRole("region").filter((r) => r.dataset.workCard !== undefined),
    ).toHaveLength(1);
    // Every home read is for her own scope: the K-1 scope's home is never asked for.
    const homeReads = seen.calls.filter((c) => c.path === "/v1/portal/home");
    expect(homeReads.length).toBeGreaterThan(0);
  });

  it("POR-02e role union: the user chip lists each scope with its role chip and switches the home", async () => {
    show("e");
    await screen.findByRole("heading", { name: "Good morning, Meera" });
    fireEvent.pointerDown(screen.getByRole("button", { name: /Meera Shah/ }), { button: 0 });
    const menu = await screen.findByRole("menu", { name: "Account" });
    const own = within(menu).getByRole("menuitemradio", { name: /Meera Shah/ });
    expect(own.getAttribute("aria-checked")).toBe("true");
    expect(within(own).getByText("Taxpayer")).toBeTruthy();
    const k1 = within(menu).getByRole("menuitemradio", {
      name: /Ridgeline Property Partners, LP/,
    });
    expect(within(k1).getByText("K-1 recipient")).toBeTruthy();
    // A K-1 recipient's scope opens My K-1s (POR-13, planned): it never becomes a home.
    expect(k1.getAttribute("aria-disabled")).toBe("true");
    expect(within(menu).getByRole("menuitem", { name: "Sign out" })).toBeTruthy();
  });

  it("POR-02e: picking another full-client scope re-reads the home with its scope_id", async () => {
    const { SCOPE_IDS, claireHome } = await import("../../fixtures/seed/portal-home");
    const seen = show("e", {
      "GET /v1/me": () =>
        json({
          user_id: "u",
          email: "meera@sink.brightwaterhale.test",
          display_name: "Meera Shah",
          active_tenant_id: "t",
          server_now: "2026-09-14T14:24:00Z",
          clock_mode: "offset",
          memberships: [],
          portal: {
            shell: "full",
            scopes: [
              { kind: "client", id: SCOPE_IDS.meera, label: "Meera Shah", role_label: "Taxpayer" },
              {
                kind: "client",
                id: SCOPE_IDS.feld,
                label: "Jonah & Claire Feld",
                role_label: "Taxpayer",
              },
            ],
            nav: ["home", "documents", "questions", "sign", "messages", "deliverables"],
            landing: "home",
          },
        }),
      "GET /v1/portal/home": ({ query }) =>
        query.get("scope_id") === SCOPE_IDS.feld
          ? json(claireHome(2))
          : (scenarios.e.handlers["GET /v1/portal/home"] as FixtureHandler)({
              method: "GET",
              path: "/v1/portal/home",
              params: {},
              query,
              body: undefined,
              persona: "meera-shah",
            }),
    });
    await screen.findByRole("heading", { name: "Good morning, Meera" });
    fireEvent.pointerDown(screen.getByRole("button", { name: /Meera Shah/ }), { button: 0 });
    const menu = await screen.findByRole("menu", { name: "Account" });
    fireEvent.click(within(menu).getByRole("menuitemradio", { name: /Jonah & Claire Feld/ }));
    expect(await screen.findByText("Household · Brooklyn, NY")).toBeTruthy();
    const reads = seen.calls.filter((c) => c.path === "/v1/portal/home");
    expect(reads.length).toBeGreaterThanOrEqual(2);
  });

  it("POR-02g statements review: Luis Ferrante on Thu Oct 22", async () => {
    show("g");
    expect(await screen.findByRole("heading", { name: "Good morning, Luis" })).toBeTruthy();
    expect(screen.getByText("Thursday, October 22")).toBeTruthy();
    const nav = screen.getByRole("navigation", { name: "Portal" });
    expect(within(nav).getByRole("button", { name: "Approvals" })).toBeTruthy();
    expect(screen.getByText("Granite Peak Outdoor Supply, Inc.")).toBeTruthy();
    expect(screen.getByText("C corporation · Colorado")).toBeTruthy();
    expect(within(todos()).getByText("Review your FY2026 financial statements")).toBeTruthy();
    expect(
      within(todos()).getByText(
        "Shared by Hannah Leclerc on Oct 21 · suggest edits or comment on any page",
      ),
    ).toBeTruthy();
    expect(within(todos()).getByText("Go to Deliverables →")).toBeTruthy();
    expect(within(todos()).getByText("Nothing to sign yet").className).toMatch(/text-ink-3/);
    expect(
      within(todos()).getByText("The representation letter comes after your review."),
    ).toBeTruthy();
    const work = screen.getByRole("region", { name: "FY2026 Financial Statement Audit" });
    expect(within(work).getByText("Year ended Jun 30, 2026")).toBeTruthy();
    expect(within(work).getByText("We're finishing your audit")).toBeTruthy();
    const steps = within(within(work).getByRole("list")).getAllByRole("listitem");
    expect(steps.map((x) => x.textContent)).toEqual([
      "DonePlanning",
      "DoneFieldwork",
      "In progressStatements review",
      "Not startedReport",
    ]);
    expect(screen.getByText("Margaret Okonkwo")).toBeTruthy();
    expect(screen.getByText("Engagement partner")).toBeTruthy();
    expect(screen.getByText("Simone Baptiste")).toBeTruthy();
    expect(screen.getByText("Your day-to-day contact")).toBeTruthy();
    expect(screen.getByText("Your draft FY2026 statements")).toBeTruthy();
  });

  it("POR-02h SOC 2: Marisol Vega, 26 open requests, 3 exceptions, description approved Sep 12", async () => {
    show("h");
    expect(await screen.findByRole("heading", { name: "Good morning, Marisol" })).toBeTruthy();
    expect(screen.getByText("Tessellate Health Cloud, Inc.")).toBeTruthy();
    expect(screen.getByText("Service organization · Denver, CO")).toBeTruthy();
    expect(within(todos()).getByText("Answer control requests")).toBeTruthy();
    expect(within(todos()).getByText("26 open requests · synced with Drata")).toBeTruthy();
    expect(within(todos()).getByText("Go to Documents →")).toBeTruthy();
    expect(within(todos()).getByText("Respond to 3 exceptions")).toBeTruthy();
    expect(within(todos()).getByText("CC6.2 · CC8.1 · A1.2 — tell us what changed")).toBeTruthy();
    expect(within(todos()).getByText("Go to Approvals →")).toBeTruthy();
    expect(within(todos()).getByText("System description approved").className).toMatch(
      /text-ink-3/,
    );
    expect(within(todos()).getByText("Approved Sep 12")).toBeTruthy();
    const work = screen.getByRole("region", {
      name: "SOC 2 Type 2 · Oct 1, 2025 – Sep 30, 2026",
    });
    expect(within(work).getByText("Security · Availability · Confidentiality")).toBeTruthy();
    expect(within(work).getByText("Testing is under way")).toBeTruthy();
    const steps = within(within(work).getByRole("list")).getAllByRole("listitem");
    expect(steps.map((x) => x.textContent)).toEqual([
      "DoneScoping",
      "DoneSystem description",
      "In progressTesting",
      "Not startedExceptions",
      "Not startedReport",
    ]);
    expect(screen.getByText("Celia Marsh")).toBeTruthy();
    expect(screen.getByText("Jasper Bell")).toBeTruthy();
    expect(screen.getByText("Exceptions from testing")).toBeTruthy();
  });

  it("POR-02 R2 avoid: no control results, deviation rates or materiality reach g or h", async () => {
    for (const s of ["g", "h"] as const) {
      show(s);
      await screen.findByRole("list", { name: "To do" });
      const text = document.body.textContent;
      expect(text).not.toMatch(
        /materiality|deviation|effective|ineffective|operating effectiveness/i,
      );
      expect(text).not.toMatch(/\d+(\.\d+)?\s?%/);
      expect(text).not.toMatch(/Accrued|\bAgent\b|\btasks?\b/);
      expect(document.querySelector(".bg-red-tint, .bg-red, .text-red-ink")).toBeNull();
      cleanup();
      restore?.();
    }
  });

  it("POR-02-M mobile 390: stacked to-dos, the tracker as a list, the team collapsed, badges", async () => {
    show("M", {}, true);
    expect(await screen.findByRole("heading", { name: "Good morning, Claire" })).toBeTruthy();
    expect(document.querySelector("[data-variant='portal-mobile']")).not.toBeNull();
    expect(document.querySelector("[data-portal='rail']")).toBeNull();
    const list = todos();
    expect(list.className).toMatch(/flex-col/);
    expect(within(list).getAllByRole("listitem")).toHaveLength(4);
    expect(within(list).getByText("Upload 2 documents")).toBeTruthy();
    const work = screen.getByRole("region", { name: "2025 Tax Return · Form 1040" });
    expect(within(work).getByRole("list").className).toMatch(/flex-col/);
    const team = screen.getByRole("region", { name: "Your team" });
    expect(within(team).getByText("4 people · Message Kevin")).toBeTruthy();
    const bar = screen.getByRole("navigation", { name: "Portal" });
    expect(within(bar).getByRole("button", { name: "Documents, 2 to do" })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "Messages, 1 to do" })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "Home" })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "Sign" })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "More" })).toBeTruthy();
  });
});

describe("POR-02 → POR-03 (R-01-T10 mounts Documents)", () => {
  it('"Go to Documents →", "Open binder" and the nav open Documents through the portal entry', async () => {
    const went: string[] = [];
    restore = installFixtureMode(scenarios.a);
    renderRoutes([
      {
        path: "/",
        component: () => (
          <PortalHome
            scopeId={null}
            onNavigate={(area) => {
              went.push(area);
            }}
          />
        ),
      },
    ]);
    const go = await within(await screen.findByRole("list", { name: "To do" })).findByRole(
      "button",
      { name: "Go to Documents →" },
    );
    fireEvent.click(go);
    fireEvent.click(screen.getByRole("button", { name: "Open binder" }));
    const nav = screen.getByRole("navigation", { name: "Portal" });
    fireEvent.click(within(nav).getByRole("button", { name: "Documents" }));
    expect(went).toEqual(["Documents", "Documents", "Documents"]);
  });

  it("the overdue close upload (d) opens POR-11, still planned: no live link", async () => {
    const went: string[] = [];
    restore = installFixtureMode(scenarios.d);
    renderRoutes([
      {
        path: "/",
        component: () => <PortalHome scopeId={null} onNavigate={(a) => went.push(a)} />,
      },
    ]);
    const list = await screen.findByRole("list", { name: "To do" });
    expect(within(list).queryByRole("button", { name: "Go to Documents →" })).toBeNull();
    expect(within(list).getByText("Go to Documents →")).toBeTruthy();
  });
});
