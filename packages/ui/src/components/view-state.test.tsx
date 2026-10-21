import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StatesPane, type PaneKind, type PaneMode } from "../specimens/states";
import { STATE_GEOMETRY } from "./states";
import {
  FlagOffState,
  READ_ONLY_REASONS,
  RESTRICTED_COPY,
  RestrictedState,
  type ViewState,
  ViewStateBody,
  VIEW_STATE_KINDS,
  flagLabel,
} from "./view-state";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const CANARY = "Brightwater Hale trial balance 4,210,877";

function Frame({
  state,
  immediate = true,
}: {
  state: ViewState;
  immediate?: boolean;
}): JSX.Element {
  return (
    <section>
      <header data-testid="header" style={{ height: "var(--pane-hd-h)" }}>
        Sessions
      </header>
      <ViewStateBody
        state={state}
        immediate={immediate}
        noun="sessions"
        flagLabel="Insights"
        empty={{ title: "No sessions yet.", body: "Ask Workbench to prepare a report." }}
      >
        <p>{CANARY}</p>
      </ViewStateBody>
    </section>
  );
}

const ALL_STATES: ViewState[] = [
  { kind: "loading" },
  { kind: "empty" },
  { kind: "filtered-empty", query: "Schwab" },
  { kind: "ready" },
  { kind: "error", retry: () => undefined },
  { kind: "restricted", reason: "role" },
  { kind: "flag-off", flag: "ff.insights" },
];

