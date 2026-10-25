// ENG-03 · New engagement wizard (P-07-T21 core; P-07-T34 e, g, h and the type-shaped steps). One
// test per artboard on its fixture scenario, the contract's acceptance bullets for them, P-07 Story 6.3,
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
  CLOCK_MAY_11,
  CLOCK_SEP_14,
  CLOCK_SEP_14_951,
  CLOCK_SEP_8,
  CONSENTS,
  FERRIS_DUPLICATE,
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

function show(
  state: Eng03State,
  onCreated?: (id: string) => void,
  extra: { onOpen?: (id: string) => void; consents?: boolean } = {},
): Seen {
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
        <ENG03
          draftId={OPENS[state]}
          {...(onCreated === undefined ? {} : { onCreated })}
          {...(extra.onOpen === undefined ? {} : { onOpen: extra.onOpen })}
          {...(extra.consents === true ? { consents: CONSENTS[state] } : {})}
        />
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
  it("defines a–h: Hannah Leclerc a–f (d on Aug 24, e on Sep 14), Margaret g, Celia h", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h"]);
    for (const s of ["a", "b", "c", "d", "e", "f"] as const)
      expect(scenarios[s].persona).toBe("hannah-leclerc");
    expect(scenarios.g.persona).toBe("margaret-okonkwo");
    expect(scenarios.h.persona).toBe("celia-marsh");
    expect(scenarios.d.clock).toBe(CLOCK_AUG_24);
    expect(scenarios.a.clock).toBe(CLOCK_SEP_8);
    expect(scenarios.e.clock).toBe(CLOCK_SEP_14);
    expect(scenarios.g.clock).toBe(CLOCK_SEP_14_951);
    expect(scenarios.h.clock).toBe(CLOCK_MAY_11);
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

function stepLabels(): string[] {
  const steps = within(wizard()).getByRole("navigation", { name: "Steps" });
  return within(steps)
    .getAllByRole("listitem")
    .map((li) => li.textContent);
}

async function pickType(seen: Seen, label: string): Promise<void> {
  const card = (await within(wizard()).findByText(label)).closest("button");
  if (card === null) throw new Error(`no ${label} card`);
  const before = seen.calls.filter((c) => c.method === "PATCH").length;
  fireEvent.click(card);
  await waitFor(() => {
    expect(seen.calls.filter((c) => c.method === "PATCH").length).toBe(before + 1);
  });
}

describe("ENG-03 remaining types (P-07-T34)", () => {
  it("ENG-03e Ferris, Form 1040, step 5: Return setup, G2 not required, the §7216 consents card (fixture-only)", async () => {
    show("e", undefined, { consents: true });
    await within(await screen.findByRole("dialog")).findByText("Portal contacts");
    expect(stepLabels()[1]).toContain("Return setup");
    expect(within(wizard()).getByText("G2 Independence — not required (non-attest)")).toBeTruthy();
    expect(within(wizard()).getByText("§7216 consents")).toBeTruthy();
    expect(
      within(wizard()).getByText(
        "Use · AI disclosure (2 consents) · 1 of 2 signed (Morgan ✓ · Kai ○)",
      ),
    ).toBeTruthy();
    expect(
      within(wizard()).getByText(
        "Agents cannot read Ferris return information until both spouses sign.",
      ),
    ).toBeTruthy();
  });

  it("ENG-03e without the fixture slot (the route's case) draws no consents card: C19 is not live", async () => {
    show("e");
    await within(await screen.findByRole("dialog")).findByText("Portal contacts");
    expect(within(wizard()).queryByText("§7216 consents")).toBeNull();
  });

  it("ENG-03e Create answers possible_duplicate: the notice offers Open it and Create anyway; the gate blocks agents, not the engagement", async () => {
    const onCreated = vi.fn();
    const onOpen = vi.fn();
    const seen = show("e", onCreated, { onOpen, consents: true });
    await within(await screen.findByRole("dialog")).findByText("Portal contacts");
    fireEvent.click(next());
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    fireEvent.click(await within(wizard()).findByRole("button", { name: "Create" }));
    const notice = await within(wizard()).findByRole("status", {
      name: (_n, el) => el.hasAttribute("data-duplicate"),
    });
    expect(
      within(notice).getByText("TY2025 Form 1040 already exists for Morgan & Kai Ferris"),
    ).toBeTruthy();
    expect(onCreated).not.toHaveBeenCalled();
    fireEvent.click(within(notice).getByRole("button", { name: "Open it" }));
    expect(onOpen).toHaveBeenCalledWith(FERRIS_DUPLICATE);
    fireEvent.click(within(notice).getByRole("button", { name: "Create anyway" }));
    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledTimes(1);
    });
    const creates = seen.calls.filter((c) => c.path.endsWith("/create"));
    expect(creates.map((c) => c.body)).toEqual([{}, { confirm_duplicate: true }]);
  });

  it("ENG-03g Harlow & Pike: FS audit with Group audit (SAS 149) on, G2 all confirmed, Set up with AI planned", async () => {
    show("g");
    expect(
      await within(await screen.findByRole("dialog")).findByText("Harlow & Pike Holdings, Inc."),
    ).toBeTruthy();
    const fs = within(wizard()).getByText("FS audit").closest("button");
    expect(fs?.getAttribute("aria-pressed")).toBe("true");
    const toggle = within(wizard()).getByRole("switch", { name: "Group audit (SAS 149)" });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(
      within(wizard()).getByText(
        "Adds the Group band (structure, scoping, component auditors) to the cockpit. SAS 149 applies to periods ending on or after Dec 15, 2026.",
      ),
    ).toBeTruthy();
    expect(within(wizard()).getByText("G2 Team independence — all confirmed")).toBeTruthy();
    expect(within(wizard()).getByText("Start from last year's files")).toBeTruthy();
    const ai = within(wizard()).getByRole("button", { name: "Set up with AI…" });
    expect((ai as HTMLButtonElement).disabled).toBe(true);
    expect(ai.getAttribute("title")).toBe("Opens ENG-14 · Set up with AI");
    expect(
      within(wizard()).getByText(
        "FY2026 Group Financial Statement Audit · Harlow & Pike Holdings, Inc. (group)",
      ),
    ).toBeTruthy();
  });

  it("the Group audit toggle needs FS audit and the group_audit entitlement (a: Hannah has neither)", async () => {
    const seen = show("a");
    await within(await screen.findByRole("dialog")).findByText("Fairhaven Foods, Inc.");
    expect(within(wizard()).queryByText("Group audit (SAS 149)")).toBeNull();
    await pickType(seen, "FS audit");
    expect(within(wizard()).queryByText("Group audit (SAS 149)")).toBeNull();
  });

  it("ENG-03h Tessellate, SOC 2 on step 2: SSAE · AT-C 205, the period, no §103(a)(3)(C) scope", async () => {
    show("h");
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("SSAE · AT-C 205")).toBeTruthy();
    expect(within(dialog).getByText("Oct 1, 2025 – Sep 30, 2026 · Type 2")).toBeTruthy();
    expect(within(dialog).queryByRole("tablist", { name: "Audit scope" })).toBeNull();
    expect(within(dialog).getByText("Draft · saved 10:00 AM")).toBeTruthy();
  });

  it("P-07-T34 acceptance: a firm without the attest entitlement cannot select SOC cards; with it (h) SOC 2 is selected", async () => {
    show("a");
    await within(await screen.findByRole("dialog")).findByText("Fairhaven Foods, Inc.");
    for (const soc of ["SOC 1", "SOC 2"]) {
      const card = within(wizard()).getByText(soc).closest("[data-type]");
      expect(card?.getAttribute("data-availability")).toBe("coming-soon");
      expect(card?.tagName).not.toBe("BUTTON");
    }
    cleanup();
    restore?.();
    restore = undefined;
    const seen = show("h");
    await within(await screen.findByRole("dialog")).findByText("SSAE · AT-C 205");
    fireEvent.click(within(wizard()).getByRole("button", { name: "Back" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    const soc2 = (await within(wizard()).findByText("SOC 2")).closest("[data-type]");
    expect(soc2?.getAttribute("data-availability")).toBe("available");
    expect(soc2?.getAttribute("aria-pressed")).toBe("true");
  });

  it("the steps re-shape by type: Form 1040 reads Return setup, Monthly close the planned Close plan template, Advisory adds the planned proposal", async () => {
    const seen = show("a");
    await within(await screen.findByRole("dialog")).findByText("Fairhaven Foods, Inc.");
    expect(stepLabels()[1]).toContain("Standards & methodology");
    await pickType(seen, "Form 1040");
    await waitFor(() => {
      expect(stepLabels()[1]).toContain("Return setup");
    });
    await pickType(seen, "Monthly close");
    await waitFor(() => {
      expect(stepLabels()[1]).toContain("Close plan template");
    });
    await pickType(seen, "Advisory project");
    const proposal = await within(wizard()).findByRole("button", {
      name: "Start from proposal ⇕",
    });
    expect((proposal as HTMLButtonElement).disabled).toBe(true);
    expect(proposal.getAttribute("title")).toBe("Opens ENG-09");
  });
});
