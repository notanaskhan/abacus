// F-08-T07 (TASK-8746; DEC-5736): agent-column cells. An agent value stays ink-2 with an ink-3
// atom until a human onAdopt resolves, edits keep "Edited by HL · was …", citations come only
// from typed C4 views, a run shows spinners and "Agent column running", and DF-04 states put the
// reason on the header with no run intent.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Actor } from "../attribution/actor";
import type { CitationView } from "../tracing/types";
import { AgentFilledCell } from "./AgentFilledCell";
import { AGENT_UNAVAILABLE, SheetGrid } from "./SheetGrid";
import type { SheetGridColumn, SheetGridRow, SheetRunState } from "./types";

const HANNAH: Actor = { kind: "human", name: "Hannah Leclerc" };
const CITES: CitationView[] = [
  {
    n: 1,
    title: "Invoice FRF-30418",
    quote: "Services through Jun 29",
    loc: "Page 1",
    match: null,
  },
  { n: 2, title: "Check register", quote: "Check 4471", loc: "Register!C14", match: null },
];

afterEach(cleanup);

function hover(): HTMLElement {
  const value = document.querySelector<HTMLElement>("[data-filled]");
  if (value === null) throw new Error("no agent cell");
  fireEvent.mouseEnter(value.parentElement as HTMLElement);
  return value;
}

describe("AgentFilledCell (F-08-T07)", () => {
  it("a suggested value is ink-2 with the ink-3 atom and the C-31 tooltip", () => {
    render(
      <AgentFilledCell
        value="Properly excluded"
        state="suggested"
        citations={CITES}
        viewer={HANNAH}
        onAdopt={() => Promise.resolve()}
      />,
    );
    const value = hover();
    expect(value.className).toContain("text-ink-2");
    expect(screen.getByLabelText("Agent value").getAttribute("class")).toContain("text-ink-3");
    expect(screen.getByRole("tooltip").textContent).toContain(
      "Suggested by Accrued Agent · 2 citations · not yet adopted",
    );
    for (const name of ["Adopt", "Edit", "Open row"]) {
      expect(screen.getByRole("button", { name })).toBeTruthy();
    }
  });

  it("stays suggested while onAdopt is pending and turns adopted only once it resolves", async () => {
    let resolve: () => void = () => undefined;
    const onAdopt = vi.fn(
      () =>
        new Promise<void>((r) => {
          resolve = r;
        }),
    );
    render(
      <AgentFilledCell
        value="Properly excluded"
        state="suggested"
        viewer={HANNAH}
        onAdopt={onAdopt}
      />,
    );
    hover();
    fireEvent.click(screen.getByRole("button", { name: "Adopt" }));
    expect(onAdopt).toHaveBeenCalledTimes(1);
    expect(document.querySelector("[data-filled]")?.getAttribute("data-filled")).toBe("suggested");
    await act(async () => {
      resolve();
      await Promise.resolve();
    });
    const value = document.querySelector<HTMLElement>("[data-filled]");
    expect(value?.getAttribute("data-filled")).toBe("adopted");
    expect(value?.className).toContain("text-ink");
    expect(value?.className).not.toContain("text-ink-2");
    expect(screen.getByLabelText("Adopted agent value").getAttribute("class")).toContain(
      "text-green",
    );
  });

  it("a refused adopt leaves the value suggested", async () => {
    render(
      <AgentFilledCell
        value="Properly excluded"
        state="suggested"
        viewer={HANNAH}
        onAdopt={() => Promise.reject(new Error("refused"))}
      />,
    );
    hover();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Adopt" }));
      await Promise.resolve();
    });
    expect(document.querySelector("[data-filled]")?.getAttribute("data-filled")).toBe("suggested");
  });

  it("an edited value keeps Edited by HL · was <old>", () => {
    render(
      <AgentFilledCell
        value="Improperly excluded"
        state="edited"
        by={{ kind: "human", name: "HL" }}
        was="Properly included"
        viewer={HANNAH}
      />,
    );
    hover();
    expect(screen.getByRole("tooltip").textContent).toContain(
      "Edited by HL · was Properly included",
    );
  });

  it("numbers only typed citations: '[n]' in the value is never a marker (INV-2)", () => {
    render(
      <AgentFilledCell
        value="Per [1] and [2] [3]"
        state="suggested"
        citations={CITES.slice(0, 1)}
        viewer={HANNAH}
      />,
    );
    hover();
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toContain("1 citation · not yet adopted");
    expect(tip.querySelectorAll("[title]").length).toBe(1);
    expect(tip.querySelector("[title]")?.getAttribute("title")).toBe("Invoice FRF-30418 · Page 1");
  });

  it("the agent or the system never gets Adopt or another human verb (INV-1)", () => {
    for (const viewer of [{ kind: "agent" }, { kind: "system" }] as Actor[]) {
      const { unmount } = render(
        <AgentFilledCell value="Properly excluded" state="suggested" viewer={viewer} />,
      );
      hover();
      expect(
        screen.queryByRole("button", { name: /approve|sign off|release|send|adopt|accept|post/i }),
      ).toBeNull();
      unmount();
    }
  });
});