describe("ViewStateBody", () => {
  it("covers every kind of the plan's ViewState", () => {
    expect(ALL_STATES.map((s) => s.kind)).toEqual([...VIEW_STATE_KINDS]);
  });

  it("renders every kind inside the same frame: the header node is never replaced", () => {
    const { rerender } = render(<Frame state={ALL_STATES[0] as ViewState} />);
    const header = screen.getByTestId("header");
    for (const state of ALL_STATES) {
      rerender(<Frame state={state} />);
      expect(screen.getByTestId("header")).toBe(header);
      expect(header.style.height).toBe("var(--pane-hd-h)");
      expect(document.querySelector(`[data-view-state='${state.kind}']`)).toBeTruthy();
    }
  });

  it("loading: a skeleton body with aria-busy and the header real", () => {
    render(<Frame state={{ kind: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading" }).getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Sessions")).toBeTruthy();
    expect(screen.queryByText(CANARY)).toBeNull();
  });

  it("empty: says what will appear and gives one action that calls back", () => {
    const run = vi.fn();
    render(<Frame state={{ kind: "empty", action: { label: "New session", onSelect: run } }} />);
    expect(screen.getByText("No sessions yet.")).toBeTruthy();
    expect(screen.getAllByRole("button")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    expect(run).toHaveBeenCalledOnce();
  });

  it("filtered-empty: No results for ‘…’ and Clear filters", () => {
    const clear = vi.fn();
    render(<Frame state={{ kind: "filtered-empty", query: "Schwab", clear }} />);
    expect(screen.getByText("No results for ‘Schwab’.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(clear).toHaveBeenCalledOnce();
  });

  it("error: Couldn’t load …, nothing was lost, Retry", () => {
    const retry = vi.fn();
    render(<Frame state={{ kind: "error", retry }} />);
    expect(screen.getByText("Couldn’t load sessions.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("ready: the children, and only then", () => {
    render(<Frame state={{ kind: "ready" }} />);
    expect(screen.getByText(CANARY)).toBeTruthy();
  });

  it("only ready shows the children", () => {
    for (const state of ALL_STATES.filter((s) => s.kind !== "ready")) {
      const { unmount } = render(<Frame state={state} />);
      expect(screen.queryByText(CANARY), state.kind).toBeNull();
      unmount();
    }
  });
});

describe("restricted shows no record data (INV-3, ADR-024)", () => {
  it("never calls the render function and never mounts the record", () => {
    const build = vi.fn(() => <p>{CANARY}</p>);
    for (const reason of READ_ONLY_REASONS) {
      const { container, unmount } = render(
        <ViewStateBody state={{ kind: "restricted", reason }} empty={{ title: "x" }}>
          {build}
        </ViewStateBody>,
      );
      expect(container.textContent).not.toContain("Brightwater");
      expect(container.textContent).toContain(RESTRICTED_COPY[reason].title);
      unmount();
    }
    expect(build).not.toHaveBeenCalled();
  });

  it("calls the render function for ready only", () => {
    const build = vi.fn(() => <p>{CANARY}</p>);
    render(
      <ViewStateBody state={{ kind: "ready" }} empty={{ title: "x" }}>
        {build}
      </ViewStateBody>,
    );
    expect(build).toHaveBeenCalledOnce();
    expect(screen.getByText(CANARY)).toBeTruthy();
  });

  it("says the reason in words for every reason, in a lock tile", () => {
    for (const reason of READ_ONLY_REASONS) {
      const { container, unmount } = render(<RestrictedState reason={reason} />);
      expect(container.textContent).toContain(RESTRICTED_COPY[reason].title);
      expect(container.textContent).toContain(RESTRICTED_COPY[reason].body);
      expect(container.querySelector("[data-icon='lock']")).toBeTruthy();
      unmount();
    }
  });

  it("does not name an ethical wall (DEC-43)", () => {
    for (const copy of Object.values(RESTRICTED_COPY)) {
      expect(`${copy.title} ${copy.body}`).not.toMatch(/wall/i);
    }
  });

  it("takes a screen's own words and one action", () => {
    const open = vi.fn();
    render(
      <RestrictedState
        reason="gate_g2"
        title="Simone Baptiste must confirm independence."
        action={
          <button type="button" onClick={open}>
            Open the confirmation
          </button>
        }
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open the confirmation" }));
    expect(open).toHaveBeenCalledOnce();
    expect(screen.getByText("Simone Baptiste must confirm independence.")).toBeTruthy();
  });
});

describe("flag-off is a designed state, never a 404", () => {
  it("is the T21e line, inside the frame the route has", () => {
    render(<Frame state={{ kind: "flag-off", flag: "ff.insights" }} />);
    expect(screen.getByText("Insights is not turned on for this firm.")).toBeTruthy();
    expect(screen.getByTestId("header")).toBeTruthy();
    expect(screen.queryByText(CANARY)).toBeNull();
  });

  it("is a tile and a line, with no 404 wording, no role=alert and no blank body", () => {
    const { container } = render(
      <FlagOffState flag="ff.attest" label="Attest" icon="shield-check" />,
    );
    expect(container.textContent).not.toMatch(/404|not found|no such page/i);
    expect(container.querySelector("[role='alert']")).toBeNull();
    expect(container.textContent.trim()).not.toBe("");
    expect(container.querySelector("[data-icon='shield-check']")).toBeTruthy();
    expect(container.querySelector("[data-flag-off='ff.attest']")).toBeTruthy();
  });

  it("reads a key in words when the screen gives no label", () => {
    expect(flagLabel("ff.insights")).toBe("Insights");
    expect(flagLabel("ff.internal_audit")).toBe("Internal audit");
    expect(flagLabel("statements_studio")).toBe("Statements studio");
  });
});

// Each ViewState kind in a pane with a real header and a real table head: the header and the
// head are the same node with the same height in every mode, and the rows keep their heights.
describe("header and row heights are unchanged in every mode (C-20)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  const KINDS: PaneKind[] = ["sessions", "issues", "requests", "files", "chat", "tasks"];
  const MODES: PaneMode[] = ["loaded", "loading", "empty", "error"];

  function heights(root: HTMLElement): { header: string; head: string | undefined } {
    const header = root.querySelector<HTMLElement>("[data-pane-header]");
    const head = root.querySelector<HTMLElement>("[data-row='table-head']");
    return { header: header?.style.height ?? "", head: head?.style.height };
  }

  it("keeps the 46px header in every kind and mode, and the 30px table head", () => {
    for (const kind of KINDS) {
      const { container, rerender } = render(
        <StatesPane kind={kind} mode="loaded" immediate still />,
      );
      const header = container.querySelector("[data-pane-header]");
      const first = heights(container);
      expect(first.header).toBe("var(--pane-hd-h)");
      for (const mode of MODES) {
        rerender(<StatesPane kind={kind} mode={mode} immediate still />);
        expect(container.querySelector("[data-pane-header]")).toBe(header);
        expect(heights(container)).toEqual(first);
        expect(container.querySelector("[data-pane]")?.getAttribute("style")).toContain(
          "height: 360px",
        );
      }
      cleanup();
    }
    const files = render(<StatesPane kind="files" mode="error" immediate still />);
    expect(heights(files.container).head).toBe(`${String(STATE_GEOMETRY.tableHead)}px`);
  });

  it("loaded rows and skeleton rows are the same height", () => {
    const rowHeights = (
      kind: PaneKind,
      mode: PaneMode,
      row: string,
      prop: "minHeight" | "height",
    ): Set<string> => {
      const { container, unmount } = render(
        <StatesPane kind={kind} mode={mode} immediate still />,
      );
      const out = new Set(
        [...container.querySelectorAll<HTMLElement>(`[data-row='${row}']`)].map(
          (r) => r.style[prop],
        ),
      );
      unmount();
      return out;
    };
    for (const [kind, row, prop, px] of [
      ["sessions", "list", "minHeight", 48],
      ["files", "table", "height", 40],
      ["tasks", "tasks", "minHeight", 50],
    ] as const) {
      const loaded = rowHeights(kind, "loaded", kind === "tasks" ? "tasks" : row, prop);
      const loading = rowHeights(kind, "loading", row, prop);
      if (kind === "tasks") {
        // Loaded task rows are AgentRunningRow <li>s: read them by tag.
        const { container, unmount } = render(
          <StatesPane kind="tasks" mode="loaded" freeze="settled" still />,
        );
        const lis = [...container.querySelectorAll<HTMLElement>("li")].map(
          (l) => l.style.minHeight,
        );
        unmount();
        expect(new Set(lis)).toEqual(new Set([`${String(px)}px`]));
      } else {
        expect(loaded).toEqual(new Set([`${String(px)}px`]));
      }
      expect(loading).toEqual(new Set([`${String(px)}px`]));
    }
  });

  it("the preview toggle moves through the modes, and Retry shows Loading, then Loaded", () => {
    render(<LiveHarness />);
    expect(document.querySelector("[data-mode='loaded']")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Error" }));
    expect(document.querySelector("[data-view-state='error']")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(document.querySelector("[data-mode='loading']")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(900);
    });
    expect(document.querySelector("[data-mode='loaded']")).toBeTruthy();
  });
});

function LiveHarness(): JSX.Element {
  const [mode, setMode] = useState<PaneMode>("loaded");
  return <StatesPane kind="sessions" mode={mode} onMode={setMode} immediate still />;
}
