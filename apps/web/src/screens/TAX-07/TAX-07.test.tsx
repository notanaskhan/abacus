// T-04-T27 (SPEC-649 AC-5.1 to AC-5.5; TAX-07 a, b, b2, c, d, e, e2 and f in fixture mode).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Activity } from "./Activity";
import { CHECKPOINTS, COPY, DELIVERED, EVENTS, FRAMES } from "./copy";

afterEach(cleanup);

describe("TAX-07 activity and checkpoints", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<Activity frame={frame} />);
    expect(document.querySelector(`[data-screen='TAX-07'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("a: 24 events newest first, Manager review is Current and starred", () => {
    render(<Activity frame="a" />);
    expect(document.querySelectorAll("[data-event]")).toHaveLength(24);
    expect(EVENTS[0]!.title).toBe("Email received from Claire Feld");
    const manager = document.querySelector("[data-checkpoint='manager']");
    expect(manager?.getAttribute("data-state")).toBe("current");
    expect(
      screen.getByRole("button", { name: "Star Manager review" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("acceptance: every approval row names a person and never Accrued Agent", () => {
    for (const e of [...EVENTS, ...DELIVERED].filter((x) => x.kind === "approval")) {
      expect(e.title).not.toMatch(/Accrued Agent/);
    }
    for (const e of EVENTS.filter((x) => x.title.includes("Accrued Agent"))) {
      expect(e.kind).toBe("agent");
      expect(e.title).toMatch(/prepared|self-checked|proposed/);
    }
  });

  it("acceptance: engine ids run V1 Feb 3, V2 Apr 14, V3 Sep 10", () => {
    const imports = EVENTS.filter((e) => e.title.startsWith("Return imported"));
    expect(imports.map((e) => [e.date, e.sub?.split(" ")[0]])).toEqual([
      ["Sep 10", "2025I:FeldJ:V3"],
      ["Apr 14", "2025I:FeldJ:V2"],
      ["Feb 3", "2025I:FeldJ:V1"],
    ]);
  });

  it("events sharing a timestamp keep their causal order: import 9:30 before approval 9:31", () => {
    const i = EVENTS.findIndex((e) => e.time === "9:30 AM" && e.date === "Sep 10");
    const j = EVENTS.findIndex((e) => e.time === "9:31 AM" && e.date === "Sep 10");
    expect(j).toBeLessThan(i); // newest first
  });

  it("b and b2: one proposed checkpoint with Review, and SHL-16's old → new steps", () => {
    render(<Activity frame="b" />);
    expect(screen.getByText(`${COPY.chipProposed} ⌄`)).toBeTruthy();
    expect(
      document.querySelector("[data-checkpoint='box18a'][data-state='proposed']"),
    ).not.toBeNull();
    cleanup();
    render(<Activity frame="b2" />);
    expect(document.querySelectorAll("[data-diff]")).toHaveLength(2);
    expect(screen.getByText("Form 1040 line 2a · 0 → 1,550")).toBeTruthy();
  });

  it("c: no changes needed and Issues 3", () => {
    render(<Activity frame="c" />);
    expect(screen.getByText(`${COPY.chipNone} ⌄`)).toBeTruthy();
    expect(document.querySelector("[data-tab='Issues 3']")).not.toBeNull();
  });

  it("d: the delivered rows newest first", () => {
    render(<Activity frame="d" />);
    const titles = [...document.querySelectorAll("[data-event]")].map((e) =>
      e.getAttribute("data-event"),
    );
    expect(titles.slice(0, 3)).toEqual([
      "NY return accepted",
      "Federal return accepted",
      "Return transmitted by Daniel Reyes",
    ]);
  });

  it("e and e2: the Agent filter, and the empty filter's words", () => {
    render(<Activity frame="e" />);
    for (const row of document.querySelectorAll("[data-event]")) {
      expect(row.getAttribute("data-kind")).toBe("agent");
    }
    cleanup();
    render(<Activity frame="e2" />);
    expect(screen.getByText(COPY.emptyFilter)).toBeTruthy();
  });

  it("search filters rows live", () => {
    render(<Activity frame="a" />);
    fireEvent.change(screen.getByLabelText(COPY.search), { target: { value: "binder" } });
    expect(document.querySelectorAll("[data-event]")).toHaveLength(2);
  });

  it("f: a checkpoint row opens SHL-16, star and Compare… go to the host", () => {
    const onOpenCheckpoint = vi.fn();
    const onStar = vi.fn();
    const onCompare = vi.fn();
    render(
      <Activity
        frame="f"
        onOpenCheckpoint={onOpenCheckpoint}
        onStar={onStar}
        onCompare={onCompare}
      />,
    );
    fireEvent.click(screen.getByText("Initial draft", { selector: "span" }));
    expect(onOpenCheckpoint).toHaveBeenCalledWith("initial");
    fireEvent.click(screen.getByRole("button", { name: "Star Engine import V3" }));
    expect(onStar).toHaveBeenCalledWith("engineV3");
    fireEvent.click(screen.getByRole("button", { name: COPY.compare }));
    expect(onCompare).toHaveBeenCalled();
    expect(CHECKPOINTS.filter((c) => c.starred)).toHaveLength(1);
  });

  it("rows that name a screen open it", () => {
    const onOpenLink = vi.fn();
    render(<Activity frame="a" onOpenLink={onOpenLink} />);
    fireEvent.click(screen.getByText("Email received from Claire Feld"));
    expect(onOpenLink).toHaveBeenCalledWith("INB-01");
  });
});
