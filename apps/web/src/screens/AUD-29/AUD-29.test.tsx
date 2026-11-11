// P-05-T14 (SPEC-650 AC-31 to AC-35, AC-38; AUD-29 a–f from the seed).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActivityLog } from "./Activity";
import { COPY, COUNTS, EVENTS, FRAMES, TARGETS } from "./copy";

afterEach(cleanup);

const rows = () => document.querySelectorAll("[data-event]");

describe("AUD-29 activity log", () => {
  it.each(FRAMES)("%s renders from the seed", (frame) => {
    render(<ActivityLog frame={frame} />);
    expect(document.querySelector(`[data-screen='AUD-29'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("AC-32: the counts foot, Human 12 + via Agent 11 + Policy 0 = 23", () => {
    expect(COUNTS.human + COUNTS.agent + COUNTS.policy).toBe(COUNTS.all);
    expect(EVENTS).toHaveLength(COUNTS.all);
    expect(EVENTS.filter((e) => e.agent)).toHaveLength(COUNTS.agent);
  });

  it("a: 23 rows newest first with the six day separators", () => {
    render(<ActivityLog frame="a" />);
    expect(rows()).toHaveLength(23);
    const separators = [...document.querySelectorAll("[data-separator]")].map(
      (s) => s.textContent,
    );
    expect(separators).toEqual([...COPY.separators]);
  });

  it("b and c: via Agent 11 and Human 12", () => {
    render(<ActivityLog frame="b" />);
    expect(rows()).toHaveLength(11);
    cleanup();
    render(<ActivityLog frame="c" />);
    expect(rows()).toHaveLength(12);
  });

  it("d: the Policy empty state", () => {
    render(<ActivityLog frame="d" />);
    expect(screen.getByText(COPY.policyEmptyTitle)).toBeTruthy();
    expect(screen.getByText(COPY.policyEmptyBody)).toBeTruthy();
  });

  it("AC-34 e: Materiality finds 11:12, 9:27 and 11:20 (by its detail)", () => {
    render(<ActivityLog frame="e" />);
    const found = [...rows()].map((r) => r.getAttribute("data-event"));
    expect(found).toEqual([
      "Run resumed · Marcus Delaney via Agent",
      "Materiality decided by Margaret Okonkwo",
      "Materiality proposed · Marcus Delaney via Agent",
    ]);
  });

  it("AC-33: no decision-class row carries the agent", () => {
    for (const e of EVENTS) {
      if (/(signed off|decided|accepted|approved|prepared by|signed by)/i.test(e.title)) {
        expect(e.agent).toBe(false);
      }
    }
  });

  it("acceptance AC-35: every row opens its target screen or a registered planned link", () => {
    const onOpen = vi.fn();
    render(<ActivityLog frame="f" onOpen={onOpen} />);
    for (const button of screen.getAllByRole("button", { name: COPY.open }))
      fireEvent.click(button);
    expect(onOpen).toHaveBeenCalledTimes(23);
    for (const [target] of onOpen.mock.calls) expect(TARGETS).toContain(target);
  });

  it("acceptance AC-38: Download shows only when allowed_actions includes export.create", () => {
    render(<ActivityLog frame="a" />);
    expect(screen.queryByRole("button", { name: COPY.download })).toBeNull();
    cleanup();
    const onDownload = vi.fn();
    render(<ActivityLog frame="a" allowedActions={["export.create"]} onDownload={onDownload} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.download }));
    expect(onDownload).toHaveBeenCalledWith("all", "");
  });

  it("the search text goes to the host, never into the address", () => {
    const onSearch = vi.fn();
    render(<ActivityLog frame="a" onSearch={onSearch} />);
    fireEvent.change(screen.getByLabelText(COPY.search), { target: { value: "PBC" } });
    expect(onSearch).toHaveBeenCalledWith("PBC");
    expect(window.location.search).not.toContain("PBC");
    expect(rows()).toHaveLength(2);
  });
});
