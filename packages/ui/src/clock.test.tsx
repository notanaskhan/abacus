import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClockProvider, useFormat, useNow, useToday } from "./clock";
import { Amount, DateText } from "./components/amount";

// Amount, DateText and the clock hooks (F-05-T10). The formatting rules are in format.test.ts.
const NOW = new Date("2026-09-14T09:24:00-05:00"); // Monday, 9:24 AM in Chicago

afterEach(cleanup);

describe("Amount and DateText", () => {
  it("Amount takes its colour from the tone", () => {
    render(
      <>
        <Amount value="-6821" style="whole" data-testid="neg" />
        <Amount value="0" data-testid="zero" />
        <Amount value="0" zero="explicit" data-testid="zero-explicit" />
        <Amount value="1462726.47" data-testid="pos" />
        <Amount value={null} data-testid="blank" />
      </>,
    );
    expect(screen.getByTestId("neg").textContent).toBe("(6,821)");
    expect(screen.getByTestId("neg").className).toContain("text-negative");
    expect(screen.getByTestId("neg").className).toContain("tabular-nums");
    expect(screen.getByTestId("zero").textContent).toBe("—");
    expect(screen.getByTestId("zero").className).toContain("text-ink-4");
    expect(screen.getByTestId("zero-explicit").textContent).toBe("$0.00");
    expect(screen.getByTestId("pos").textContent).toBe("$1,462,726.47");
    expect(screen.getByTestId("pos").className).not.toContain("text-");
    expect(screen.getByTestId("blank").textContent).toBe("—");
  });

  it("DateText reads against the clock the app provides", () => {
    render(
      <ClockProvider now={() => NOW.getTime()}>
        <DateText value="2026-09-13T20:00:00Z" kind="relative" data-testid="rel" />
        <DateText value="2026-08-07T15:00:00Z" data-testid="date" />
        <DateText value="2026-10-15" withYear data-testid="due" />
        <DateText value="2026-05-11T16:03:00Z" kind="dateTime" zone data-testid="dt" />
        <DateText value={null} data-testid="none" />
      </ClockProvider>,
    );
    expect(screen.getByTestId("rel").textContent).toBe("Yesterday");
    expect(screen.getByTestId("date").textContent).toBe("Aug 7");
    expect(screen.getByTestId("due").textContent).toBe("Oct 15, 2026");
    expect(screen.getByTestId("due").getAttribute("datetime")).toBe("2026-10-15");
    expect(screen.getByTestId("dt").textContent).toBe("May 11, 2026 11:03 AM CT");
    expect(screen.getByTestId("none").textContent).toBe("—");
  });
});

describe("ClockProvider", () => {
  function Probe(): React.JSX.Element {
    const now = useNow(1000);
    const today = useToday();
    const f = useFormat();
    return (
      <p>{`${now.toISOString()}|${today}|${f.relative("2026-09-13T20:00:00Z")}|${f.date("2026-01-02")}`}</p>
    );
  }

  it("serves the app's now-source and zone to the hooks", () => {
    render(
      <ClockProvider now={() => NOW}>
        <Probe />
      </ClockProvider>,
    );
    expect(
      screen.getByText(/^2026-09-14T14:24:00.000Z\|2026-09-14\|Yesterday\|Jan 2$/),
    ).toBeTruthy();
  });

  it("uses the firm's zone for today", () => {
    const late = new Date("2026-09-15T03:00:00Z"); // 10 PM Sep 14 in Chicago, Sep 15 in Berlin
    function Today(): React.JSX.Element {
      return <p>{useToday()}</p>;
    }
    const { rerender } = render(
      <ClockProvider now={() => late}>
        <Today />
      </ClockProvider>,
    );
    expect(screen.getByText("2026-09-14")).toBeTruthy();
    rerender(
      <ClockProvider now={() => late} tz="Europe/Berlin">
        <Today />
      </ClockProvider>,
    );
    expect(screen.getByText("2026-09-15")).toBeTruthy();
  });

  it("re-reads the source on every tick", () => {
    vi.useFakeTimers();
    let ms = NOW.getTime();
    const source = (): number => ms;
    render(
      <ClockProvider now={source}>
        <Probe />
      </ClockProvider>,
    );
    expect(screen.getByText(/^2026-09-14T14:24:00/)).toBeTruthy();
    ms += 3_600_000;
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/^2026-09-14T15:24:00/)).toBeTruthy();
    vi.useRealTimers();
  });

  it("falls back to the device clock without a provider", () => {
    render(<Probe />);
    expect(screen.getByText(/^\d{4}-\d{2}-\d{2}T/)).toBeTruthy();
  });
});
