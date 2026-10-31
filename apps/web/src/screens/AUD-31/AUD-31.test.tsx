// AUD-31 · Trial balance mapping (A-03-T12). Acceptance: "AUD-31 f matches the artboard at Tier C
// with MAPPED 128 of 128 and TB BALANCED 1 of 1 tie, a′–e′ hold Tier D computed styles with no
// Accept or Request changes control, and AUD-06 groups Granite Peak's lines by FS line once the
// set is confirmed." Tier C/D pixels are the visual suite's; here the content, the controls, the
// writes, and AUD-06's grouping (AUD-06/FsLine.test.tsx).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { REVIEW_ACCOUNT } from "../../fixtures/seed/aud31";
import { renderRoutes } from "../../testing/support";
import { AUD31 } from ".";
import { type Aud31State, GRANITE_MAPPING_ENGAGEMENT, STATES, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function show(state: Aud31State): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  renderRoutes([
    { path: "/", component: () => <AUD31 engagementId={GRANITE_MAPPING_ENGAGEMENT} /> },
  ]);
  return calls;
}

async function table(): Promise<HTMLElement> {
  return screen.findByRole("table", { name: "Trial balance mapping" });
}

function tally(label: string): string {
  const strip = document.querySelector('[data-tally-strip=""]');
  const card = [...(strip?.querySelectorAll("li") ?? [])].find((li) =>
    li.textContent.toUpperCase().startsWith(label.toUpperCase()),
  );
  return card?.textContent ?? "";
}

/** DV-B2: no Accept and no Request changes… anywhere (no suggestions without the TB mapper). */
function noSuggestionControls(): void {
  expect(screen.queryByRole("button", { name: /^Accept/u })).toBeNull();
  expect(screen.queryByRole("button", { name: /Request changes/u })).toBeNull();
}

describe("AUD-31", () => {
  it("builds f, a′–e′ and the C-20 states", () => {
    expect(STATES).toEqual([
      "f",
      "a2",
      "b2",
      "c2",
      "d2",
      "e2",
      "off",
      "loading",
      "error",
      "not_allowed",
    ]);
  });

  it("f: Confirmed Sep 11, MAPPED 128 of 128, NEED REVIEW 0, TB BALANCED 1 of 1 tie; groups by grouping › FS line", async () => {
    show("f");
    const t = await table();
    expect(await screen.findByText("Confirmed Sep 11")).toBeTruthy();
    expect(tally("Mapped")).toContain("128 of 128");
    expect(tally("Need review")).toContain("0");
    expect(tally("TB balanced")).toContain("1 of 1");
    expect(tally("TB balanced")).toContain("tie");
    expect(screen.getByText("Granite Peak Outdoor Supply · FY2026")).toBeTruthy();
    // DV-B1: the run line names the code run and carries no atom.
    const run = screen.getByText(/^Mapping rules ran/u);
    expect(run.querySelector("svg")).toBeNull();
    const groups = [...t.querySelectorAll("[data-mapping-group]")].map((g) => g.textContent);
    expect(groups[0]).toBe("Cash");
    expect(groups).toContain("Property, plant & equipment");
    expect(groups.at(-1)).toBe("Interest");
    expect(screen.getByRole("button", { name: "Open TB & leadsheets ›" })).toBeTruthy();
    expect(
      screen.getByText("Mapping confirmed by Caleb Dunn on Sep 11 · 128 accounts"),
    ).toBeTruthy();
    noSuggestionControls();
  });

  it("f: a group opens on its rows and the server's subtotal; a row lights its source row", async () => {
    show("f");
    const t = await table();
    fireEvent.click(within(t).getByRole("button", { name: "Debt" }));
    const rows = await waitFor(() => {
      const found = t.querySelectorAll("[data-mapping-row]");
      if (found.length === 0) throw new Error("no rows");
      return found;
    });
    expect([...rows].map((r) => r.getAttribute("data-mapping-row"))).toEqual([
      "revolver_front_range_bank",
      "term_loan",
    ]);
    expect(t.querySelector('[data-mapping-subtotal="debt"]')?.textContent).toContain(
      "(9,700,000)",
    );
    fireEvent.click(rows[1] as HTMLElement);
    const lit = await waitFor(() => {
      const found = document.querySelector("tr[data-lit]");
      if (found === null) throw new Error("not lit");
      return found;
    });
    expect(lit.textContent).toContain("Term loan");
    expect(lit.textContent).toContain("3,200,000");
  });

  it("a′: needs review without suggestions: the band, NEED REVIEW 1, Change ⌄ only; Confirm waits", async () => {
    show("a2");
    const t = await table();
    expect(await screen.findByText("1 need review")).toBeTruthy();
    const band = t.querySelector('[data-mapping="review"]');
    expect(band?.textContent).toContain("Needs review · 1");
    expect(band?.querySelector(`[data-mapping-row="${REVIEW_ACCOUNT}"]`)?.textContent).toContain(
      "Other assets",
    );
    expect(within(band as HTMLElement).getByRole("button", { name: /Change/u })).toBeTruthy();
    const confirm = screen.getByRole<HTMLButtonElement>("button", {
      name: "Confirm and continue",
    });
    expect(confirm.disabled).toBe(true);
    noSuggestionControls();
  });

  it("b′: the rules running: the importing card and the run read polled", async () => {
    const calls = show("b2");
    expect(await screen.findByText("Mapping trial balance accounts")).toBeTruthy();
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/run"))).toBe(true);
    });
    expect(tally("Mapped")).toContain("Pending");
  });

  it("c′: change made: Edited by CD, Confidence —; Confirm asks and posts the hash seen", async () => {
    const calls = show("c2");
    const t = await table();
    fireEvent.click(within(t).getByRole("button", { name: "Other assets" }));
    expect(await within(t).findByText("Edited by CD")).toBeTruthy();
    const confirm = await screen.findByRole<HTMLButtonElement>("button", {
      name: "Confirm and continue",
    });
    expect(confirm.getAttribute("data-human-verb")).toBe("Adopt");
    fireEvent.click(confirm);
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog.textContent).toContain(
      "Adopt 128 mappings (1 edited) and mark the mapping Prepared?",
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/confirm"))).toBe(true);
    });
    const body = calls.find((c) => c.path.endsWith("/confirm"))?.body as { seen_hash: string };
    expect(body.seen_hash).toMatch(/^[0-9a-f]{64}$|^sha256:/u);
    // d′: confirmed in this session.
    expect(await screen.findByText(/^Mapping confirmed by Caleb Dunn · /u)).toBeTruthy();
  });

  it("e′: changed after sign-off: the amber banner and pill", async () => {
    show("e2");
    await table();
    expect(screen.getAllByText("Changed after sign-off").length).toBeGreaterThan(0);
    expect(document.querySelector('[data-aud31="stale"]')).not.toBeNull();
  });

  it("C-20: off, error, not allowed", async () => {
    show("off");
    // The pane title and the C-20 state both name the screen.
    expect((await screen.findAllByText(/Trial balance mapping/u)).length).toBeGreaterThan(0);
    expect(screen.queryByRole("table", { name: "Trial balance mapping" })).toBeNull();
    cleanup();
    restore?.();
    show("error");
    expect(await screen.findByRole("button", { name: /Try again|Retry/u })).toBeTruthy();
    cleanup();
    restore?.();
    show("not_allowed");
    await waitFor(() => {
      expect(screen.queryByRole("table", { name: "Trial balance mapping" })).toBeNull();
    });
    expect(document.body.textContent).not.toContain("128");
  });
});
