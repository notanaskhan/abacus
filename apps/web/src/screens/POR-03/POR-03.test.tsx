// POR-03 · Documents, part 1 (R-01-T06). One test per artboard part 1 builds (a, c, e, f, g, h)
// on its fixture scenario, the contract's acceptance and AVOID lines for them, and the task's
// acceptance: "Scenario tests for a, c, e, f, g and h pass with axe clean and no firm status word,
// agent name or bell in the DOM." axe runs in e2e/screens/POR-03.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { PortalDocuments } from ".";
import { ARTBOARD as ALL_ARTBOARDS, scenarios as all } from "../../fixtures/scenarios/POR-03";
import { type Por03State, STATES, scenarios } from "./scenarios";

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

function show(state: Por03State | "c2"): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = state === "c2" ? all.c2 : scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const board = ALL_ARTBOARDS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <PortalDocuments
          binderId={board.binderId}
          hold={{
            ...(board.uploads === undefined ? {} : { uploads: board.uploads }),
            ...(board.ignoreOpenOn === undefined ? {} : { ignoreOpenOn: board.ignoreOpenOn }),
          }}
        />
      ),
    },
  ]);
  return seen;
}

async function row(title: string): Promise<HTMLElement> {
  const text = await screen.findByText(title);
  const el = text.closest<HTMLElement>("[data-request]");
  if (el === null) throw new Error(`no row ${title}`);
  return el;
}

const FIRM_WORDS = [
  /Accrued/,
  /\bAgent\b/,
  /Uploaded – needs review/,
  /Received ✓/,
  /In review/,
  /confidence/i,
  /Matched \d+%/,
  /Pending incorporation/,
];

function noFirmWords(): void {
  const text = document.body.textContent;
  for (const word of FIRM_WORDS) expect(text).not.toMatch(word);
  const labels = [...document.querySelectorAll("[aria-label],[title],[alt],[placeholder]")]
    .flatMap((el) => ["aria-label", "title", "alt", "placeholder"].map((a) => el.getAttribute(a)))
    .join(" ");
  for (const word of FIRM_WORDS) expect(labels).not.toMatch(word);
  // No bell (DEC-58 d).
  expect(screen.queryByRole("button", { name: /notification/i })).toBeNull();
  expect(document.querySelector("[data-icon='bell']")).toBeNull();
}

describe("POR-03 artboards (part 1)", () => {
  it("defines a, c, e, f, g and h as Claire Feld at E0", () => {
    expect(STATES).toEqual(["a", "c", "e", "f", "g", "h"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe("claire-feld");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("POR-03a default: two requests open (Intake 2), two files uploading", async () => {
    show("a");
    expect(await screen.findByText("Form 1095-C From Mercer Hill Health")).toBeTruthy();
    const open = document.querySelectorAll("[data-open-request]");
    expect(open).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^Ignore / })).toHaveLength(2);
    expect(screen.getAllByText("Received by email Aug 3")).toHaveLength(2);
    expect(screen.getByText("Jonah uploaded Aug 5")).toBeTruthy();
    expect(screen.getByText("You uploaded Aug 7")).toBeTruthy();
    expect(
      screen.getByText(
        "Brightwater Hale prepares this K-1 and adds it for you. Nothing to upload.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Uploading 2 files…")).toBeTruthy();
    expect(screen.getByText("Feld_2025_Estimated_Payments.pdf")).toBeTruthy();
    expect(screen.getByText("Feld_2025_IT2105_Confirmations.pdf")).toBeTruthy();
    const done = screen.getByRole("button", { name: "Mark as Done" });
    expect(done.getAttribute("data-ready")).toBe("false");
    expect(screen.getByRole("button", { name: "Upload something else" })).toBeTruthy();
    noFirmWords();
  });

  it("POR-03a ticks the rail by the rule and lists the closed 2024 binder", async () => {
    show("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    const rail = screen.getByRole("listbox", { name: /categor/i });
    const ticked = within(rail)
      .getAllByRole("option")
      .filter((o) => o.getAttribute("data-done") === "true")
      .map((o) => o.textContent);
    expect(ticked).toEqual([
      "Personal & Household Information",
      "Income Sources",
      "Home & Property",
      "Charitable & Donations",
    ]);
    fireEvent.click(screen.getByRole("button", { name: /2025 Binder/ }));
    const menu = screen.getByRole("menu", { name: "Binder" });
    expect(within(menu).getByRole("menuitemradio", { name: "2024 Binder (closed)" })).toBeTruthy();
  });

  it("POR-03c: the estimated payments read Suggested — Brightwater Hale will confirm", async () => {
    show("c");
    const est = await row(
      "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    );
    expect(within(est).getByText("Feld_2025_Estimated_Payments.pdf")).toBeTruthy();
    expect(within(est).getByText("Feld_2025_IT2105_Confirmations.pdf")).toBeTruthy();
    expect(within(est).getByText("You uploaded Sep 14")).toBeTruthy();
    expect(within(est).getByText("Suggested — Brightwater Hale will confirm")).toBeTruthy();
    expect(within(est).queryByText("Matched to this request")).toBeNull();
    expect(document.querySelectorAll("[data-open-request]")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Mark as Done" }).getAttribute("data-ready")).toBe(
      "false",
    );
    noFirmWords();
  });

  it("POR-03e: marked done, the green-tint banner with Undo, and Undo reaches the server", async () => {
    const seen = show("e");
    expect(
      await screen.findByText("Marked done Sep 14 · Brightwater Hale will review your documents"),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/mark-done/undo"))).toBe(true);
    });
    noFirmWords();
  });

  it("POR-03f: Ignore holds the three reasons and a note; choosing one ignores with its code", async () => {
    const seen = show("f");
    const menu = await screen.findByRole("menu", { name: "Ignore" });
    const reasons = within(menu)
      .getAllByRole("menuitem")
      .map((b) => b.textContent);
    expect(reasons).toEqual([
      "Not applicable this year",
      "Already sent another way",
      "I don’t have this",
    ]);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "No 1095-C this year." } });
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Already sent another way" }));
    await waitFor(() => {
      const call = seen.calls.find((c) => c.path.endsWith("/ignore"));
      expect(call?.body).toEqual({ reason: "sent_another_way", note: "No 1095-C this year." });
    });
    const form = await row("Form 1095-C From Mercer Hill Health");
    expect(within(form).getByRole("button", { name: "Undo" })).toBeTruthy();
    noFirmWords();
  });

  it("POR-03g: returned by the firm, red-tint, with Kevin Osei's note and Upload…", async () => {
    show("g");
    const form = await row("Form 1095-C From Mercer Hill Health");
    const pill = within(form).getByText("Returned · wrong year");
    expect(pill.className).toContain("bg-red-tint");
    expect(
      within(form).getByText("This is the 2024 form. We need the 2025 Form 1095-C. — Kevin Osei"),
    ).toBeTruthy();
    expect(within(form).getByText("Feld_1095C_2024.pdf")).toBeTruthy();
    expect(within(form).getByRole("button", { name: "Upload…" })).toBeTruthy();
    noFirmWords();
  });

  it("POR-03h: nothing requested — You’re all caught up.", async () => {
    show("h");
    expect(await screen.findByText("You’re all caught up.")).toBeTruthy();
    expect(screen.getByText("Brightwater Hale hasn’t requested anything new.")).toBeTruthy();
    noFirmWords();
  });
});

