// ac-test-author: ayushkbhatia
// F-06-T17 (ADR-078): the independent suite for the T10 DocumentOnWell kit, written from the row
// and F-06.md §5.2 (SPEC-400 AC-19, AC-21; ADR P-25; INV-1, INV-2, INV-5; ADR-111, DEC-79), not
// from the code: no markup path, citations only with a typed verified locator, Approve a person's
// HumanAction that opens a dialog (SHL-12 is the consumer's) and does nothing else, Locked read
// only, a person's edit stays marked across a regenerate, attribution words, and no model text or
// agent Drafting state on a client- or agency-facing variant unless `modelTextToClients` is passed.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Actor } from "../../attribution/actor";
import type { CitationView } from "../../tracing/types";
import { type DocBlock, DocBlocks } from "./DocBlocks";
import { DocumentOnWell, type DocumentOnWellProps } from "./DocumentOnWell";
import type { DocumentVM, DocumentVariant } from "./types";

afterEach(cleanup);

const COPY: DocumentOnWellProps["copy"] = {
  edit: "Edit",
  regenerate: "Regenerate…",
  drafting: "Accrued Agent is drafting the memo",
  rendering: "Preparing the letter",
  watermark: "DRAFT",
  variables: "Variables",
};
const TOOLBAR = {
  firm: "Brightwater Hale",
  nav: [],
  active: "Engagements",
} as unknown as DocumentOnWellProps["toolbar"];
const SAMUEL: Actor = { kind: "human", name: "Samuel Ito" };

const VERIFIED: CitationView = {
  n: 1,
  title: "Ridgeline 2025 trial balance",
  quote: "1,231,600",
  loc: "Investments!D8",
  match: null,
};

function vm(extra: Partial<DocumentVM> = {}): DocumentVM {
  return {
    status: "draft",
    variant: "paper",
    structure: {
      kind: "clauses",
      clauses: [{ id: "scope", label: "Scope of services", on: true }],
      variables: [{ id: "fee", label: "Fee", value: "$18,500 fixed" }],
    },
    title: "Engagement letter",
    watermark: true,
    actions: { edit: true, regenerate: true, approve: { actor: SAMUEL, object: "letter" } },
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

const AGENT_PARAGRAPH: DocBlock = {
  kind: "p",
  provenance: "agent",
  segments: [{ kind: "text", text: "The agent's reading of the §754 deadline." }],
};
const TEMPLATE_PARAGRAPH: DocBlock = {
  kind: "p",
  provenance: "template",
  segments: [
    { kind: "text", text: "A fixed fee of " },
    { kind: "fact", text: "$18,500" },
  ],
};

describe("no markup path", () => {
  it("the kit's source never sets HTML", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    for (const name of readdirSync(dir).filter(
      (f) => /\.tsx?$/u.test(f) && !f.includes(".test."),
    )) {
      const source = readFileSync(join(dir, name), "utf8");
      expect(source, name).not.toMatch(
        /dangerouslySetInnerHTML|\.innerHTML\s*=|insertAdjacentHTML/u,
      );
    }
  });

  it.each(["<b>bold</b>", "**bold**", "<script>alert(1)</script>", "<img src=x onerror=1>"])(
    "prints %s as its characters on every variant",
    (hostile) => {
      for (const variant of ["paper", "letter", "email"] as const) {
        const { container } = render(
          <DocBlocks
            variant={variant}
            blocks={[
              { kind: "p", provenance: "template", segments: [{ kind: "text", text: hostile }] },
            ]}
          />,
        );
        expect(container.textContent).toContain(hostile);
        expect(container.querySelector("b, strong, script, img")).toBeNull();
        cleanup();
      }
    },
  );

  it("model markup in an agent block on the paper renders as text, not as markup", () => {
    const { container } = render(
      <DocBlocks
        variant="paper"
        blocks={[{ ...AGENT_PARAGRAPH, segments: [{ kind: "text", text: "# Heading *em*" }] }]}
      />,
    );
    expect(container.querySelector("h1, h2, em")).toBeNull();
  });
});

describe("locator-only citations (INV-2)", () => {
  const cite = (segment: Partial<{ verified: boolean; loc: string; n: number }>) => (
    <DocBlocks
      variant="paper"
      blocks={[
        {
          kind: "p",
          provenance: "template",
          segments: [
            { kind: "text", text: "Investments [3] " },
            {
              kind: "cite",
              n: segment.n ?? 1,
              citation: { ...VERIFIED, loc: segment.loc ?? VERIFIED.loc },
              ...(segment.verified === undefined ? {} : { verified: segment.verified }),
            },
          ],
        },
      ]}
    />
  );

  it("draws a marker for a typed, verified locator", () => {
    const { container } = render(cite({ verified: true }));
    expect(container.textContent).toContain("Investments [3]");
    expect(container.querySelectorAll("button, [role='button']").length).toBe(1);
  });

  it.each([
    ["unverified", { verified: false }],
    ["unflagged", {}],
    ["an empty locator", { verified: true, loc: "  " }],
    ["a number that is not the citation's", { verified: true, n: 2 }],
  ])("draws nothing for %s", (_name, segment) => {
    const { container } = render(cite(segment));
    expect(container.querySelectorAll("button, [role='button']").length).toBe(0);
    expect(container.textContent).toContain("[3]");
  });
});

describe("Approve: a person's HumanAction (INV-1)", () => {
  it("opens a dialog and only calls onApprove", () => {
    const onApprove = vi.fn();
    const onEdit = vi.fn();
    const onRegenerate = vi.fn();
    well(vm(), { onApprove, onEdit, onRegenerate });
    const approve = screen.getByRole("button", { name: "Approve letter…" });
    expect(approve.getAttribute("data-human-verb")).toBe("Approve");
    fireEvent.click(approve);
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onEdit).not.toHaveBeenCalled();
    expect(onRegenerate).not.toHaveBeenCalled();
  });

  it.each<[string, Actor]>([
    ["the agent", { kind: "agent" }],
    ["a person via the agent", { kind: "agent_assisted", person: "Hannah Leclerc" }],
    ["a policy", { kind: "policy", name: "BH letters", version: 2 }],
    ["the system", { kind: "system" }],
  ])("never renders for %s", (_who, actor) => {
    well(vm({ actions: { edit: true, regenerate: true, approve: { actor } } }));
    expect(screen.queryByRole("button", { name: /^Approve/u })).toBeNull();
    expect(document.querySelector("[data-human-verb]")).toBeNull();
  });
});

