import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installDomShims } from "../test-dom";
import { CapabilityMatrix, type CapabilityWords, capabilityText } from "./capability-matrix";

// CapabilityMatrix (G-01 §5.2, ADM-02b; AC5.4 and §5.5): five marks with text alternatives, a
// highlighted column, and a ◐ whose condition opens on focus as well as hover.

beforeAll(installDomShims);
afterEach(cleanup);

const WORDS: CapabilityWords = {
  allow: "Allowed",
  allowWith: (c) => `Allowed: ${c}`,
  conditional: (c) => `Allowed with a condition: ${c}`,
  delegated: "Draft or propose only",
  deny: "No access",
  locked: "Locked",
};

const COLUMNS = [
  { key: "partner", label: "Partner" },
  { key: "senior", label: "Senior" },
  { key: "staff", label: "Staff" },
];

function show(highlight: string | null = null) {
  return render(
    <CapabilityMatrix
      label="Capabilities by role template"
      header="Capability"
      columns={COLUMNS}
      highlight={highlight}
      words={WORDS}
      rows={[
        {
          key: "reviewer_sign_off",
          label: "Reviewer sign-off L2/L3",
          cells: { partner: "allow", senior: "conditional", staff: "deny" },
          conditions: { senior: "staff work only" },
        },
        {
          key: "release_audit_report",
          label: "Release audit report",
          cells: { partner: "allow", senior: "delegated", staff: "locked" },
          conditions: { partner: "EP only" },
        },
      ]}
    />,
  );
}

describe("CapabilityMatrix", () => {
  it("is a table with scoped column and row headers", () => {
    show();
    const table = screen.getByRole("table", { name: "Capabilities by role template" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Capability", "Partner", "Senior", "Staff"]);
    expect(within(table).getByRole("rowheader", { name: "Release audit report" })).toBeTruthy();
  });

  it("gives every mark a text alternative", () => {
    show();
    expect(screen.getByRole("img", { name: "Allowed" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Allowed: EP only" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Draft or propose only" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "No access" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Locked" })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Allowed with a condition: staff work only" }),
    ).toBeTruthy();
  });

  it("opens a ◐'s condition on focus (AC5.4)", async () => {
    show();
    const half = screen.getByRole("button", { name: "Allowed with a condition: staff work only" });
    fireEvent.focus(half);
    expect((await screen.findAllByText("staff work only")).length).toBeGreaterThan(0);
  });

  it("highlights the selected column", () => {
    const { container } = show("partner");
    const marked = container.querySelectorAll("[data-highlight]");
    expect(marked).toHaveLength(1);
    expect(marked[0]?.textContent).toBe("Partner");
  });

  it("words each cell", () => {
    expect(capabilityText("conditional", "approved batch", WORDS)).toBe(
      "Allowed with a condition: approved batch",
    );
    expect(capabilityText("allow", undefined, WORDS)).toBe("Allowed");
  });
});
