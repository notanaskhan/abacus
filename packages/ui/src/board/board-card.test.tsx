// F-08-T21 (TASK-8927; F-08 §B3; DEC-5929): "Cards show owner chip <= 20, metrics, AgentProgress
// and P/R slots, the four overlays differ without colour fills, and the navigator collapses to a
// 44 rail." Plus the header's count and the lane's DoneCount.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AgentProgress, BoardCard, BoardColumnHeader, BoardLane, BoardNavigator } from ".";

afterEach(cleanup);

const BASE = {
  title: "Search for unrecorded liabilities",
  code: "BH-FS-430",
  owner: "CH",
  ownerName: "Cole Hart",
  metrics: [3, 4, 1, 2] as const,
  agent: { state: "progress" as const, pct: 40 },
  p: { level: "L1", role: "Preparer", signer: "Cole Hart", at: "Sep 24, 9:30 AM" },
  r: { level: "L2", role: "Reviewer", signer: null, at: null },
};

function card(): HTMLElement {
  const found = document.querySelector<HTMLElement>("[data-card]");
  if (found === null) throw new Error("no card");
  return found;
}

describe("BoardCard C-24", () => {
  it("shows the owner chip at 20 px, the four metrics, AgentProgress and the P/R slots", () => {
    render(<BoardCard {...BASE} />);
    const owner = document.querySelector<HTMLElement>("[data-owner]");
    expect(owner?.className).toContain("size-[20px]");
    expect(owner?.getAttribute("title")).toBe("Cole Hart");
    const metrics = document.querySelector("[data-metrics]");
    expect(
      [...(metrics?.querySelectorAll("span[title]") ?? [])].map((m) => m.textContent),
    ).toEqual(["3", "4", "1", "2"]);
    expect(document.querySelector('[data-agent-progress="40"]')).not.toBeNull();
    expect(screen.getByText("40%")).toBeTruthy();
    const slots = [...document.querySelectorAll("[data-slots] [data-slot]")].map((s) =>
      s.getAttribute("data-slot"),
    );
    expect(slots).toEqual(["signed", "empty"]);
    expect(screen.getByText(BASE.code)).toBeTruthy();
  });

  it("the four overlays differ, and none fills the card with colour", () => {
    const seen: string[] = [];
    for (const over of [
      { flag: "input" as const },
      { flag: "client" as const },
      { spin: true },
      { sentBy: "Hannah Leclerc" },
    ]) {
      const { unmount } = render(<BoardCard {...BASE} {...over} />);
      const el = card();
      expect(el.className).toContain("bg-card");
      expect(el.className).not.toMatch(/bg-(amber|red|green|nested)/);
      seen.push(
        [
          el.querySelector(".bg-amber") ? "dot" : "",
          screen.queryByText("Waiting on client") ? "pill" : "",
          el.querySelector("[data-spin]") ? "spin" : "",
          el.querySelector('[data-bar="sent-back"]') ? "bar" : "",
        ].join(""),
      );
      unmount();
    }
    expect(seen).toEqual(["dot", "pill", "spin", "bar"]);
    render(<BoardCard {...BASE} sentBy="Hannah Leclerc" />);
    expect(screen.getByText("Sent back · Hannah Leclerc")).toBeTruthy();
  });

  it("a stale preparer sign-off reads as the stale slot", () => {
    render(<BoardCard {...BASE} p={{ ...BASE.p, stale: true }} />);
    expect(document.querySelector('[data-slot="stale"]')?.textContent).toBe("!");
  });

  it("control, return and close variants carry their own lines", () => {
    const { unmount } = render(
      <BoardCard {...BASE} variant="control" code="CC6.1" tag="CC6.1" result="exc" />,
    );
    expect(screen.getByText("Exceptions noted")).toBeTruthy();
    unmount();
    const r = render(
      <BoardCard {...BASE} variant="return" sub="Form 1120-S" pill="Ready" due="Due Mar 16" />,
    );
    expect(screen.getByText("Due Mar 16")).toBeTruthy();
    r.unmount();
    render(<BoardCard {...BASE} variant="close" done={{ text: "5 of 5", complete: true }} />);
    expect(screen.getByText("to-dos done")).toBeTruthy();
  });

  it("the card holds no sign-off, approve, release, send or post control (INV-1)", () => {
    render(<BoardCard {...BASE} />);
    for (const word of ["Sign off", "Approve", "Release", "Send", "Post"]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
  });
});

describe("C-26 AgentProgress", () => {
  it("renders nothing for none and a chip for each state", () => {
    const { container, unmount } = render(<AgentProgress state="none" />);
    expect(container.innerHTML).toBe("");
    unmount();
    for (const [state, word] of [
      ["running", "Running"],
      ["input", "Needs input"],
      ["client", "Waiting on client"],
      ["done", "Done"],
    ] as const) {
      const r = render(<AgentProgress state={state} />);
      expect(screen.getAllByText(word).length).toBeGreaterThan(0);
      r.unmount();
    }
  });
});

describe("Header, Lane and Navigator", () => {
  it("the header shows its count", () => {
    render(<BoardColumnHeader label="In progress" count={5} disc="half" />);
    expect(document.querySelector("[data-count]")?.textContent).toBe("5");
  });

  it("the lane shows its DoneCount and collapses", () => {
    let collapsed = false;
    const { rerender } = render(
      <BoardLane
        title="Planning"
        meta="8 programs"
        done="8 of 8"
        collapsed={collapsed}
        onToggle={(c) => (collapsed = c)}
      >
        <p>child</p>
      </BoardLane>,
    );
    expect(document.querySelector("[data-lane-done]")?.textContent).toBe("8 of 8");
    fireEvent.click(screen.getByRole("button", { expanded: true }));
    expect(collapsed).toBe(true);
    rerender(
      <BoardLane title="Planning" collapsed>
        <p>child</p>
      </BoardLane>,
    );
    expect(screen.queryByText("child")).toBeNull();
  });

  it("the 280 navigator collapses to a 44 rail", () => {
    let collapsed = false;
    const items = [
      { key: "planning", label: "Planning", count: 8 },
      { key: "area-a", label: "Area A · Revenue", count: 4, depth: 1 as const },
    ];
    const { rerender } = render(
      <BoardNavigator
        title="Programs"
        items={items}
        collapsed={collapsed}
        onToggle={(c) => (collapsed = c)}
      />,
    );
    expect(document.querySelector('[data-navigator="open"]')?.className).toContain("w-[280px]");
    fireEvent.click(screen.getByRole("button", { name: "Collapse Programs" }));
    expect(collapsed).toBe(true);
    rerender(<BoardNavigator title="Programs" items={items} collapsed />);
    expect(document.querySelector('[data-navigator="rail"]')?.className).toContain("w-[44px]");
  });
});
