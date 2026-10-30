import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentOnWell, type DocumentOnWellProps } from "./DocumentOnWell";
import type { DocumentVM } from "./types";

// F-06-T14 (SPEC-400 AC-19, AC-21; F-06 Stories 4.1 and 4.3): "T10a shows three skeleton
// paragraphs under a header spinner with no approval control enabled, and T10b shows the DRAFT
// watermark at 6 percent ink with citation markers." F-06-T17 owns the independent suite.

afterEach(cleanup);

const COPY = {
  edit: "Edit",
  regenerate: "Regenerate…",
  drafting: "Accrued Agent is drafting the memo",
  rendering: "Preparing the document",
  watermark: "DRAFT",
  variables: "Variables",
};

const TOOLBAR = {
  firm: "Brightwater Hale",
  nav: [],
  active: "Tax Returns",
} as unknown as DocumentOnWellProps["toolbar"];

function doc(extra: Partial<DocumentVM> = {}): DocumentVM {
  return {
    status: "draft",
    variant: "paper",
    structure: {
      kind: "kv",
      sheets: [
        {
          crumb: "Partnership › General Information",
          sections: [
            {
              title: "Partners",
              rows: [
                { key: "General partner", value: "Ridgeline GP, LLC", linkId: "gp" },
                { key: "Section 754 election", value: null },
              ],
            },
          ],
        },
      ],
    },
    title: "Return Summary",
    watermark: true,
    actions: {
      edit: true,
      regenerate: true,
      approve: { actor: { kind: "human", name: "Samuel Ito" }, object: "memo" },
    },
    ...extra,
  };
}

function well(document: DocumentVM, extra: Partial<DocumentOnWellProps> = {}) {
  return render(
    <DocumentOnWell document={document} copy={COPY} toolbar={TOOLBAR} record={null} {...extra}>
      <p>Paper body</p>
    </DocumentOnWell>,
  );
}

describe("T10a: drafting", () => {
  it("AC-19: three skeleton paragraphs under the header spinner, no body yet", () => {
    well(doc({ status: "drafting", watermark: false }));
    const drafting = document.querySelector('[data-document="drafting"]') as HTMLElement;
    expect(drafting.children).toHaveLength(3);
    expect(screen.getByRole("status").textContent).toContain("Accrued Agent is drafting the memo");
    expect(screen.queryByText("Paper body")).toBeNull();
  });

  it("AC-21: approval and Regenerate are disabled and name the drafting as the reason", () => {
    well(doc({ status: "drafting", watermark: false }));
    const approve = screen.getByRole<HTMLButtonElement>("button", { name: "Approve memo…" });
    const regenerate = screen.getByRole<HTMLButtonElement>("button", { name: "Regenerate…" });
    expect(approve.disabled).toBe(true);
    expect(regenerate.disabled).toBe(true);
    const reason = approve.getAttribute("aria-describedby");
    expect(reason).not.toBeNull();
    expect(document.getElementById(reason ?? "")?.textContent).toContain("drafting the memo");
    expect(regenerate.getAttribute("aria-describedby")).toBe(reason);
  });

  it("a letter without model text has no agent Drafting state (ADR P-25 off)", () => {
    well(doc({ status: "drafting", variant: "letter", watermark: false }));
    expect(screen.getByRole("status").textContent).toContain("Preparing the document");
    expect(screen.queryByText(/Accrued Agent/)).toBeNull();
  });
});

describe("T10b: draft", () => {
  it("AC-19: the DRAFT watermark is decoration at 6 % espresso, hidden from assistive technology", () => {
    well(doc());
    const mark = document.querySelector('[data-document="watermark"]') as HTMLElement;
    expect(mark.textContent).toBe("DRAFT");
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(mark.className).toContain("text-espresso/6");
    expect(mark.className).toContain("text-[72px]");
    expect(screen.getByText("Paper body")).toBeTruthy();
  });

  it("AC-21: Approve only calls onApprove", () => {
    const onApprove = vi.fn();
    well(doc(), { onApprove });
    fireEvent.click(screen.getByRole("button", { name: "Approve memo…" }));
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it("AC-21: an agent actor never gets the approval control (INV-1)", () => {
    well(doc({ actions: { approve: { actor: { kind: "agent" }, object: "memo" } } }));
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
  });

  it("the server withholding document.approve draws it disabled with the reason", () => {
    well(
      doc({
        actions: {
          approve: {
            actor: { kind: "human", name: "Olivia Brandt" },
            object: "memo",
            disabledReason: "Only a partner approves the memo.",
          },
        },
      }),
    );
    const approve = screen.getByRole<HTMLButtonElement>("button", { name: "Approve memo…" });
    expect(approve.disabled).toBe(true);
    const id = approve.getAttribute("aria-describedby") ?? "";
    expect(document.getElementById(id)?.textContent).toBe("Only a partner approves the memo.");
  });
});

describe("T10 geometry and structure", () => {
  it("Tier D: the 470 structure pane, the paper pane and the 600 paper card", () => {
    well(doc());
    const panes = document.querySelectorAll('[data-shell="pane"]');
    expect((panes[0] as HTMLElement).style.width).toBe("470px");
    const paper = document.querySelector('[data-document="paper"]') as HTMLElement;
    expect(paper.className).toContain("w-[600px]");
    expect(paper.className).toContain("px-[24px]");
    expect(paper.className).toContain("pt-[20px]");
    expect(paper.className).toContain("pb-[24px]");
  });

  it("KV rows: a link in ink with →, an empty value as —", () => {
    const onOpenLink = vi.fn();
    well(doc(), { onOpenLink });
    const sheet = document.querySelector('[data-document="kv-sheet"]') as HTMLElement;
    fireEvent.click(within(sheet).getByRole("button", { name: /Ridgeline GP, LLC/ }));
    expect(onOpenLink).toHaveBeenCalledWith("gp");
    expect(within(sheet).getByLabelText("Section 754 election: none").textContent).toBe("—");
  });

  it("locked: clause toggles and variables are read-only (F-06-T15 draws the locked header)", () => {
    well(
      doc({
        status: "locked",
        lockedReason: "Out for signature",
        structure: {
          kind: "clauses",
          clauses: [{ id: "c1", label: "Scope of services", on: true, reason: "Required" }],
          variables: [{ id: "v1", label: "Fee", value: "$18,500" }],
        },
      }),
    );
    expect(
      screen.getByRole<HTMLButtonElement>("switch", { name: "Scope of services" }).disabled,
    ).toBe(true);
    expect(screen.getByText("Variables")).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Edit" }).disabled).toBe(true);
  });
});