describe("attribution words (INV-5)", () => {
  it("names the person who approved", () => {
    well(
      vm({
        status: "approved",
        watermark: false,
        approvedBy: { actor: SAMUEL, when: "Sep 14, 9:40 AM" },
      }),
    );
    expect(screen.getByText("Samuel Ito · Sep 14, 9:40 AM")).toBeTruthy();
  });

  it.each<[string, Actor]>([
    ["the agent", { kind: "agent" }],
    ["a person via the agent", { kind: "agent_assisted", person: "Hannah Leclerc" }],
    ["the system", { kind: "system" }],
  ])("never reads as approved by %s", (_who, actor) => {
    well(
      vm({ status: "approved", watermark: false, approvedBy: { actor, when: "Sep 14, 9:40 AM" } }),
    );
    const text = document.body.textContent;
    expect(text).not.toContain("Accrued Agent");
    expect(text).not.toContain("via Agent");
    expect(text).not.toContain("System ·");
  });

  it("marks a person's edit with the consumer's words", () => {
    render(
      <DocBlocks
        variant="paper"
        blocks={[{ ...AGENT_PARAGRAPH, editedBy: "Hannah Leclerc" }]}
        editedLabel={(name) => `Edited by ${name}`}
      />,
    );
    expect(screen.getByText("Edited by Hannah Leclerc")).toBeTruthy();
  });
});

describe("Locked is read-only", () => {
  it("disables Edit, Regenerate, Approve, every clause toggle and every variable, saying why", () => {
    well(vm({ status: "locked", watermark: false, lockedReason: "Signed and filed" }), {
      onToggleSection: vi.fn(),
      onVariable: vi.fn(),
    });
    for (const name of ["Edit", "Regenerate…", "Approve letter…"]) {
      const control = screen.queryByRole("button", { name });
      if (control !== null) expect((control as HTMLButtonElement).disabled).toBe(true);
    }
    for (const toggle of screen.getAllByRole("switch")) {
      expect((toggle as HTMLButtonElement).disabled).toBe(true);
    }
    for (const input of Array.from(document.querySelectorAll("input, textarea"))) {
      const field = input as HTMLInputElement;
      expect(field.disabled || field.readOnly).toBe(true);
    }
    expect(screen.getAllByText("Signed and filed").length).toBeGreaterThan(0);
  });
});

describe("Regenerate keeps a person's edits marked", () => {
  it("asks first, calls only onRegenerate, and the edit mark survives the new blocks", () => {
    const onRegenerate = vi.fn();
    const blocks = (n: number): DocBlock[] => [
      { ...AGENT_PARAGRAPH, segments: [{ kind: "text", text: `Draft ${String(n)}` }] },
      { ...AGENT_PARAGRAPH, editedBy: "Hannah Leclerc" },
    ];
    const view = well(vm(), { onRegenerate });
    const regenerate = screen.getByRole("button", { name: "Regenerate…" });
    fireEvent.click(regenerate);
    expect(onRegenerate).toHaveBeenCalledTimes(1);
    view.unmount();
    const { rerender } = render(<DocBlocks variant="paper" blocks={blocks(1)} />);
    expect(screen.getByText("Edited by Hannah Leclerc")).toBeTruthy();
    rerender(<DocBlocks variant="paper" blocks={blocks(2)} />);
    expect(screen.getByText("Edited by Hannah Leclerc")).toBeTruthy();
  });
});

describe("no model text to clients while ADR P-25 is off (ADR-111, DEC-79)", () => {
  const clientFacing: readonly DocumentVariant[] = ["letter", "email"];

  it.each(clientFacing)("%s drops agent prose and keeps template text", (variant) => {
    const { container } = render(
      <DocBlocks
        variant={variant}
        blocks={[
          { kind: "h", level: 3, text: "Agent heading", provenance: "agent" },
          AGENT_PARAGRAPH,
          TEMPLATE_PARAGRAPH,
        ]}
      />,
    );
    expect(container.textContent).not.toContain("Agent heading");
    expect(container.textContent).not.toContain("the §754 deadline");
    expect(container.textContent).toContain("A fixed fee of $18,500");
  });

  it.each(clientFacing)("%s has no agent Drafting state", (variant) => {
    well(vm({ status: "drafting", variant, watermark: false }));
    expect(document.body.textContent).not.toContain("Accrued Agent is drafting");
    expect(document.querySelector("[data-document='drafting']")).toBeNull();
  });

  it.each(clientFacing)(
    "%s shows agent text only when the consumer passes modelTextToClients",
    (variant) => {
      render(<DocBlocks variant={variant} modelTextToClients blocks={[AGENT_PARAGRAPH]} />);
      expect(screen.getByText(/the §754 deadline/u)).toBeTruthy();
    },
  );

  it("the firm-internal paper shows the agent's drafting state", () => {
    well(vm({ status: "drafting" }));
    const header = document.body;
    expect(
      within(header).getAllByText("Accrued Agent is drafting the memo").length,
    ).toBeGreaterThan(0);
  });
});
