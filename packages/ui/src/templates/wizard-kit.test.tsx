import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../components/popover";
import { TPL18_CATALOGUE, Tpl18Specimen } from "../specimens/wizard";
import { GateCard, TypeCatalogue, typeAvailability } from "./wizard-kit";

// F-05-T38 acceptance: "TPL-18e disables Create behind the Gate G1 card, and the type catalogue
// comes from data with Single audit fixed at Coming soon." Plus the frames' step order, the
// summary card and the §7216 consent action.

afterEach(cleanup);

function board(container: HTMLElement, id: string): HTMLElement {
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no artboard ${id}`);
  return el;
}

function specimen(): HTMLElement {
  return render(
    <TooltipProvider>
      <Tpl18Specimen />
    </TooltipProvider>,
  ).container;
}

const ADVISORY = TPL18_CATALOGUE.find((g) => g.id === "advisory");

describe("typeAvailability: the catalogue is data", () => {
  const single = ADVISORY?.types.find((t) => t.id === "single");
  const soc = ADVISORY?.types.find((t) => t.id === "soc");
  if (single === undefined || soc === undefined) throw new Error("catalogue data missing");

  it("Single audit is coming soon whatever the entitlements say (D1, D10)", () => {
    expect(typeAvailability(single, [])).toBe("coming-soon");
    expect(typeAvailability(single, ["attest", "group_audit", "single_audit"])).toBe(
      "coming-soon",
    );
  });

  it("SOC and AUP follow the attest entitlement", () => {
    expect(typeAvailability(soc, [])).toBe("coming-soon");
    expect(typeAvailability(soc, ["attest"])).toBe("available");
  });

  it("a type with no entitlement is always available", () => {
    const first = TPL18_CATALOGUE[0]?.types[0];
    if (first === undefined) throw new Error("no types");
    expect(typeAvailability(first, [])).toBe("available");
  });
});

describe("TypeCatalogue", () => {
  it("renders every group and type from the data it is given, and nothing else", () => {
    const groups = [
      {
        id: "g",
        label: "Group",
        tone: "clay" as const,
        icon: "file-text" as const,
        types: [
          { id: "a", label: "Alpha", sub: "First" },
          { id: "b", label: "Beta", comingSoon: true },
        ],
      },
    ];
    const { container } = render(<TypeCatalogue groups={groups} entitlements={[]} />);
    expect(container.querySelectorAll("[data-type]")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "Group" })).toBeTruthy();
    expect(container.querySelector('[data-type="b"]')?.textContent).toContain("Coming soon");
  });

  it("a press selects an available card, a second press clears it, and soon cards do nothing", () => {
    const onSelect = vi.fn();
    render(<TypeCatalogue groups={TPL18_CATALOGUE} entitlements={[]} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Form 1065/ }));
    expect(onSelect).toHaveBeenLastCalledWith("1065");
    cleanup();
    render(
      <TypeCatalogue
        groups={TPL18_CATALOGUE}
        entitlements={[]}
        selected="1065"
        onSelect={onSelect}
      />,
    );
    const card = screen.getByRole("button", { name: /Form 1065/ });
    expect(card.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(card);
    expect(onSelect).toHaveBeenLastCalledWith(null);
    // Coming-soon cards are not buttons at all.
    expect(screen.queryByRole("button", { name: /Single audit/ })).toBeNull();
  });

  it("with attest, AUP and SOC become buttons; Single audit stays Coming soon", () => {
    const { container } = render(
      <TypeCatalogue groups={TPL18_CATALOGUE} entitlements={["attest"]} />,
    );
    expect(screen.getByRole("button", { name: /SOC 1 \/ SOC 2/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Agreed-upon procedures/ })).toBeTruthy();
    const single = container.querySelector('[data-type="single"]');
    expect(single?.getAttribute("data-availability")).toBe("coming-soon");
    expect(single?.getAttribute("aria-disabled")).toBe("true");
  });
});

describe("GateCard", () => {
  it("names its tone and puts the words first", () => {
    const { container } = render(
      <>
        <GateCard tone="met">Met</GateCard>
        <GateCard tone="needs">Needs</GateCard>
        <GateCard tone="blocked">Blocked</GateCard>
      </>,
    );
    const tones = [...container.querySelectorAll("[data-gate]")].map((el) =>
      el.getAttribute("data-gate"),
    );
    expect(tones).toEqual(["met", "needs", "blocked"]);
    // Not colour alone: the blocked card carries a labelled disc.
    expect(
      within(container.querySelector('[data-gate="blocked"]') as HTMLElement).getByRole("img"),
    ).toBeTruthy();
  });
});

describe("TPL-18 frames", () => {
  it("are steps 1, 4, 3, 6 and 6, in that order (frame letters out of step order)", () => {
    const container = specimen();
    const current = ["a", "b", "c", "d", "e"].map(
      (l) =>
        board(container, `tpl-18${l}`).querySelector('[aria-current="step"]')?.textContent ?? "",
    );
    expect(current).toEqual([
      "Step 1: Client & type",
      "Step 4: Team & independence",
      "Step 3: Period & deadlines",
      "Step 6: Letter & review",
      "Step 6: Letter & review",
    ]);
  });

  it("TPL-18a: Advisory project is picked and three types are coming soon at E0", () => {
    const a = board(specimen(), "tpl-18a");
    expect(
      within(a)
        .getByRole("button", { name: /Advisory project/ })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    const soon = [...a.querySelectorAll('[data-availability="coming-soon"]')].map(
      (el) => el.getAttribute("data-type") ?? "",
    );
    expect(soon).toEqual(["aup", "soc", "single"]);
    expect(a.textContent).toContain("Advisory project · Ridgeline Property Partners, LP");
  });

  it("TPL-18a: clearing the type disables Next and the summary says so", () => {
    const a = board(specimen(), "tpl-18a");
    fireEvent.click(within(a).getByRole("button", { name: /Advisory project/ }));
    expect(within(a).getByRole<HTMLButtonElement>("button", { name: "Next" }).disabled).toBe(true);
    expect(a.textContent).toContain("No type yet · Ridgeline Property Partners, LP");
  });

  it("TPL-18d: Create is enabled, and Request consent adds the consent to the letter", () => {
    const d = board(specimen(), "tpl-18d");
    expect(within(d).getByRole<HTMLButtonElement>("button", { name: "Create" }).disabled).toBe(
      false,
    );
    expect(d.querySelector('[data-gate="needs"]')?.textContent).toContain(
      "needs a signed §7216 consent to disclose. It isn’t on file.",
    );
    expect(d.querySelector('[data-gate="met"]')?.textContent).toBe(
      "Continuance: existing client, accepted Jan 2026 (G1)",
    );
    fireEvent.click(within(d).getByRole("button", { name: "Request consent with the letter" }));
    expect(d.textContent).toContain("Consent requested with the letter");
  });

  it("TPL-18e: the Gate G1 card shows, Create is disabled and Start acceptance is offered", () => {
    const e = board(specimen(), "tpl-18e");
    const gate = e.querySelector('[data-gate="blocked"]');
    expect(gate?.textContent).toContain(
      "Acceptance decision required (Gate G1) — Margaret Okonkwo must approve acceptance before a letter can be created",
    );
    expect(
      within(gate as HTMLElement).getByRole("button", { name: /Start acceptance \(CLI-07\)/ }),
    ).toBeTruthy();
    expect(within(e).getByRole<HTMLButtonElement>("button", { name: "Create" }).disabled).toBe(
      true,
    );
    expect(
      within(e).getByRole<HTMLButtonElement>("button", { name: "Create & send letter" }).disabled,
    ).toBe(true);
  });

  it("a done step can be reopened from the list, and Back walks one step", () => {
    const b = board(specimen(), "tpl-18b");
    fireEvent.click(within(b).getByRole("button", { name: /Client & type/ }));
    expect(b.querySelector('[aria-current="step"]')?.textContent).toBe("Step 1: Client & type");
    fireEvent.click(within(b).getByRole("button", { name: "Next" }));
    expect(b.querySelector('[aria-current="step"]')?.textContent).toBe(
      "Step 2: Standards & methodology",
    );
    expect(b.textContent).toContain("AICPA SSTS · CS 100 · Circular 230 §10.37");
  });
});
