// K-03-T16 (TASK-8932; DEC-5934): "SHT-01b, c, a and f render in fixture mode at their clocks with no
// column letters, row numbers or zebra rows, locked cells refuse edits with the final tooltip, and
// Sign-offs opens ?ov=signoff for the selected rows."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { SHT01 } from "./index";
import { SHEET_ID, scenarios } from "./scenarios";

const opened = vi.hoisted(() => [] as { key: string; args: readonly string[] }[]);
vi.mock("../../app-core/open", () => ({
  useOpenOverlay: () => (ref: { key: string; args: readonly string[] }) => {
    opened.push(ref);
  },
}));

const AUDIT = "00000000-0000-4000-8000-0000000000a2";
const LOCKED = "Signed-off rows are locked. Sign-offs are removed only from the sign-off modal.";
let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(state: "a" | "b" | "c" | "f"): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <SHT01 auditId={AUDIT} sheetId={SHEET_ID} /> }]);
}

async function grid(): Promise<HTMLElement> {
  return screen.findByRole("grid");
}

describe("SHT-01 BH-FS-430 sheet", () => {
  it("b: empty from template", async () => {
    show("b");
    expect(await screen.findByText("No rows yet.")).toBeTruthy();
  });

  it("c and a: the strata bands with their totals; no agent column in this row", async () => {
    for (const st of ["c", "a"] as const) {
      show(st);
      const g = await grid();
      await waitFor(() => {
        expect(g.querySelectorAll("[data-row-key]").length).toBeGreaterThan(0);
      });
      expect(g.textContent).toContain("3,286,400.00");
      expect(g.textContent).toContain("412,300.00");
      expect(screen.queryByRole("columnheader", { name: /Conclusion/ })).toBeNull();
      cleanup();
      restore?.();
      restore = null;
    }
  });

  it("no column letters, row numbers or zebra rows", async () => {
    show("a");
    const g = await grid();
    await waitFor(() => {
      expect(g.querySelectorAll("[data-row-key]").length).toBeGreaterThan(0);
    });
    const headers = [...g.querySelectorAll('[role="columnheader"]')].map((h) =>
      (h.textContent || "").trim(),
    );
    expect(headers.some((h) => /^[A-Z]$/.test(h))).toBe(false);
    expect(g.querySelector('[role="rowheader"]')).toBeNull();
    const rows = [...g.querySelectorAll<HTMLElement>("[data-row-key]")];
    expect(rows.some((r) => /odd:|even:|bg-band/.test(r.className))).toBe(false);
  });

  it("f: locked cells refuse edits with the final tooltip", async () => {
    show("f");
    const g = await grid();
    await waitFor(() => {
      expect(g.querySelectorAll("[data-locked]").length).toBeGreaterThan(0);
    });
    const locked = g.querySelector<HTMLElement>("[data-locked] [aria-readonly='true']");
    expect(locked?.getAttribute("title")).toBe(LOCKED);
    locked?.focus();
    fireEvent.keyDown(locked as HTMLElement, { key: "Enter" });
    expect(screen.queryByRole("textbox", { name: /edit/i })).toBeNull();
  });

  it("Sign-offs opens ?ov=signoff for the selected rows", async () => {
    show("a");
    await grid();
    const box = await screen.findByRole("checkbox", { name: "Select SURL-05" });
    fireEvent.click(box);
    fireEvent.click(screen.getByRole("button", { name: /^Sign-offs/ }));
    await waitFor(() => {
      expect(opened.at(-1)).toEqual({ key: "signoff", args: ["sheet_row", "SURL-05"] });
    });
  });
});
