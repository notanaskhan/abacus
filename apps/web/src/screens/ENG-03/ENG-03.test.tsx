// ENG-03 · New engagement wizard, core (P-07-T21). One test per artboard this task builds (a, b,
// c, d, f) on its fixture scenario, the contract's acceptance bullets for them, P-07 Story 6.3,
// and the task's acceptance: "Scenarios a to d and f pass, Next stays disabled with the reason
// announced while G1 is unmet, and the f tooltip text is verbatim."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { ENG03, catalogueGroups } from ".";
import {
  CLOCK_AUG_24,
  CLOCK_SEP_8,
  type Eng03State,
  OPENS,
  STATES,
  TYPES,
  freshScenario,
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
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Eng03State, onCreated?: (id: string) => void): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = freshScenario(state);
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
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ENG03 draftId={OPENS[state]} {...(onCreated === undefined ? {} : { onCreated })} />
      ),
    },
  ]);
  return seen;
}

function wizard(): HTMLElement {
  return screen.getByRole("dialog");
}

function next(): HTMLButtonElement {
  return within(wizard()).getByRole<HTMLButtonElement>("button", { name: "Next" });
}

describe("ENG-03 artboards", () => {
  it("defines a, b, c, d and f as Hannah Leclerc; d on Aug 24", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "f"]);
    for (const s of STATES) expect(scenarios[s].persona).toBe("hannah-leclerc");
    expect(scenarios.d.clock).toBe(CLOCK_AUG_24);
    expect(scenarios.a.clock).toBe(CLOCK_SEP_8);
  });

  it("ENG-03a step 1: Fairhaven, EBP audit selected, G1 met", async () => {
    show("a");
    expect(await screen.findByRole("heading", { name: /New engagement/ })).toBeTruthy();
    expect(within(wizard()).getByText("Draft · saved 9:39 AM")).toBeTruthy();
    const steps = within(wizard()).getByRole("navigation", { name: "Steps" });
    expect(
      within(steps)
        .getAllByRole("listitem")
        .map((s) => s.textContent),
    ).toEqual([
      expect.stringContaining("Client & type"),
      expect.stringContaining("Standards & methodology"),
      expect.stringContaining("Period & deadlines"),
      expect.stringContaining("Team & independence"),
      expect.stringContaining("Binder & portal"),
      expect.stringContaining("Letter & review"),
    ]);
    expect(await within(wizard()).findByText("Fairhaven Foods, Inc.")).toBeTruthy();
    expect(within(wizard()).getByText("Fairhaven Foods 401(k) Plan")).toBeTruthy();
    expect(within(wizard()).getByText("Continuance approved · Aug 28, 2026 ✓")).toBeTruthy();
    expect(
      await within(wizard()).findByText(
        "G1 Continuance approved — Margaret Okonkwo · Aug 28, 2026",
      ),
    ).toBeTruthy();
    expect(within(wizard()).getByText("G2 Team independence — step 4")).toBeTruthy();
    expect(within(wizard()).getByText("G3 Letter signed — after Create")).toBeTruthy();
    expect(
      within(wizard())
        .getByRole("button", { name: /EBP audit/ })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(next().disabled).toBe(false);
  });

  it("ENG-03b step 2: standards and the §103(a)(3)(C) scope", async () => {
    show("b");
    expect(
      await within(await screen.findByRole("dialog")).findByText(
        "GAAS nonissuer · periods ending 12/31/2025 · AU-C 703",
      ),
    ).toBeTruthy();
    expect(
      within(wizard()).getByRole("tab", { name: "§103(a)(3)(C)" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("ENG-03c step 4: five team rows, Fiona Nash requested, the EQR not on the team", async () => {
    show("c");
    expect(
      await within(await screen.findByRole("dialog")).findByText(
        "Fiona Nash cannot be assigned or sign off until she confirms independence (G2).",
      ),
    ).toBeTruthy();
    expect(within(wizard()).getAllByText("✓ Confirmed")).toHaveLength(4);
    expect(within(wizard()).getAllByText("○ Requested")).toHaveLength(1);
    expect(
      within(wizard()).getByText("EQR eligible — not on team, no cooling-off conflict"),
    ).toBeTruthy();
    expect(within(wizard()).getByText("Senior (in-charge)")).toBeTruthy();
  });

  it("ENG-03d G1 unmet: Next disabled, the reason announced, Start acceptance", async () => {
    const seen = show("d");
    const reason = await within(await screen.findByRole("dialog")).findByText(
      "Acceptance is not approved yet (G1).",
    );
    expect(reason.closest("[role='status']")).not.toBeNull();
    expect(
      (await within(wizard()).findAllByText("Granite Peak Outdoor Supply, Inc.")).length,
    ).toBeGreaterThan(0);
    expect(next().disabled).toBe(true);
    fireEvent.click(within(wizard()).getByRole("button", { name: "Start acceptance" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/start-acceptance"))).toBe(true);
    });
  });

  it("ENG-03f the Single audit tile: Coming soon, never selectable, its tooltip verbatim", async () => {
    show("f");
    const dialog = await screen.findByRole("dialog");
    const tile = (await within(dialog).findByText("Single audit")).closest(
      "[aria-disabled='true']",
    );
    if (tile === null) throw new Error("no coming-soon tile");
    expect(within(tile as HTMLElement).getByText("Coming soon")).toBeTruthy();
    fireEvent.focus(tile);
    fireEvent.pointerEnter(tile);
    expect(
      (
        await screen.findAllByText(
          "Not in this release. Run single audits outside Accrued for now.",
        )
      ).length,
    ).toBeGreaterThan(0);
  });
});

describe("ENG-03 acceptance", () => {
  it("P-07 Story 6.3: the catalogue never holds single_audit; only the static tile does", () => {
    expect(TYPES.items.map((i) => i.code)).not.toContain("single_audit");
    const groups = catalogueGroups(TYPES.items);
    const counts = groups.map((g) => g.types.length);
    // Tax 8 · Audit & assurance 8 selectable + 1 static Coming soon tile · CAS & Advisory 2.
    expect(counts).toEqual([8, 9, 2]);
    expect(groups[1]?.types.filter((t) => t.comingSoon === true).map((t) => t.label)).toEqual([
      "Single audit",
    ]);
  });

  it("ENG-03 acceptance (R2): AUP, SOC 1 and SOC 2 are in the catalogue; SOC cards need attest", () => {
    const codes = TYPES.items.map((i) => i.code);
    expect(codes).toEqual(expect.arrayContaining(["agreed_upon_procedures", "soc1", "soc2"]));
    expect(TYPES.items.filter((i) => i.entitlement === "attest").map((i) => i.code)).toEqual([
      "soc1",
      "soc2",
    ]);
  });

  it("Next moves the draft a step with the version seen (autosave)", async () => {
    const seen = show("a");
    await within(await screen.findByRole("dialog")).findByText("Fairhaven Foods, Inc.");
    fireEvent.click(next());
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    expect(seen.calls.find((c) => c.method === "PATCH")?.body).toEqual({
      step: "standards_methodology",
      seen_version: 3,
    });
    expect(await within(wizard()).findByText("Draft · saved 9:40 AM")).toBeTruthy();
  });

  it('Escape asks "Discard this draft?" and Discard deletes it', async () => {
    const seen = show("a");
    await within(await screen.findByRole("dialog")).findByText("Fairhaven Foods, Inc.");
    fireEvent.keyDown(wizard(), { key: "Escape" });
    const ask = await screen.findByRole("dialog", { name: "Discard this draft?" });
    fireEvent.click(within(ask).getByRole("button", { name: "Discard" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "DELETE")).toBe(true);
    });
  });

  it("Create is the person's click on the last step and opens the new engagement", async () => {
    const onCreated = vi.fn();
    const seen = show("a", onCreated);
    await within(await screen.findByRole("dialog")).findByText("Fairhaven Foods, Inc.");
    for (let i = 0; i < 5; i += 1) {
      fireEvent.click(next());
      await waitFor(() => {
        expect(seen.calls.filter((c) => c.method === "PATCH")).toHaveLength(i + 1);
      });
    }
    fireEvent.click(await within(wizard()).findByRole("button", { name: "Create" }));
    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledTimes(1);
    });
    expect(toastStore.list().map((t) => t.text)).toContain(
      "Engagement created · PY2025 EBP Audit",
    );
  });
});
