// POR-02 · Portal home, part 1 (P-08-T15). One test per artboard part 1 builds (a, b, c, f) on
// its fixture scenario, the contract's acceptance bullets and AVOID lines for them, P-08 Story
// 6.2 (the welcome dismissal), and the task's acceptance: "Scenario tests for a, b, c and f pass,
// planned targets render only in fixture builds, and no red appears except on a past-due item."
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

function show(state: Por02State, over: Record<string, FixtureHandler> = {}): Seen {
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
  renderRoutes([{ path: "/", component: () => <PortalHome scopeId={null} /> }]);
  return seen;
}

function todos(): HTMLElement {
  return screen.getByRole("list", { name: "To do" });
}

describe("POR-02 artboards (part 1)", () => {
  it("defines a, b, c and f as Claire Feld; b on her first visit", () => {
    expect(STATES).toEqual(["a", "b", "c", "f"]);
    for (const s of STATES) expect(scenarios[s].persona).toBe("claire-feld");
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
