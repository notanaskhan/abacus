// ADM-05 · Consent registry (§7216) (T-01-T13, part 1). One test per built artboard (a, b, f,
// g) on its fixture scenario (SPEC-501 AC-11; T-01 §3.1), plus: the tiles foot to 218, a
// standard set reads as one row of two consents, and no Re-request control exists on a declined
// row. axe runs in the Playwright walk, not here.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ConsentRegistryPage } from ".";
import { type Adm05State, OPENS, scenarios } from "./scenarios";

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

function show(state: Adm05State, initial: string = OPENS[state]): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ConsentRegistryPage initial={initial} />
    </QueryClientProvider>,
  );
}

async function rows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole("table");
  return within(table).getAllByRole("row").slice(1);
}

describe("ADM-05 a · default", () => {
  it("foots the tiles to 218 and shows 14 rows needs attention first", async () => {
    show("a");
    const tiles = await screen.findByRole("group", { name: "Consents by status" });
    const counts = within(tiles).getAllByRole("button");
    expect(await screen.findByText("Consents · 218")).toBeTruthy();
    expect(within(tiles).getByText("212")).toBeTruthy();
    expect(counts.length).toBe(6);
    const shown = await rows();
    expect(shown).toHaveLength(14);
    expect(shown[0]?.textContent).toContain("Morgan & Kai Ferris");
    expect(shown[0]?.textContent).toContain("Requested · 1 of 2 signed");
    expect(shown[0]?.textContent).toContain("Envelope due Sep 23");
    expect(shown[1]?.textContent).toContain("No re-solicitation · prepared without agents");
    expect(shown[2]?.textContent).toContain("Expired");
    expect(screen.getByText("14 of 218 consents")).toBeTruthy();
    expect(
      screen.getByText(/Return information withheld from agents for 3 clients\./),
    ).toBeTruthy();
    expect(screen.getByText(/210 AI-use consents expire Dec 31, 2026/)).toBeTruthy();
  });

  it("shows a standard set as one row of two consents, recipients from the register", async () => {
    show("a");
    const feld = (await rows()).find((r) => r.textContent.includes("Jonah & Claire Feld"));
    expect(feld?.textContent).toContain("Use · AI disclosure (2 consents)");
    expect(feld?.textContent).toContain("Amazon Web Services (Bedrock) (US)");
    expect(feld?.textContent).toContain("Signed · expires Dec 31 2026");
  });

  it("offers no Re-request control on a declined row", async () => {
    show("a");
    const stein = (await rows()).find((r) => r.textContent.includes("Harold Stein"));
    expect(stein).toBeDefined();
    if (stein === undefined) return;
    expect(within(stein).queryByRole("button", { name: /request/i })).toBeNull();
    expect(stein.textContent).not.toMatch(/re-?request/i);
    expect(
      within(stein).getByRole<HTMLInputElement>("checkbox", { name: "Select Harold Stein" })
        .disabled,
    ).toBe(true);
  });
});

describe("ADM-05 b · expiring", () => {
  it("filters to Rao (16 days) and Osterberg (22 days)", async () => {
    show("b");
    expect(await screen.findByText("Consents · 2")).toBeTruthy();
    const shown = await rows();
    expect(shown.map((r) => r.getAttribute("data-row"))).toEqual([
      "Sunil & Asha Rao",
      "Benjamin Osterberg",
    ]);
    expect(shown[0]?.textContent).toContain("Expiring · 16 days");
    expect(shown[1]?.textContent).toContain("Expiring · 22 days");
  });
});

describe("ADM-05 f · no matches", () => {
  it("says nothing matches and how to see all 218", async () => {
    show("f");
    expect(await screen.findByText("No consents match.")).toBeTruthy();
    expect(screen.getByText("Clear filters to see all 218.")).toBeTruthy();
  });
});

describe("ADM-05 g · 3 selected", () => {
  it("shows the selection bar for Iyer, Rao and Osterberg", async () => {
    show("g");
    await rows();
    for (const name of ["Priyanka & Sam Iyer", "Sunil & Asha Rao", "Benjamin Osterberg"]) {
      fireEvent.click(screen.getByRole("checkbox", { name: `Select ${name}` }));
    }
    const bar = await screen.findByRole("region", { name: "3 selected" });
    expect(within(bar).getByText("Renew 3…")).toBeTruthy();
    fireEvent.click(within(bar).getByRole("button", { name: "Clear" }));
    expect(screen.queryByRole("region", { name: "3 selected" })).toBeNull();
  });
});

describe("ADM-05 links (DEC-1273)", () => {
  it("a client name opens CLI-05's Consents section for that client", async () => {
    show("a");
    const link = await screen.findByRole("link", { name: "Morgan & Kai Ferris" });
    expect(link.getAttribute("href")).toMatch(
      /^\/clients\/[0-9a-f-]{36}\/tax-profile\/consents$/u,
    );
  });
});