const COLUMNS: SheetGridColumn[] = [
  { key: "key", type: "text", label: "Key", width: 96, frozen: true },
  { key: "conclusion", type: "agent", label: "Conclusion", width: 180, agent: { name: "Tester" } },
];

function rows(): SheetGridRow[] {
  return [
    {
      key: "R-1",
      sectionKey: "a",
      locked: false,
      cells: {
        key: { value: "R-1", state: "human" },
        conclusion: { value: "Properly excluded", state: "suggested" },
      },
    },
    {
      key: "R-2",
      sectionKey: "a",
      locked: false,
      cells: { key: { value: "R-2", state: "human" } },
    },
    {
      key: "R-3",
      sectionKey: "a",
      locked: false,
      cells: { key: { value: "R-3", state: "human" } },
    },
  ];
}

describe("SheetGrid agent column (F-08-T07)", () => {
  it("a run shows spinners in its pending empty cells and the status bar says so", () => {
    let state: SheetRunState = { running: true, pendingRowKeys: new Set(["R-2"]) };
    const listeners = new Set<() => void>();
    const run = {
      subscribe: (l: () => void) => {
        listeners.add(l);
        return () => listeners.delete(l);
      },
      getSnapshot: () => state,
    };
    render(
      <SheetGrid
        label="Sheet"
        columns={COLUMNS}
        sections={[{ key: "a", title: "Disbursements", count: 3 }]}
        rows={rows()}
        status={{ rows: 3, exceptions: 0, view: "Default" }}
        viewer={HANNAH}
        run={run}
      />,
    );
    const cell = (key: string) =>
      document.querySelector<HTMLElement>(
        `[data-row-key="${key}"] [data-col-key="conclusion"]`,
      ) as HTMLElement;
    expect(cell("R-2").querySelector("[data-spinner]")).not.toBeNull();
    expect(cell("R-3").querySelector("[data-spinner]")).toBeNull();
    expect(screen.getByText("Agent column running")).toBeTruthy();
    act(() => {
      state = { running: false };
      for (const l of listeners) l();
    });
    expect(screen.queryByText("Agent column running")).toBeNull();
    expect(cell("R-2").querySelector("[data-spinner]")).toBeNull();
  });

  it("a DF-04 state puts its reason on the header and offers no run intent", () => {
    for (const reason of ["real_client_data", "consent_7216"] as const) {
      const { unmount } = render(
        <SheetGrid
          label="Sheet"
          columns={[
            COLUMNS[0] as SheetGridColumn,
            { ...(COLUMNS[1] as SheetGridColumn), agent: { name: "Tester", unavailable: reason } },
          ]}
          sections={[{ key: "a", title: "Disbursements", count: 3 }]}
          rows={rows()}
          status={{ rows: 3, exceptions: 0, view: "Default" }}
        />,
      );
      expect(screen.getByText(AGENT_UNAVAILABLE[reason])).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "Conclusion column menu" }));
      expect(screen.queryByRole("menuitem", { name: "Run on empty rows" })).toBeNull();
      expect(screen.queryByRole("menuitem", { name: "Edit agent column…" })).toBeNull();
      unmount();
    }
    expect(AGENT_UNAVAILABLE).toEqual({
      real_client_data: "AI isn't available for real client data yet",
      consent_7216: "Agents are off for this taxpayer — §7216 consent isn't on file",
    });
  });
});