describe("POR-03 behaviour", () => {
  it("Withdraw asks with the DF-15 line and withdraws Claire's own unaccepted file", async () => {
    const seen = show("a");
    const gifts = await row("2025 donation receipts and acknowledgment letters");
    fireEvent.click(
      within(gifts).getByRole("button", { name: "Withdraw Feld_2025_Donations.pdf" }),
    );
    expect(
      screen.getByText(
        "Withdraw this file? Brightwater Hale’s team won’t use it. It’s kept securely for 30 days, then erased.",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "Withdraw file" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/withdraw"))).toBe(true);
    });
  });

  it("no Withdraw on an emailed or another contact's file", async () => {
    show("a");
    const w2 = await row("2025 W-2 From Mercer Hill Health");
    expect(within(w2).queryByRole("button", { name: /^Withdraw/ })).toBeNull();
    const halvard = await row("2025 Consolidated 1099 From Halvard Securities (Acct ••3318)");
    expect(within(halvard).queryByRole("button", { name: /^Withdraw/ })).toBeNull();
  });

  it("Mark as Done turns olive once nothing is open, then marks the binder with a banner", async () => {
    // c2's data (part 2's artboard): the emailed 1095-C filed, nothing open.
    const seen = show("c2");
    const done = await screen.findByRole("button", { name: "Mark as Done" });
    expect(done.getAttribute("data-ready")).toBe("true");
    fireEvent.click(done);
    expect(
      await screen.findByText("Marked done Sep 14 · Brightwater Hale will review your documents"),
    ).toBeTruthy();
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/mark-done"))).toBe(true);
    });
  });

  it("the closed 2024 binder opens read-only", async () => {
    show("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    fireEvent.click(screen.getByRole("button", { name: /2025 Binder/ }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "2024 Binder (closed)" }));
    await waitFor(() => {
      expect(screen.queryByText("Form 1095-C From Mercer Hill Health")).toBeNull();
    });
    expect(screen.queryByRole("button", { name: "Mark as Done" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Ignore / })).toBeNull();
    expect(screen.queryByRole("button", { name: "Upload…" })).toBeNull();
  });
});

describe("POR-03 AVOID", () => {
  it("no red on a requested row; only Returned uses red-tint", async () => {
    show("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    for (const el of document.querySelectorAll<HTMLElement>('[data-status="req"]')) {
      const classes = [el, ...el.querySelectorAll<HTMLElement>("*")]
        .map((x) => x.getAttribute("class") ?? "")
        .join(" ");
      expect(classes).not.toMatch(/\b(bg|text)-red/);
    }
  });

  it("no checkboxes and no confidence percentages", async () => {
    show("c");
    await screen.findByText("Suggested — Brightwater Hale will confirm");
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/\d+%/);
  });
});
