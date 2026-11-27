// T-06-T52 (TASK-9031; DEC-6036): TXP-13 a, b, b2, c, c2 and c3 from their scenarios, whose lines
// are the exported Python scenario's. Row acceptance: "No partnership vocabulary appears on 1120
// or 990 frames, and the 990 title reads '2025 Form 990 (FYE Jun 30, 2026)'."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { FRAMES as F } from "./copy";
import { TXP13 } from "./index";
import { FRAME_RETURN, scenarios } from "./scenarios";

const opened = vi.hoisted(() => [] as { key: string; args: readonly string[] }[]);
vi.mock("../../app-core/open", () => ({
  useOpenOverlay: () => (ref: { key: string; args: readonly string[] }) => {
    opened.push(ref);
  },
  useOpenHref: () => () => undefined,
}));

let restore: (() => void) | null = null;
type Frame = keyof typeof FRAME_RETURN;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
  opened.length = 0;
});

function show(frame: Frame): void {
  restore = installFixtureMode(scenarios[frame]);
  renderRoutes([{ path: "/", component: () => <TXP13 returnId={FRAME_RETURN[frame]} /> }]);
}

async function table(name: string): Promise<HTMLElement> {
  return screen.findByRole("table", { name });
}

function rowOf(t: HTMLElement, first: string): HTMLElement {
  const found = within(t)
    .getAllByRole("row")
    .find((r) => r.textContent.includes(first));
  if (found === undefined) throw new Error(`no row ${first}`);
  return found;
}

describe("TXP-13 frames a–c3", () => {
  it("TXP-13a 1120-S: Schedule M-2 rolls 1,240,000 to 1,488,200, read-only once Accepted", async () => {
    show("a");
    const m2 = await table(F.a.m2);
    expect(rowOf(m2, "Balance at beginning of tax year").textContent).toContain("1,240,000");
    expect(rowOf(m2, "Other reductions").textContent).toContain("(4,200)");
    expect(rowOf(m2, "Balance at end of tax year").textContent).toContain("1,488,200");
    expect(screen.getByText("2025 Form 1120-S")).toBeTruthy();
    expect(screen.getByRole("img", { name: F.locked })).toBeTruthy();
    const allocation = await table(F.a.allocation);
    expect(rowOf(allocation, "Arjun Mehta").textContent).toContain("602,000");
    expect(rowOf(allocation, "Sunita Rao").textContent).toContain("186,000");
  });

  it("TXP-13b 1120: the provision 2,257,200 at 28.9% and the reconciliation ties", async () => {
    show("b");
    const current = await table(F.b.current);
    expect(rowOf(current, "Taxable income").textContent).toContain("7,490,000");
    expect(rowOf(current, "Bonus depreciation").textContent).toContain("(640,000)");
    expect(rowOf(current, "Total provision").textContent).toContain("2,257,200");
    const recon = await table(F.b.views[1]);
    expect(rowOf(recon, "Statutory federal").textContent).toContain("21.0%");
    expect(rowOf(recon, "Total").textContent).toContain("28.9%");
    expect(document.querySelector('[data-txp13="unclassified"]')).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: F.b.views[2] }));
    const deferred = await table(F.b.views[2]);
    expect(rowOf(deferred, "Net deferred").textContent).toContain("122,550");
  });

  it("TXP-13b2 exception: the unclassified 1,200 row and Explain… opens SHL-15", async () => {
    show("b2");
    const row = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-txp13="unclassified"]');
      if (found === null) throw new Error("no row");
      return found;
    });
    expect(row.textContent).toContain("Unclassified difference 1,200");
    fireEvent.click(within(row).getByRole("button", { name: F.b.explain }));
    await waitFor(() => {
      expect(opened.some((o) => o.key === "issue")).toBe(true);
    });
  });

  it("TXP-13 acceptance: the 990 title reads '2025 Form 990 (FYE Jun 30, 2026)'", async () => {
    show("c");
    await table(F.c.center);
    const title = document.querySelector('[data-txp13="title"]')?.textContent ?? "";
    const fye = document.querySelector('[data-txp13="fye"]')?.textContent ?? "";
    expect(`${title} ${fye}`).toBe("2025 Form 990 (FYE Jun 30, 2026)");
  });

  it("TXP-13c 990: Part IX foots to 4,014,000 with each column's total", async () => {
    show("c");
    const t = await table(F.c.center);
    expect(rowOf(t, "Total functional expenses").textContent).toContain("4,014,000");
    expect(rowOf(t, "Total functional expenses").textContent).toContain("3,210,000");
    expect(rowOf(t, "Books and learning materials").textContent).toContain("412,000");
  });

  it("TXP-13c2 allocation basis: the time-study lines show their percentages", async () => {
    show("c2");
    await table(F.c.center);
    fireEvent.click(screen.getByRole("tab", { name: F.c.views[1] }));
    const t = await table(F.c.views[1]);
    const officers = rowOf(t, "Compensation of current officers");
    expect(officers.textContent).toContain("Time study");
    expect(officers.textContent).toContain("50.0%");
    expect(rowOf(t, "Occupancy").textContent).toContain("Direct");
  });

  it("TXP-13c3 building: skeleton rows while the time-study allocation runs", async () => {
    show("c3");
    expect(await screen.findAllByText(F.c.building)).toBeTruthy();
  });

  it("TXP-13 acceptance: no partnership vocabulary on the 1120 or 990 frames", async () => {
    for (const frame of ["a", "b", "b2", "c", "c2"] as const) {
      show(frame);
      await screen.findAllByRole("table");
      const text = document.body.textContent.toLowerCase();
      for (const word of ["capital account", "partner", "k-1"]) {
        expect(text.includes(word), `${frame}: ${word}`).toBe(false);
      }
      cleanup();
      restore?.();
      restore = null;
    }
  });
});
