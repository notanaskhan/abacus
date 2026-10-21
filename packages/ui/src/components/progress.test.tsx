import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { REDUCED_MOTION_QUERY } from "../motion";
import {
  KpiGrid,
  KpiTile,
  ProgressBar,
  RatioStat,
  StatusTile,
  StatusTileStrip,
  StepCounter,
  UploadRing,
} from "./progress";
import { practiceOpen } from "./progress-model";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function reduceMotion(): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query === REDUCED_MOTION_QUERY,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    })),
  );
}

function moving(root: HTMLElement): Element[] {
  return [...root.querySelectorAll("*")].filter((el) =>
    /\bmotion-|\btransition-/.test(el.getAttribute("class") ?? ""),
  );
}

describe("ProgressBar", () => {
  it("says n of N on the left, a 3px track, and is a progressbar with the numbers", () => {
    render(<ProgressBar done={9} total={13} right="Started 20 minutes ago" />);
    expect(screen.getByText("9 of 13 complete")).toBeTruthy();
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("9");
    expect(bar.getAttribute("aria-valuemax")).toBe("13");
    expect(bar.getAttribute("aria-label")).toBe("9 of 13");
    expect(bar.className).toContain("h-[3px]");
    expect((bar.firstElementChild as HTMLElement).style.width).toBe("69%");
    expect(screen.getByText("Started 20 minutes ago").className).toContain("text-ink-3");
  });

  it("is espresso by default and amber for uploads, never green", () => {
    const { container, rerender } = render(<ProgressBar done={3} total={18} />);
    expect(container.querySelector(".bg-espresso")).toBeTruthy();
    rerender(<ProgressBar done={3} total={18} tone="amber" noun="files uploaded" />);
    expect(container.querySelector(".bg-amber")).toBeTruthy();
    expect(container.innerHTML).not.toMatch(/bg-green/);
    expect(screen.getByText("3 of 18 files uploaded")).toBeTruthy();
  });

  it("moves its width over 400ms only when the count changes (a transition, no loop)", () => {
    const { container } = render(<ProgressBar done={3} total={18} />);
    const fill = container.querySelector<HTMLElement>("[role='progressbar'] > span");
    expect(fill?.className).toContain("transition-[width]");
    expect(fill?.className).toContain("duration-400");
    expect(container.innerHTML).not.toMatch(/motion-slide/);
  });

  it("is indeterminate only for an unknown total", () => {
    const { container } = render(<ProgressBar done={0} total={null} tone="amber" />);
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBeNull();
    expect(bar.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Counting files…")).toBeTruthy();
    expect(container.querySelector(".motion-slide")).toBeTruthy();
    expect(container.querySelector(".w-\\[30\\%\\]")).toBeTruthy();
  });

  it("holds still under reduced motion", () => {
    reduceMotion();
    const { container } = render(
      <div>
        <ProgressBar done={3} total={null} tone="amber" />
        <ProgressBar done={3} total={18} />
      </div>,
    );
    expect(moving(container)).toEqual([]);
    expect(container.querySelector("[data-motion='still']")).toBeTruthy();
  });
});

describe("RatioStat", () => {
  it("shows whole percents with the counts, over a caption", () => {
    render(
      <RatioStat
        items={[
          { done: 4, total: 24, caption: "Accounts Reconciled" },
          { done: 13, total: 20, caption: "Documents Received" },
        ]}
      />,
    );
    expect(screen.getByText("17% (4 / 24)")).toBeTruthy();
    expect(screen.getByText("65% (13 / 20)")).toBeTruthy();
    expect(screen.getByText("Accounts Reconciled").className).toContain("text-ink-3");
  });
});

describe("UploadRing", () => {
  it("is a progressbar named by its caption and its state", () => {
    const { rerender } = render(<UploadRing fraction={0.45} caption="Uploading" />);
    const ring = screen.getByRole("progressbar");
    expect(ring.getAttribute("aria-valuenow")).toBe("45");
    expect(ring.getAttribute("aria-label")).toBe("Uploading, uploading");
    rerender(<UploadRing fraction={1} caption="Uploaded" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-label")).toBe("Uploaded, uploaded");
    expect(screen.getByRole("progressbar").getAttribute("data-done")).toBe("true");
  });

  it("draws no arc at 0 and fades the ring and the file out at 100%", () => {
    const { container, rerender } = render(<UploadRing fraction={0} caption="Waiting" />);
    expect(container.querySelectorAll("svg circle")).toHaveLength(1);
    rerender(<UploadRing fraction={0.5} caption="Uploading" />);
    expect(container.querySelectorAll("svg circle")).toHaveLength(2);
    rerender(<UploadRing fraction={1} caption="Uploaded" />);
    expect(container.querySelector("svg")?.getAttribute("class")).toContain("opacity-0");
    expect(container.querySelector("[data-icon='check']")?.parentElement?.className).toContain(
      "opacity-100",
    );
  });

  it("jumps under reduced motion", () => {
    reduceMotion();
    const { container } = render(<UploadRing fraction={0.45} caption="Uploading" />);
    expect(moving(container)).toEqual([]);
  });
});

describe("StepCounter", () => {
  const steps = [
    { name: "Read the general ledger", done: 312, total: 312 },
    { name: "Match bank transactions", done: 10, total: 312 },
    { name: "Draft reconciling entries", done: 0, total: 18 },
    { name: "Wait for the reviewer", done: 0, total: 0 },
  ];
  it("is a list of Agent run steps with one in progress and a dash for an unknown total", () => {
    render(<StepCounter steps={steps} />);
    const list = screen.getByRole("list", { name: "Agent run steps" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows.map((r) => r.getAttribute("data-step"))).toEqual([
      "done",
      "progress",
      "pending",
      "pending",
    ]);
    expect(within(rows[0] as HTMLElement).getByText("312 of 312 · 100%")).toBeTruthy();
    expect(within(rows[1] as HTMLElement).getByText("10 of 312 · 3%")).toBeTruthy();
    expect(within(rows[3] as HTMLElement).getByText("—")).toBeTruthy();
    expect(within(rows[1] as HTMLElement).getByRole("img", { name: "In progress" })).toBeTruthy();
    expect(within(rows[2] as HTMLElement).getByRole("img", { name: "Not started" })).toBeTruthy();
    expect(within(rows[0] as HTMLElement).getByRole("img", { name: "Done" })).toBeTruthy();
  });
});

describe("KpiTile", () => {
  it("colours a delta by good or bad and draws the arrow by direction", () => {
    const { container } = render(
      <KpiGrid>
        <KpiTile
          label="Returns filed this week"
          value="38"
          delta={{ text: "12 more than last week", tone: "good" }}
          spark={[1, 2, 3]}
        />
        <KpiTile
          label="Unbilled WIP"
          value="$412,860"
          delta={{ text: "6.1% since August 31", tone: "good-down" }}
        />
        <KpiTile
          label="Open issues"
          value="47"
          delta={{ text: "9 more since Monday", tone: "bad" }}
        />
        <KpiTile
          label="Average days to file"
          value="11.4"
          delta={{ text: "Same as last season", tone: "flat" }}
        />
      </KpiGrid>,
    );
    const deltas = [...container.querySelectorAll<HTMLElement>("[data-delta]")];
    expect(deltas.map((d) => d.dataset["delta"])).toEqual(["good", "good", "bad", "flat"]);
    expect(deltas[0]?.className).toContain("text-green-ink");
    expect(deltas[2]?.className).toContain("text-red-ink");
    expect(deltas[3]?.className).toContain("text-ink-3");
    expect(deltas[0]?.querySelectorAll("svg")).toHaveLength(1);
    expect(deltas[3]?.querySelectorAll("svg")).toHaveLength(0);
    expect(container.querySelectorAll("polyline")).toHaveLength(1);
  });

  it("every tile is at least as tall as the card skeleton, so a tile without a sparkline stretches to its row", () => {
    const { container } = render(<KpiTile label="Average days to file" value="11.4" />);
    expect((container.firstElementChild as HTMLElement).style.minHeight).toBe("88px");
  });

  it("rises 45ms apart, and not at all under reduced motion", () => {
    const { container } = render(
      <div>
        <KpiTile index={0} label="A" value="1" />
        <KpiTile index={3} label="B" value="2" />
      </div>,
    );
    const tiles = [...container.querySelectorAll<HTMLElement>("[data-kpi='tile']")];
    expect(tiles[0]?.style.animationDelay).toBe("");
    expect(tiles[1]?.style.animationDelay).toBe("135ms");
    cleanup();
    reduceMotion();
    const still = render(<KpiTile index={3} label="B" value="2" />);
    expect(moving(still.container)).toEqual([]);
  });
});

describe("StatusTile", () => {
  it("is 120 by 72 on the practice strip and 120 by 99 on Home", () => {
    const { container } = render(
      <div>
        <StatusTile count={17} label="Prepared" />
        <StatusTile size="home" count={17} label="Prepared" />
      </div>,
    );
    const [practice, home] = [...container.querySelectorAll<HTMLElement>("[data-tile]")];
    expect(practice?.className).toContain("h-[72px]");
    expect(practice?.className).toContain("w-[120px]");
    expect(home?.className).toContain("h-[99px]");
    expect(home?.className).toContain("rounded-dialog");
  });

  it("keeps KPI type at 22px or less on both", () => {
    const { container } = render(
      <StatusTile size="home" count={7} label="Ready" variant="green-tint" />,
    );
    expect(container.innerHTML).toContain("text-kpi");
    expect(container.innerHTML).not.toMatch(/text-\[2[3-9]px\]|text-\[[3-9]\dpx\]/);
  });

  it("drops a long label to 10.5px and truncates at 116", () => {
    const { container } = render(
      <div>
        <StatusTile count={10} label="Awaiting signature" variant="amber" mark="dot" />
        <StatusTile count={145} label="Prepared" />
      </div>,
    );
    const pills = [...container.querySelectorAll<HTMLElement>("[data-tile] > span:last-child")];
    expect(pills[0]?.className).toContain("text-micro");
    expect(pills[0]?.className).toContain("max-w-[116px]");
    expect(pills[1]?.className).not.toContain("text-micro");
  });

  it("draws the check on Filed · Accepted on solid green, and a dot on Awaiting signature", () => {
    const { container } = render(
      <div>
        <StatusTile count={145} label="Filed · Accepted" variant="green" mark="check" />
        <StatusTile count={10} label="Awaiting signature" variant="amber" mark="dot" />
      </div>,
    );
    const [filed, awaiting] = [...container.querySelectorAll<HTMLElement>("[data-tile]")];
    expect(filed?.querySelector("svg")).toBeTruthy();
    expect(filed?.querySelector(".bg-green")).toBeTruthy();
    expect(awaiting?.querySelector(".bg-amber.size-\\[6px\\]")).toBeTruthy();
  });

  it("a tile that filters is a pressed button", () => {
    const pick = vi.fn();
    render(<StatusTile count={11} label="Issues" variant="red-tint" selected onSelect={pick} />);
    const tile = screen.getByRole("button", { name: /Issues/ });
    expect(tile.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(tile);
    expect(pick).toHaveBeenCalledOnce();
  });

  it("the practice strip adds up to 79 open and 224 returns, with the totals beside the tiles", () => {
    const counts = [17, 15, 11, 7, 8, 9, 10];
    const open = practiceOpen(counts, 2);
    render(
      <StatusTileStrip
        label="Tax returns by status"
        side={`${String(open)} open · 145 done · ${String(open + 145)} TY2025 returns`}
      >
        <StatusTile count={17} label="Prepared" />
      </StatusTileStrip>,
    );
    expect(screen.getByRole("group", { name: "Tax returns by status" })).toBeTruthy();
    expect(screen.getByText("79 open · 145 done · 224 TY2025 returns")).toBeTruthy();
  });
});
