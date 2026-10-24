import { cleanup, fireEvent, render, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { NORTHWIND_PBC } from "../specimens/seed-figures";
import { RUN_PROJECTION, Tpl02Board } from "../specimens/tpl02";
import { installDomShims } from "../test-dom";

// F-05-T51: "Rail counts tie at 11 of 24 (3+4+3+1), the trial balance tie reads $16,812,400.00, and
// dock content in a, c and d is masked until the P-04 and P-09 kits land." Plus the TPL-02 states:
// idle with Run, the blocked focus, the failed step with Retry, the pill rail, and the live canvas
// (search, sort, a document opening the viewer).

beforeAll(installDomShims);
afterEach(cleanup);

function board(id: string): HTMLElement {
  const { container } = render(<Tpl02Board id={id} />);
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no board ${id}`);
  return el;
}

const part = (el: HTMLElement, name: string): HTMLElement => {
  const found = el.querySelector<HTMLElement>(`[data-cockpit="${name}"]`);
  if (found === null) throw new Error(`no ${name}`);
  return found;
};

describe("TPL-02 Northwind 401(k) cockpit", () => {
  it("ties the rail's 11 of 24 to the canvas's Received pills, 3 + 4 + 3 + 1", () => {
    const a = board("tpl-02a");
    const rail = part(a, "rail");
    expect(within(rail).getByText("11 of 24 received")).toBeTruthy();
    const canvas = part(a, "canvas");
    const received = canvas.querySelectorAll('[data-source-docs="row"][data-status="received"]');
    expect(received.length).toBe(11);
    const bands = [...canvas.querySelectorAll('[data-source-docs="group"] > button')].map(
      (b) => b.textContent,
    );
    expect(bands).toEqual([
      "Plan documents3 of 5",
      "Trust / Recordkeeper Reports4 of 6",
      "Census & Payroll3 of 7",
      "Form 5500 & SOC 11 of 4",
      "Cash0 of 1",
      "Compliance & other0 of 1",
    ]);
    expect(canvas.querySelectorAll('[data-source-docs="row"]').length).toBe(NORTHWIND_PBC.length);
  });

  it("the trial balance tie reads $16,812,400.00 = $16,500,000.00 + $312,400.00", () => {
    const dock = part(board("tpl-02a"), "dock");
    expect(dock.textContent).toContain(
      "agreed to the Harborline Trust Company net trust assets: $16,812,400.00 at 12/31/2025 (investments $16,500,000.00 + participant notes $312,400.00)",
    );
    expect(dock.textContent).toContain("unadjusted net assets of $16,812,400.");
    expect(dock.textContent).toContain("Margaret Okonkwo");
  });

  it("masks the dock content in a, c and d, never in b or e", () => {
    for (const id of ["tpl-02a", "tpl-02c", "tpl-02d"]) {
      const dock = part(board(id), "dock");
      expect(dock.querySelector("[data-parity-mask]"), id).not.toBeNull();
      cleanup();
    }
    for (const id of ["tpl-02b", "tpl-02e"]) {
      const dock = part(board(id), "dock");
      expect(dock.querySelector("[data-parity-mask]"), id).toBeNull();
      cleanup();
    }
  });

  it("the run projection reads 14 workpapers across 5 levels, Planning 0 of 5", () => {
    expect(RUN_PROJECTION.reduce((n, l) => n + l.total, 0)).toBe(14);
    const projection = board("tpl-02a").querySelector<HTMLElement>('[data-tpl02="projection"]');
    expect(projection?.textContent).toContain("Run projection · 14 workpapers · 5 levels");
    expect(projection?.textContent).toContain("Planning1 blocked · 1 running0 of 5");
  });

  it("idle: every rail row is Not started and Run starts the run", () => {
    const b = board("tpl-02b");
    const rail = part(b, "rail");
    expect(within(rail).getAllByText("Not started").length).toBe(8);
    // The band and the overview card's state pill.
    expect(within(rail).getAllByText("Planning").length).toBe(2);
    const dock = part(b, "dock");
    expect(dock.textContent).toContain("Ready to run 14 workpapers across 5 levels");
    fireEvent.click(within(dock).getByRole("button", { name: "Run" }));
    expect(dock.querySelector("[data-parity-mask]")).not.toBeNull();
    expect(within(rail).getByText("Blocked on a partner decision")).toBeTruthy();
  });

  it("the rail's sub-lines are the spec's words, each beside its disc", () => {
    const rail = part(board("tpl-02a"), "rail");
    for (const words of [
      "Complete · 9:26 AM",
      "Blocked on a partner decision",
      "Running",
      "Queued",
      "Not started",
    ]) {
      expect(within(rail).getAllByText(words).length, words).toBeGreaterThan(0);
    }
    expect(within(rail).getAllByText("Waiting on inputs").length).toBe(3);
  });

  it("blocked focus: Materiality waits on Margaret Okonkwo with Open decision", () => {
    const canvas = part(board("tpl-02c"), "canvas");
    expect(within(canvas).getByText("Waiting on Margaret Okonkwo")).toBeTruthy();
    expect(within(canvas).getByRole("button", { name: "Open decision →" })).toBeTruthy();
  });

  it("failed step: Internal Control reads Failed — see run, and Retry runs it again", () => {
    const d = board("tpl-02d");
    const rail = part(d, "rail");
    expect(within(rail).getByText("Failed — see run")).toBeTruthy();
    fireEvent.click(within(part(d, "dock")).getByRole("button", { name: "Retry" }));
    expect(within(rail).queryByText("Failed — see run")).toBeNull();
  });

  it("the idle rail variant carries Ready and In progress pills", () => {
    const rail = part(board("tpl-02e"), "rail");
    expect(within(rail).getAllByText("Ready").length).toBe(1);
    expect(within(rail).getAllByText("In progress").length).toBe(5);
  });

  it("search filters the documents, the sort flips, and a row opens the viewer", () => {
    const a = board("tpl-02a");
    const canvas = part(a, "canvas");
    fireEvent.change(within(canvas).getByRole("searchbox", { name: "Search" }), {
      target: { value: "keystone" },
    });
    // Titles only: the Keystone bridge letter and SOC 1 report.
    expect(canvas.querySelectorAll('[data-source-docs="row"]').length).toBe(2);
    fireEvent.change(within(canvas).getByRole("searchbox", { name: "Search" }), {
      target: { value: "" },
    });
    const first = (): string | null | undefined =>
      canvas.querySelector('[data-source-docs="row"]')?.getAttribute("data-status");
    expect(first()).toBe("requested");
    fireEvent.click(within(canvas).getByRole("button", { name: "Missing first" }));
    expect(first()).toBe("received");
    fireEvent.click(within(canvas).getByRole("button", { name: /Adoption agreement/ }));
    const dock = part(a, "dock");
    expect(dock.getAttribute("data-view")).toBe("Viewer");
    expect(dock.textContent).toContain("Adoption agreement");
  });

  it("Sign off run is a disabled HumanAction; the toggle reads Auto mode", () => {
    const a = board("tpl-02a");
    const signOff = within(part(a, "dock")).getByRole("button", { name: "Sign off run" });
    expect(signOff.getAttribute("data-human-verb")).toBe("Sign off");
    expect((signOff as HTMLButtonElement).disabled).toBe(true);
    expect(within(a).getByText("Auto mode")).toBeTruthy();
  });
});
