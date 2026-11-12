// T-04-T41 (SPEC-649 §3.8; TXI-03 a–e in fixture mode). Acceptance: "TXI-03a-e render from
// scenarios, the tables foot to the acceptance checklist, cells deep-link to TXI-01 fields and
// TXI-02 treatment 7, and Send is absent for the agent and for non-reviewers."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COPY, CREDITS, FRAMES, INCOME, NOTES } from "./copy";
import { ResidencyAllocation } from "./Residency";

afterEach(cleanup);

const n = (s: string): number => (s === "—" || s === "" ? 0 : Number(s.replace(/,/g, "")));
const col = (rows: readonly (readonly string[])[], i: number): number[] =>
  rows.filter((r) => r[0] !== "TOTAL").map((r) => n(r[i] ?? ""));
const total = (rows: readonly (readonly string[])[], i: number): number =>
  n(rows.find((r) => r[0] === "TOTAL")?.[i] ?? "");
const sum = (xs: number[]): number => xs.reduce((a, b) => a + b, 0);

describe("TXI-03 state residency and allocation", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<ResidencyAllocation frame={frame} />);
    expect(document.querySelector(`[data-screen='TXI-03'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("TXI-03 acceptance: income by jurisdiction foots", () => {
    expect(sum(col(INCOME, 1))).toBe(598_030);
    expect(total(INCOME, 1)).toBe(598_030);
    expect(598_030 + 1_550 + 16_025).toBe(615_605);
    expect(sum(col(INCOME, 2))).toBe(total(INCOME, 2));
    expect(total(INCOME, 2)).toBe(615_605);
    expect(sum(col(INCOME, 3))).toBe(615_605);
    expect(sum(col(CREDITS, 1))).toBe(307_900);
  });

  it("TXI-03 acceptance: PTET credits and the resident credit", () => {
    expect(sum(col(CREDITS, 4))).toBe(16_025);
    expect(total(CREDITS, 4)).toBe(16_025);
    expect(sum(col(CREDITS, 3))).toBe(64_096);
    expect(Math.min(7_011 + 4_268, Math.round((41_070 * 238_623) / 615_605))).toBe(11_279);
    expect(Math.round((41_070 * 238_623) / 615_605)).toBe(15_920);
    expect(4_746 + 11_279).toBe(16_025);
    expect(NOTES.find(([k]) => k === "NYC")?.[1]).toContain("No credit for other-state taxes");
  });

  it("the tables carry no $", () => {
    render(<ResidencyAllocation frame="a" />);
    for (const table of document.querySelectorAll("table")) {
      expect(table.textContent).not.toContain("$");
    }
  });

  it("a: the review point, the agent's recommendation, Confirm for a reviewer", () => {
    const onConfirm = vi.fn();
    render(<ResidencyAllocation frame="a" onConfirm={onConfirm} />);
    expect(document.querySelector("[data-tally='residency']")?.textContent).toContain(
      "Review point",
    );
    expect(
      document.querySelector("[data-option='full_year_nys_nyc'] [data-recommended]"),
    ).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: COPY.confirm }));
    expect(onConfirm).toHaveBeenCalledWith("full_year_nys_nyc");
  });

  it("b: confirmed by Samuel Ito and the tally reads Confirmed", () => {
    render(<ResidencyAllocation frame="b" />);
    expect(screen.getByRole("status").textContent).toBe(COPY.confirmed);
    expect(document.querySelector("[data-tally='residency']")?.textContent).toContain("Confirmed");
    expect(screen.queryByRole("button", { name: COPY.confirm })).toBeNull();
  });

  it("c: Action required, option 2 recommended, Ask the client primary", () => {
    render(<ResidencyAllocation frame="c" />);
    expect(screen.getByRole("alert").textContent).toBe(COPY.actionRequired);
    expect(
      document.querySelector("[data-option='full_year_nys_part_year_nyc'] [data-recommended]"),
    ).not.toBeNull();
    const ask = screen.getByRole("button", { name: COPY.askClient });
    expect(ask.getAttribute("data-variant")).toBe("primary");
  });

  it("d: the POR-04 preview with Send for a reviewer; Send is absent for others", () => {
    const onSend = vi.fn();
    render(<ResidencyAllocation frame="d" onSend={onSend} />);
    const sheet = screen.getByRole("dialog", { name: "Ask the client" });
    expect(sheet.textContent).toContain(COPY.sheetQuestion);
    fireEvent.click(screen.getByRole("button", { name: COPY.send }));
    expect(onSend).toHaveBeenCalledOnce();
    cleanup();
    render(<ResidencyAllocation frame="d" reviewer={false} />);
    expect(screen.queryByRole("button", { name: COPY.send })).toBeNull();
    expect(screen.queryByRole("button", { name: COPY.confirm })).toBeNull();
  });

  it("e: the loading skeleton reads Sourcing by property…", () => {
    render(<ResidencyAllocation frame="e" />);
    expect(document.querySelector("[data-skeleton][aria-busy='true']")?.textContent).toContain(
      COPY.loading,
    );
  });

  it("cells deep-link to TXI-01 fields and the PTET share to TXI-02 treatment 7", () => {
    const onCell = vi.fn();
    render(<ResidencyAllocation frame="a" onCell={onCell} />);
    const il = document.querySelector("[data-cell='TXI-01:il1040_schnr']") as HTMLElement;
    fireEvent.click(il);
    expect(onCell).toHaveBeenCalledWith("TXI-01:il1040_schnr");
    const ptet = document.querySelector("[data-cell='TXI-02:7']") as HTMLElement;
    fireEvent.click(ptet);
    expect(onCell).toHaveBeenLastCalledWith("TXI-02:7");
  });
});
