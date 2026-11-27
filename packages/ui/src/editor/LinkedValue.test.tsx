// @vitest-environment jsdom
// F-08-T29 (TASK-9022; DEC-6027; C-37). Row acceptance: "A linked number cannot be typed over,
// deleted or pasted into, stale overrides show the Relink action on amber tint, and hover
// lights only that value."
import { TextSelection } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import type { JSONContent } from "@tiptap/react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentEditor } from "./DocumentEditor";
import { plainPaste } from "./paste";
import type { Lineage, LinkedValueAttrs } from "./linked";

afterEach(cleanup);

const value = (attrs: LinkedValueAttrs): JSONContent => ({ type: "linkedValue", attrs });
const INVENTORY: LinkedValueAttrs = {
  id: "inventory-2026",
  value: 11420000,
  source: "tb_linked",
  stale: false,
  dollar: false,
};
const LTD: LinkedValueAttrs = {
  id: "ltd-2026",
  value: 3200000,
  source: "override",
  stale: true,
  dollar: false,
};

const DOC: JSONContent = {
  type: "doc",
  content: [
    {
      type: "section",
      attrs: { key: "balance_sheets", label: "Balance sheets" },
      content: [
        {
          type: "paragraph",
          content: [{ type: "text", text: "Inventory, net " }, value(INVENTORY)],
        },
        { type: "paragraph", content: [{ type: "text", text: "Long-term debt " }, value(LTD)] },
      ],
    },
  ],
};

const LINEAGE: Record<string, Lineage> = {
  "inventory-2026": {
    title: "Inventory, net · June 30, 2026",
    subtitle: "TB-linked · 2 groups",
    groups: [
      { label: "Inventory", account: "1300 Inventory", amount: 11906000 },
      { label: "Obsolescence reserve", account: "1450 Inventory reserve", amount: -486000 },
    ],
  },
};

function editorView(): EditorView {
  const root: (HTMLElement & { editor?: { view: EditorView } }) | null =
    document.querySelector(".ProseMirror");
  const view = root?.editor?.view;
  if (view === undefined) throw new Error("no editor view");
  return view;
}

function linkedPos(view: EditorView, id: string): number {
  let at = -1;
  view.state.doc.descendants((node, pos) => {
    if (node.type.name === "linkedValue" && node.attrs["id"] === id) at = pos;
    return true;
  });
  return at;
}

async function mount(
  props: Partial<Parameters<typeof DocumentEditor>[0]> = {},
): Promise<EditorView> {
  render(
    <DocumentEditor
      content={DOC}
      label="Statements"
      linked={{ lineage: (id) => LINEAGE[id] }}
      {...props}
    />,
  );
  await screen.findByText("11,420,000");
  return editorView();
}

describe("F-08-T29 LinkedValue", () => {
  it("acceptance: a linked number cannot be typed over, deleted or pasted into", async () => {
    const view = await mount();
    const before = JSON.stringify(view.state.doc.toJSON());
    const at = linkedPos(view, "inventory-2026");
    act(() => {
      view.dispatch(view.state.tr.replaceWith(at, at + 1, view.state.schema.text("12,000,000")));
    }); // typed over
    act(() => {
      view.dispatch(view.state.tr.delete(at, at + 1));
    }); // deleted
    act(() => {
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, at, at + 1)));
      plainPaste(view, {
        clipboardData: { getData: () => "99" },
        preventDefault: () => undefined,
      });
    }); // pasted into
    expect(JSON.stringify(view.state.doc.toJSON())).toBe(before);
    expect(screen.getByText("11,420,000")).toBeTruthy();
    // Text beside it still edits.
    act(() => {
      view.dispatch(view.state.tr.insertText("Net ", 2));
    });
    expect(JSON.stringify(view.state.doc.toJSON())).toContain("Net Inventory, net");
    expect(linkedPos(view, "inventory-2026")).toBeGreaterThan(0);
  });

  it("acceptance: a stale override shows Relink on amber tint, and Relink is an intent", async () => {
    const onRelink = vi.fn();
    await mount({ linked: { lineage: (id) => LINEAGE[id], onRelink } });
    const stale = document.querySelector('[data-linked="ltd-2026"][data-stale="true"]');
    expect(stale).not.toBeNull();
    const figure = screen.getByRole("button", { name: "3,200,000, override, stale override" });
    expect(figure.className).toContain("bg-amber-tint");
    const relink = screen.getByRole("button", { name: "↺ Relink" });
    fireEvent.click(relink);
    expect(onRelink).toHaveBeenCalledWith("ltd-2026");
    // A TB-linked value carries neither.
    expect(document.querySelector('[data-linked="inventory-2026"][data-stale]')).toBeNull();
    expect(screen.getAllByRole("button", { name: "↺ Relink" })).toHaveLength(1);
  });

  it("acceptance: hover lights only that value, with its lineage", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await mount();
    const inventory = screen.getByRole("button", { name: "11,420,000, tb-linked" });
    const ltd = screen.getByRole("button", { name: "3,200,000, override, stale override" });
    act(() => {
      fireEvent.pointerEnter(inventory);
      vi.advanceTimersByTime(500);
    });
    expect(inventory.className).toContain("bg-match-bg");
    expect(ltd.className).not.toContain("bg-match-bg");
    expect(document.querySelectorAll("[data-lit]")).toHaveLength(1);
    const card = screen.getByRole("tooltip");
    expect(card.textContent).toContain("Inventory · 1300 Inventory");
    expect(card.textContent).toContain("(486,000)");
    expect(card.textContent).toContain("11,420,000");
    vi.useRealTimers();
  });

  it("every linked value carries the shared dotted underline", async () => {
    await mount();
    for (const b of screen.getAllByRole("button").filter((x) => x.hasAttribute("data-match"))) {
      expect(b.className).toContain("decoration-dotted");
    }
  });
});
