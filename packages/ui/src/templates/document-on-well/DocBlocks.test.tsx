// F-06-T15 (T10 DocBlocks): no block renders HTML or model markup; a citation without a typed,
// verified locator renders no marker; "[n]" in text stays literal; agent blocks render only on the
// firm-internal paper unless the consumer passes `modelTextToClients` (ADR P-25 off); a human edit
// is marked; T10c names the approver with a disabled Approved control; T10d disables Edit and
// Regenerate with its reason; the email variant frames at 600 and 390.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MatchScope } from "../../tracing/match";
import type { CitationView } from "../../tracing/types";
import { type DocBlock, DocBlocks, EmailFrame } from "./DocBlocks";
import { DocumentOnWell, type DocumentOnWellProps } from "./DocumentOnWell";
import type { DocumentVM } from "./types";

afterEach(cleanup);

const CITE: CitationView = {
  n: 1,
  title: "Ridgeline 2025 trial balance",
  quote: "1,231,600",
  loc: "Investments!D8",
  match: null,
};

const BLOCKS: readonly DocBlock[] = [
  { kind: "letterhead", firm: "Brightwater Hale LLP", lines: ["Chicago · Denver · New York"] },
  { kind: "h", level: 3, text: "Summary", provenance: "agent" },
  {
    kind: "p",
    provenance: "agent",
    segments: [
      { kind: "text", text: "Total assets are " },
      { kind: "fact", text: "1,231,600" },
      { kind: "text", text: " <b>bold</b> [3]" },
      { kind: "cite", n: 1, citation: CITE, verified: true },
      { kind: "cite", n: 2, citation: { ...CITE, n: 2, loc: "" }, verified: true },
      { kind: "cite", n: 1, citation: CITE, verified: false },
    ],
    editedBy: "Hannah Leclerc",
  },
  {
    kind: "p",
    provenance: "template",
    segments: [{ kind: "text", text: "Please sign and return the enclosed letter." }],
  },
  {
    kind: "table",
    provenance: "agent",
    head: ["Line", "2025"],
    rows: [
      { cells: [[{ kind: "text", text: "Assets" }], [{ kind: "fact", text: "1,231,600" }]] },
      {
        cells: [[{ kind: "text", text: "Total" }], [{ kind: "fact", text: "1,256,200" }]],
        total: true,
      },
    ],
  },
  { kind: "signature", name: "Daniel Reyes", title: "Tax Partner" },
];

function show(variant: "paper" | "letter" | "email", modelTextToClients?: boolean): void {
  render(
    <MatchScope>
      <DocBlocks
        blocks={BLOCKS}
        variant={variant}
        {...(modelTextToClients === undefined ? {} : { modelTextToClients })}
      />
    </MatchScope>,
  );
}

describe("DocBlocks", () => {
  it("renders no HTML and keeps '[n]' literal", () => {
    show("paper");
    expect(document.querySelector("b")).toBeNull();
    expect(screen.getByText(/<b>bold<\/b> \[3\]/)).toBeTruthy();
  });

  it("renders a marker only for a typed, verified locator", () => {
    show("paper");
    const markers = document.querySelectorAll("[data-doc='paragraph'] button");
    expect(markers).toHaveLength(1);
    expect(markers[0]?.textContent).toContain("1");
  });

  it("marks a person's edit and keeps statement totals", () => {
    show("paper");
    expect(screen.getByText("Edited by Hannah Leclerc")).toBeTruthy();
    expect(document.querySelectorAll("tr[data-total]")).toHaveLength(1);
  });

  it.each(["letter", "email"] as const)("drops agent blocks on %s while P-25 is off", (v) => {
    show(v);
    expect(screen.queryByText("Summary")).toBeNull();
    expect(screen.queryByText(/Total assets/)).toBeNull();
    expect(screen.getByText("Please sign and return the enclosed letter.")).toBeTruthy();
    expect(screen.getByText("Brightwater Hale LLP")).toBeTruthy();
    expect(screen.getByText("Daniel Reyes")).toBeTruthy();
  });

  it("shows agent blocks on a letter when the consumer passes modelTextToClients", () => {
    show("letter", true);
    expect(screen.getByText("Summary")).toBeTruthy();
  });

  it.each([600, 390] as const)("frames the email variant at %i", (width) => {
    render(
      <EmailFrame width={width}>
        <p>Hello</p>
      </EmailFrame>,
    );
    expect(
      document.querySelector(`[data-document='email'][data-width='${String(width)}']`),
    ).not.toBeNull();
  });
});

const SAMUEL = { kind: "human" as const, name: "Samuel Ito" };

function cockpit(doc: DocumentVM): void {
  const props: DocumentOnWellProps = {
    document: doc,
    copy: {
      edit: "Edit",
      regenerate: "Regenerate…",
      drafting: "Accrued Agent is drafting the memo",
      rendering: "Preparing the letter",
      watermark: "DRAFT",
      variables: "Variables",
    },
    toolbar: {
      firm: "Brightwater Hale",
      nav: [],
      active: "Tax Returns",
    },
    record: <div />,
  };
  render(<DocumentOnWell {...props} />);
}

const BASE: DocumentVM = {
  status: "approved",
  variant: "paper",
  structure: { kind: "kv", sheets: [] },
  title: "Preparer memo",
  watermark: false,
  approvedBy: { actor: SAMUEL, when: "Sep 14, 9:40 AM" },
  actions: { approve: { actor: SAMUEL, object: "memo" }, edit: true, regenerate: true },
};

describe("T10c and T10d", () => {
  it("c · names Samuel Ito with a disabled Approved control", () => {
    cockpit(BASE);
    expect(screen.getByRole<HTMLButtonElement>("button", { name: /Approved/ }).disabled).toBe(
      true,
    );
    expect(screen.getByText(/Samuel Ito · Sep 14, 9:40 AM/)).toBeTruthy();
  });

  it("d · disables Edit and Regenerate with its reason", () => {
    const locked: DocumentVM = {
      status: "locked",
      variant: "paper",
      structure: BASE.structure,
      title: BASE.title,
      watermark: false,
      lockedReason: "Locked with the engagement archive",
      actions: BASE.actions,
    };
    cockpit(locked);
    const edit = screen.getByRole<HTMLButtonElement>("button", { name: /Edit/ });
    expect(edit.disabled).toBe(true);
    expect(edit.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getAllByText("Locked with the engagement archive").length).toBeGreaterThan(0);
  });
});
