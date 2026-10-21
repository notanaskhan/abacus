import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { REDUCED_MOTION_QUERY } from "../motion";
import {
  AgentLive,
  AgentRunningRow,
  EmptyLink,
  EmptyState,
  ErrorRow,
  ErrorState,
  FieldsetEmpty,
  OfflineBanner,
  SKELETON_COUNT,
  STATE_COPY,
  STATE_GEOMETRY,
  Skeleton,
  SkeletonRows,
  WaitingBadge,
  runRowView,
  skeletonRows,
} from "./states";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function reduceMotion(on: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query === REDUCED_MOTION_QUERY && on,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    })),
  );
}

/** Every element that would start an animation or a transition. */
function moving(root: HTMLElement): Element[] {
  return [...root.querySelectorAll("*")].filter((el) => {
    const cls = el.getAttribute("class") ?? "";
    return (
      /\bmotion-|\banimate-|\btransition-/.test(cls) ||
      (el as HTMLElement).style.animationDelay !== ""
    );
  });
}

describe("EmptyState", () => {
  it("keeps the older callers working: title, children and action", () => {
    render(
      <EmptyState title="No engagements yet" action={<button type="button">Create</button>}>
        Create one to start requesting evidence.
      </EmptyState>,
    );
    expect(screen.getByText("No engagements yet")).toBeTruthy();
    expect(screen.getByText("Create one to start requesting evidence.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create" })).toBeTruthy();
  });

  it("draws a 34px tile, hidden from assistive technology, in the neutral tint", () => {
    const { container } = render(<EmptyState title="No sessions yet." icon="message-square" />);
    const tile = container.querySelector("[aria-hidden='true']");
    expect(tile?.className).toContain("size-[34px]");
    expect(tile?.className).toContain("bg-nested");
    expect(tile?.querySelector("[data-icon='message-square']")).toBeTruthy();
  });

  it("takes the brick tint for an error, never a red pane", () => {
    const { container } = render(
      <EmptyState tone="error" icon="circle-alert" title="Couldn’t load files." />,
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).not.toMatch(/bg-red/);
    expect(container.querySelector("[aria-hidden='true']")?.className).toContain("bg-red-tint");
  });

  it("allows one action or one link, and the types refuse both", () => {
    render(
      <EmptyState title="No results for ‘Schwab’." link={<EmptyLink>Clear filters</EmptyLink>} />,
    );
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeTruthy();
    // @ts-expect-error an action and a link together are a type error
    const both = <EmptyState title="x" action={<i />} link={<b />} />;
    expect(both).toBeTruthy();
  });
});

describe("ErrorState", () => {
  it("says what failed, that nothing was lost, and offers Retry", () => {
    const retry = vi.fn();
    render(<ErrorState noun="sessions" onRetry={retry} />);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Couldn’t load sessions.")).toBeTruthy();
    expect(screen.getByText(STATE_COPY.errorBody)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("never says Accrued in the portal", () => {
    const { container } = render(
      <ErrorState noun="documents" audience="portal" onRetry={() => undefined} />,
    );
    expect(container.textContent).not.toMatch(/Accrued/);
  });
});

describe("Skeleton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("is blank for 200ms, then drawn, and holds its place the whole time", () => {
    const { container } = render(<SkeletonRows type="list" />);
    const region = screen.getByRole("status", { name: "Loading" });
    expect(region.getAttribute("aria-busy")).toBe("true");
    expect(region.className).toContain("invisible");
    expect(container.querySelectorAll("[data-row='list']")).toHaveLength(6);
    act(() => {
      vi.advanceTimersByTime(199);
    });
    expect(region.className).toContain("invisible");
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(region.className).not.toContain("invisible");
  });

  it("can be drawn at once", () => {
    render(<SkeletonRows type="tasks" immediate />);
    expect(screen.getByRole("status").className).not.toContain("invisible");
  });

  it("draws the kit's counts: list 6, table 6, tasks 5, chat 1", () => {
    expect(SKELETON_COUNT).toMatchObject({ list: 6, table: 6, tasks: 5, chat: 1 });
    for (const type of ["list", "table", "tasks", "chat", "card"] as const) {
      const { container, unmount } = render(<SkeletonRows type={type} immediate />);
      expect(container.querySelectorAll(`[data-row='${type}']`)).toHaveLength(
        SKELETON_COUNT[type],
      );
      unmount();
    }
  });

  it("cycles title bars 62, 38, 74 and meta bars 38, 74, 62, each row 70ms behind", () => {
    expect(skeletonRows("list").map((r) => r.title)).toEqual([
      "62%",
      "38%",
      "74%",
      "62%",
      "38%",
      "74%",
    ]);
    expect(skeletonRows("list").map((r) => r.meta)).toEqual([
      "38%",
      "74%",
      "62%",
      "38%",
      "74%",
      "62%",
    ]);
    expect(skeletonRows("tasks").map((r) => r.delayMs)).toEqual([0, 70, 140, 210, 280]);
    const { container } = render(<SkeletonRows type="list" immediate />);
    const rows = [...container.querySelectorAll<HTMLElement>("[data-row='list']")];
    expect(rows.map((r) => r.style.animationDelay)).toEqual([
      "",
      "70ms",
      "140ms",
      "210ms",
      "280ms",
      "350ms",
    ]);
    const bars = rows[1]?.querySelectorAll<HTMLElement>("span[aria-hidden]") ?? [];
    expect([...bars].map((b) => b.style.width)).toEqual(["38%", "74%"]);
  });

  it("keeps the loaded row heights: 48 list, 40 table, 50 tasks", () => {
    expect(STATE_GEOMETRY).toMatchObject({
      header: 46,
      list: 48,
      tableHead: 30,
      tableRow: 40,
      task: 50,
    });
    const heights = (type: "list" | "table" | "tasks", prop: "minHeight" | "height"): string[] => {
      const { container, unmount } = render(<SkeletonRows type={type} immediate />);
      const out = [...container.querySelectorAll<HTMLElement>(`[data-row='${type}']`)].map(
        (r) => r.style[prop],
      );
      unmount();
      return out;
    };
    expect(new Set(heights("list", "minHeight"))).toEqual(new Set(["48px"]));
    expect(new Set(heights("table", "height"))).toEqual(new Set(["40px"]));
    expect(new Set(heights("tasks", "minHeight"))).toEqual(new Set(["50px"]));
  });

  it("never shimmers: no gradient in any skeleton class", () => {
    const { container } = render(<SkeletonRows type="table" immediate />);
    expect(container.innerHTML).not.toMatch(/gradient|shimmer/);
  });

  it("Skeleton, the bar the app already uses, waits and pulses", () => {
    render(<Skeleton className="h-16" />);
    const bar = document.querySelector("[data-pulse]") as HTMLElement;
    expect(bar.className).toContain("invisible");
    expect(bar.dataset["pulse"]).toBe("skeleton");
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(bar.className).not.toContain("invisible");
  });

  it("nothing pulses under reduced motion", () => {
    reduceMotion(true);
    const { container } = render(
      <div>
        <SkeletonRows type="list" immediate />
        <SkeletonRows type="chat" immediate />
        <Skeleton immediate />
      </div>,
    );
    expect(moving(container)).toEqual([]);
  });
});

