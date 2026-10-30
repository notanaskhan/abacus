// KNW-03 · Program editor (K-01-T13). K-01 AC4.1–4.3 on scenarios a, b and e: step 4 lit on
// arrival from a citation, the rail's 67 · 21 with each program's counts, Rules and Skill reading
// a dash on every BH-EBP-110 row, the SHL-07 popover, the Change log computed from v2 and v3, and
// Open in Excel. Tier C parity runs in the end review's gallery sweep.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ProgramEditorPage, changesOf } from ".";
import { COPY } from "./copy";
import { type Knw03State, OPENS, scenarios } from "./scenarios";

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

function show(state: Knw03State): string[] {
  const paths: string[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        paths.push(request.path);
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const open = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ProgramEditorPage
        programId={open.programId}
        initialSegment={open.segment}
        {...(open.step === undefined ? {} : { step: open.step })}
        {...(open.from === undefined ? {} : { from: open.from })}
        popoverOpen={open.popover === true}
      />
    </QueryClientProvider>,
  );
  return paths;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-step]")];
}

describe("KNW-03 a: arrived from a citation", () => {
  it("step 4 is lit and no other", async () => {
    show("a");
    await waitFor(() => {
      expect(rows()).toHaveLength(16);
    });
    const lit = rows().filter((r) => r.hasAttribute("data-lit"));
    expect(lit.map((r) => r.getAttribute("data-step"))).toEqual(["4"]);
  });

  it("the rail reads EBP v3 · 67 steps · 21 mandatory and each program's counts", async () => {
    show("a");
    expect(await screen.findByText("67 steps · 21 mandatory")).toBeTruthy();
    expect(screen.getByText("EBP v3")).toBeTruthy();
    for (const sub of ["16 steps · 8 mandatory", "8 · 3", "6 · 2", "8 · 2", "10 · 3", "7 · 1", "12 · 2"]) {
      expect(screen.getAllByText(sub).length).toBeGreaterThan(0);
    }
  });

  it("every BH-EBP-110 row reads a dash in Rules and Skill; 8 locks; footer 16 · 8", async () => {
    show("a");
    await waitFor(() => {
      expect(rows()).toHaveLength(16);
    });
    for (const r of rows()) {
      const cells = r.querySelectorAll("td");
      expect(cells[6]?.textContent).toBe("—");
      expect(cells[7]?.textContent).toBe("—");
    }
    expect(screen.getAllByLabelText(COPY.mandatory)).toHaveLength(8);
    expect(screen.getAllByText("16 steps · 8 mandatory").length).toBeGreaterThan(0);
    expect(screen.getByText("Reserved to EP")).toBeTruthy();
  });

  it("step 15 carries New in v3; the record bar reads Published · effective Jan 1, 2026", async () => {
    show("a");
    expect(await screen.findByText(COPY.newIn("v3"))).toBeTruthy();
    expect(screen.getByText("Published · effective Jan 1, 2026")).toBeTruthy();
  });

  it("a row expands to its full text with the Skill and Scoping rules lines", async () => {
    show("a");
    await waitFor(() => {
      expect(rows()).toHaveLength(16);
    });
    fireEvent.click(rows()[8] as HTMLElement);
    const detail = document.querySelector<HTMLElement>('[data-step-detail="9"]');
    expect(detail).not.toBeNull();
    expect(within(detail as HTMLElement).getByText(/^Skill/u)).toBeTruthy();
    expect(within(detail as HTMLElement).getByText(/^Scoping rules/u)).toBeTruthy();
  });

  it("the Guidance dock shows Risk Assessment and where step 4 is cited", async () => {
    show("a");
    expect(await screen.findByRole("region", { name: "Risk Assessment" })).toBeTruthy();
    expect(await screen.findByText(COPY.whereCited(4))).toBeTruthy();
    expect(screen.getByText("1 citation")).toBeTruthy();
  });

  it("Open in Excel downloads the version's export", async () => {
    const paths = show("a");
    const button = await screen.findByRole("button", { name: COPY.actions.excel });
    await waitFor(() => {
      expect(button.hasAttribute("disabled")).toBe(false);
    });
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => undefined;
    fireEvent.click(button);
    await waitFor(() => {
      expect(paths.some((p) => p.endsWith("/export.xlsx"))).toBe(true);
    });
  });
});

describe("KNW-03 b: the SHL-07 popover on step 4", () => {
  it("names the program, quotes the step and counts 1 citation", async () => {
    show("b");
    expect(await screen.findByText("BH-EBP-110: General Planning Procedures")).toBeTruthy();
    expect(
      screen.getByText(/^4\. Determine whether the plan uses service organizations/u),
    ).toBeTruthy();
    expect(screen.getAllByText("1 citation").length).toBeGreaterThan(0);
  });
});

describe("KNW-03 e: Change log", () => {
  it("lists 7, 9 and 10 changed and 15 new against v2 (Change log 4)", async () => {
    show("e");
    const log = await screen.findByRole("list", { name: COPY.changeLog });
    await waitFor(() => {
      expect(log.querySelectorAll("li")).toHaveLength(4);
    });
    const entries = [...log.querySelectorAll<HTMLElement>("li")].map(
      (li) => `${li.getAttribute("data-change") ?? ""} ${li.textContent.trim().split(/\D/u)[0] ?? ""}`,
    );
    expect(entries).toEqual(["changed 7", "changed 9", "changed 10", "added 15"]);
    expect(screen.getAllByText("4 changes from v2").length).toBeGreaterThan(0);
  });
});

describe("changesOf", () => {
  it("is empty for identical versions and names removals", () => {
    expect(changesOf([], [])).toEqual([]);
  });
});
