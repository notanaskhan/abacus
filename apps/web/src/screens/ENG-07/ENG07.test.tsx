// T-08-T15 (TASK-8841; docs/screens/ENG-07.md): "ENG-07 a-e render from data with verbatim copy,
// Approve is absent for Grace Holloway, and no count is computed in the browser."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { scenarios } from "../../fixtures/scenarios/ENG-07";
import { manifest, rows } from "../../fixtures/seed/eng07";
import { COPY } from "./copy";
import { ENG07, tallyItems } from ".";

afterEach(cleanup);

describe("ENG-07 Season setup", () => {
  it("covers a–e and the two composed states", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e", "x1", "x2"]);
  });

  it("a: 214 · 224 · 241, 4 of 6, created 126, cohort 5 under review", () => {
    render(<ENG07 manifest={manifest()} rows={rows()} view="cohorts" />);
    const items = tallyItems(manifest());
    expect(items.map((i) => ("value" in i ? i.value : ""))).toEqual([
      "214",
      "224",
      "241",
      "4 of 6",
      "126",
      "3",
    ]);
    expect(document.querySelectorAll("[data-cohort]")).toHaveLength(6);
    expect(screen.getByText("Jonah & Claire Feld")).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.bar.approve(5) })).toBeTruthy();
    expect(screen.getByText(COPY.bar.helper)).toBeTruthy();
  });

  it("a: Approve opens the confirm Dialog and approves on confirm", () => {
    const onApprove = vi.fn();
    render(<ENG07 manifest={manifest()} rows={rows()} view="cohorts" onApprove={onApprove} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.bar.approve(5) }));
    expect(screen.getByText(COPY.bar.confirm(38, "New York"))).toBeTruthy();
  });

  it("b: approved, queued after cohort 4, 5 of 6", () => {
    render(<ENG07 manifest={manifest("approved")} rows={rows()} view="cohorts" />);
    expect(screen.getByText(COPY.queuedAfter(4))).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.bar.approve(5) })).toBeNull();
    expect(tallyItems(manifest("approved"))[3]).toMatchObject({ value: "5 of 6" });
  });

  it("c: executing cohort 3 with the attributed running pill", () => {
    render(<ENG07 manifest={manifest("executing")} rows={rows(3)} view="cohorts" expanded={3} />);
    expect(screen.getByText(COPY.running(3, "Isaac Moreau"))).toBeTruthy();
    expect(screen.getByText(COPY.executingOf(31, 42))).toBeTruthy();
  });

  it("d: exceptions list Osterberg, Farouk and Barlow with Reassign and Exclude", () => {
    render(<ENG07 manifest={manifest()} rows={rows()} view="exceptions" />);
    expect(document.querySelectorAll("[data-row]")).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: COPY.reassign })).toHaveLength(3);
  });

  it("e: the ask card answers once; x1 planner off shows the code exception", () => {
    const onAnswer = vi.fn();
    render(<ENG07 manifest={manifest()} rows={rows()} view="cohorts" onAnswer={onAnswer} />);
    fireEvent.click(screen.getByRole("button", { name: "One binder (recommended)" }));
    expect(onAnswer).toHaveBeenCalledTimes(1);
    cleanup();
    render(<ENG07 manifest={manifest("agentsOff")} rows={rows()} view="cohorts" />);
    expect(screen.getByText(COPY.plannerOff)).toBeTruthy();
  });

  it("Approve is absent for Grace Holloway (no approve action on her cohort view)", () => {
    const m = manifest();
    const forGrace = { ...m, cohorts: m.cohorts.map((c) => ({ ...c, allowed_actions: [] })) };
    render(<ENG07 manifest={forGrace} rows={rows()} view="cohorts" />);
    expect(screen.queryByRole("button", { name: COPY.bar.approve(5) })).toBeNull();
  });
});