describe("runRowView", () => {
  const row = {
    title: "Reconcile",
    meta: "0 open · No issues",
    errorTitle: "Bank feed unavailable",
  };
  it("crossfades from the idle disc to the end disc", () => {
    expect(runRowView("queued", row)).toMatchObject({
      disc: { idle: "todo", end: "todo", settled: false },
      meta: "Queued",
    });
    expect(runRowView("run", row)).toMatchObject({
      disc: { idle: "run", end: "todo", settled: false },
      meta: "Running…",
    });
    expect(runRowView("done", row)).toMatchObject({
      disc: { end: "done", settled: true },
      meta: "0 open · No issues",
    });
    expect(runRowView("wait", row)).toMatchObject({
      disc: { end: "wait", settled: true },
      waitingBadge: true,
    });
    expect(runRowView("fail", row)).toMatchObject({
      disc: { end: "fail", settled: true },
      title: "Bank feed unavailable",
      errorRow: true,
    });
  });
});

describe("AgentRunningRow", () => {
  it("is at least 50 high in every state", () => {
    for (const state of ["queued", "run", "done", "wait", "fail"] as const) {
      const { container, unmount } = render(
        <ul>
          <AgentRunningRow
            state={state}
            title="Step"
            meta="Result"
            errorTitle="Failed"
            waiting={{ label: "Waiting on the client" }}
          />
        </ul>,
      );
      expect((container.querySelector("li") as HTMLElement).style.minHeight).toBe("50px");
      unmount();
    }
  });

  it("shows Running… with a spinner that assistive technology does not announce", () => {
    const { container } = render(
      <ul>
        <AgentRunningRow state="run" title="Match bank transactions" />
      </ul>,
    );
    expect(screen.getByText("Running…", { selector: "p" })).toBeTruthy();
    const idle = container.querySelector("[data-layer='idle']") as HTMLElement;
    expect(idle.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("[data-spinner]")).toBeTruthy();
  });

  it("swaps layers on settling, with a 180ms fade and exactly one layer exposed", () => {
    const { container, rerender } = render(
      <ul>
        <AgentRunningRow state="run" title="A" meta="Done" />
      </ul>,
    );
    const end = container.querySelector("[data-layer='end']") as HTMLElement;
    expect(end.className).toContain("opacity-0");
    expect(end.className).toContain("duration-[180ms]");
    rerender(
      <ul>
        <AgentRunningRow state="done" title="A" meta="Done" />
      </ul>,
    );
    expect(end.className).not.toContain("opacity-0");
    expect(end.getAttribute("aria-hidden")).toBeNull();
    expect(screen.getByRole("img", { name: "Done" })).toBeTruthy();
    expect(screen.getByText("Done", { selector: "p" })).toBeTruthy();
  });

  it("a waiting row links to the decision and the badge draws no button of its own", () => {
    render(
      <ul>
        <AgentRunningRow
          state="wait"
          title="Post proposed adjustments"
          waiting={{ label: "Blocked on a partner decision", href: "/decisions/1" }}
        />
      </ul>,
    );
    const link = screen.getByRole("link", { name: "Blocked on a partner decision" });
    expect(link.getAttribute("href")).toBe("/decisions/1");
    expect(link.className).toContain("text-amber-ink");
  });

  it("a failed row is the error row: brick title, cause in ink-2, Retry for this step and View run", () => {
    const retry = vi.fn();
    const view = vi.fn();
    render(
      <ul>
        <AgentRunningRow
          state="fail"
          title="Reconcile Amex"
          errorTitle="Bank feed unavailable"
          meta="Front Range Bank connection expired on Sep 12."
          onRetry={retry}
          onViewRun={view}
        />
      </ul>,
    );
    const title = screen.getByText("Bank feed unavailable");
    expect(title.className).toContain("text-red-ink");
    expect(screen.getByRole("alert").textContent).toContain("Front Range Bank");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    fireEvent.click(screen.getByRole("button", { name: "View run" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(view).toHaveBeenCalledOnce();
  });

  it("names whose work it is as ‹person› via Agent, never a persona", () => {
    render(
      <ul>
        <AgentRunningRow state="run" title="Match bank transactions" actor="Hannah Leclerc" />
      </ul>,
    );
    expect(screen.getByText("Running… · Hannah Leclerc via Agent")).toBeTruthy();
  });

  it("nothing fades or turns under reduced motion", () => {
    reduceMotion(true);
    const { container } = render(
      <ul>
        <AgentRunningRow state="run" title="A" />
        <AgentRunningRow state="done" title="B" meta="x" />
      </ul>,
    );
    expect(moving(container)).toEqual([]);
    expect(container.querySelector("[data-spinner='still']")).toBeTruthy();
  });
});

describe("ErrorRow and WaitingBadge", () => {
  it("ErrorRow is an alert, 50 high, with the cause under the title", () => {
    render(
      <ErrorRow title="Bank feed unavailable">
        Front Range Bank connection expired on Sep 12.
      </ErrorRow>,
    );
    const row = screen.getByRole("alert");
    expect(row.style.minHeight).toBe("50px");
    expect(
      within(row).getByText("Front Range Bank connection expired on Sep 12.").className,
    ).toContain("text-ink-2");
    expect(within(row).queryByRole("button")).toBeNull();
  });

  it("WaitingBadge is a plain label until it has a decision to point at", () => {
    const { rerender } = render(<WaitingBadge>Waiting on the client</WaitingBadge>);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    const open = vi.fn();
    rerender(<WaitingBadge onOpen={open}>Waiting on the client</WaitingBadge>);
    fireEvent.click(screen.getByRole("button"));
    expect(open).toHaveBeenCalledOnce();
  });
});

describe("AgentLive", () => {
  it("draws the breathing dot only while running and says so in words", () => {
    const { container, rerender } = render(<AgentLive running={false} />);
    expect(container.firstChild).toBeNull();
    rerender(<AgentLive running />);
    expect(screen.getByRole("status").textContent).toBe("Accrued Agent is running");
    expect(container.querySelector("[data-pulse='breathe']")).toBeTruthy();
  });

  it("is still under reduced motion", () => {
    reduceMotion(true);
    const { container } = render(<AgentLive running />);
    expect(container.querySelector("[data-pulse='still']")).toBeTruthy();
    expect(moving(container)).toEqual([]);
  });
});

describe("OfflineBanner and FieldsetEmpty", () => {
  it("keeps a status region always, and draws the 32px banner only while offline", () => {
    const { rerender } = render(<OfflineBanner offline={false} />);
    const region = screen.getByRole("status");
    expect(region.textContent).toBe("");
    rerender(<OfflineBanner offline />);
    expect(region.textContent).toBe("You’re offline. Changes will sync when you reconnect.");
    expect((region.firstElementChild as HTMLElement).style.height).toBe("32px");
    expect(region.firstElementChild?.className).toContain("bg-amber-tint");
  });

  it("follows the browser's network status", () => {
    const online = vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(true);
    render(<OfflineBanner />);
    expect(screen.getByRole("status").textContent).toBe("");
    online.mockReturnValue(false);
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByRole("status").textContent).toContain("You’re offline");
    online.mockRestore();
  });

  it("FieldsetEmpty is one line of ink-3", () => {
    render(<FieldsetEmpty>No inputs. This agent runs without a form.</FieldsetEmpty>);
    expect(screen.getByText("No inputs. This agent runs without a form.").className).toContain(
      "text-ink-3",
    );
  });
});

describe("the words", () => {
  it("have no exclamation mark, no three dots, no emoji, and the Agent is Accrued Agent", () => {
    for (const text of Object.values(STATE_COPY)) {
      expect(text).not.toMatch(/!|\.\.\./u);
      expect(text).not.toMatch(/\p{Extended_Pictographic}/u);
    }
    expect(STATE_COPY.agentRunning).toBe("Accrued Agent is running");
    expect(STATE_COPY.errorBodyPortal).not.toMatch(/Accrued/);
  });
});
