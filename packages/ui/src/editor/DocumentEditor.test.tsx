// @vitest-environment jsdom
// F-08-T28 (TASK-9021; DEC-6026): the T20 engine. Row acceptance: "The editor renders only
// through React and ProseMirror nodes, pasted HTML lands as plain text, CSP style-src 'self'
// holds, and another editor's section is read-only with its banner."
import { TextSelection } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import type { JSONContent } from "@tiptap/react";
import { act, cleanup, render, screen } from "@testing-library/react";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import type { PresencePeer } from "../collab/presence";
import { DocumentEditor } from "./DocumentEditor";
import { plainPaste } from "./paste";
import type { SectionLock, StatementTableAttrs } from "./types";

afterEach(cleanup);

const TABLE: StatementTableAttrs = {
  key: "balance_sheets",
  columns: ["2026", "2025"],
  rows: [
    { key: "assets", caption: "ASSETS", indent: 0, amounts: [], heading: true },
    { key: "cash", caption: "Cash", indent: 1, amounts: [2140000, 2610000], dollar: true },
    { key: "reserve", caption: "Obsolescence reserve", indent: 1, amounts: [-486000, null] },
    {
      key: "total_assets",
      caption: "Total assets",
      indent: 0,
      amounts: [26410000, 23200000],
      dollar: true,
      rule: "double_below",
    },
  ],
};

const DOC: JSONContent = {
  type: "doc",
  content: [
    {
      type: "section",
      attrs: { key: "balance_sheets", label: "Balance sheets" },
      content: [
        {
          type: "heading",
          attrs: { level: 1 },
          content: [{ type: "text", text: "Balance Sheets" }],
        },
        { type: "statementTable", attrs: TABLE },
      ],
    },
    {
      type: "section",
      attrs: { key: "note_5", label: "Note 5" },
      content: [
        {
          type: "heading",
          attrs: { level: 2 },
          content: [{ type: "text", text: "5 Long-term debt" }],
        },
        { type: "paragraph", content: [{ type: "text", text: "The Company has a term loan." }] },
      ],
    },
  ],
};

const HANNAH: PresencePeer = {
  userId: "u-hl",
  name: "Hannah Leclerc",
  tint: 1,
  idle: false,
  anchor: { kind: "section", key: "note_5" },
  activity: "editing",
  joinedAt: 1,
  lastSeenAt: 2,
};

function editorView(): { view: EditorView } {
  // TipTap hangs its editor off the ProseMirror element.
  const root: (HTMLElement & { editor?: { view: EditorView } }) | null =
    document.querySelector(".ProseMirror");
  const view = root?.editor?.view;
  if (view === undefined) throw new Error("no editor view");
  return { view };
}

describe("F-08-T28 DocumentEditor", () => {
  it("acceptance: renders only through React and ProseMirror nodes, with no injected style", async () => {
    const before = document.head.querySelectorAll("style").length;
    render(<DocumentEditor content={DOC} label="Granite Peak FY2026 financial statements" />);
    expect(
      screen.getByRole("textbox", { name: "Granite Peak FY2026 financial statements" }),
    ).toBeTruthy();
    // injectCSS: false — TipTap adds no <style> (CSP style-src 'self').
    expect(document.head.querySelectorAll("style").length).toBe(before);
    expect(document.querySelector("style[data-tiptap-style]")).toBeNull();
    // The statement table is a React node view, read-only, with figures on paper.
    expect(await screen.findByText("$ 2,140,000")).toBeTruthy();
    const table = document.querySelector(
      '[data-statement="balance_sheets"][data-readonly="true"]',
    );
    expect(table?.getAttribute("contenteditable")).toBe("false");
    expect(screen.getByText("$ 2,140,000")).toBeTruthy();
    expect(screen.getByText("(486,000)")).toBeTruthy(); // negatives in parentheses
    expect(screen.getByText("$ 26,410,000")).toBeTruthy();
  });

  it("acceptance: the kit's source never writes HTML into the DOM (CSP and the lint ban)", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    for (const file of readdirSync(dir).filter(
      (f) => /\.tsx?$/.test(f) && !f.includes(".test."),
    )) {
      const text = readFileSync(join(dir, file), "utf8");
      for (const banned of [
        "dangerouslySetInnerHTML",
        "innerHTML",
        "insertAdjacentHTML",
        "createContextualFragment",
        "injectCSS: true",
      ]) {
        expect(text.includes(banned), `${file} uses ${banned}`).toBe(false);
      }
    }
  });

  it("acceptance: pasted HTML lands as plain text", () => {
    render(<DocumentEditor content={DOC} label="Statements" />);
    const { view } = editorView();
    const end = view.state.doc.content.size - 2;
    act(() => {
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, end)));
    });
    let prevented = false;
    act(() => {
      plainPaste(view, {
        clipboardData: {
          getData: (t: string) =>
            t === "text/plain"
              ? " Matures 2028."
              : '<b onclick="x()">Matures 2028.</b><script>bad()</script>',
        },
        preventDefault: () => {
          prevented = true;
        },
      });
    });
    expect(prevented).toBe(true);
    const json = JSON.stringify(view.state.doc.toJSON());
    expect(json).toContain("Matures 2028.");
    expect(json).not.toContain("bold");
    expect(json).not.toContain("script");
    expect(document.querySelector(".ProseMirror b, .ProseMirror script")).toBeNull();
  });

  it("a statement table cannot be removed or changed by a transaction", () => {
    render(<DocumentEditor content={DOC} label="Statements" />);
    const { view } = editorView();
    const before = JSON.stringify(view.state.doc.toJSON());
    act(() => {
      view.dispatch(view.state.tr.delete(0, view.state.doc.content.size)); // select-all delete
    });
    expect(JSON.stringify(view.state.doc.toJSON())).toBe(before);
  });

  it("acceptance: another editor's section is read-only here, with its banner", () => {
    const lock: SectionLock = { section: "note_5", label: "Note 5", peer: HANNAH };
    render(<DocumentEditor content={DOC} label="Statements" locks={[lock]} />);
    expect(screen.getByRole("status").textContent).toContain("Hannah Leclerc is editing Note 5");
    const { view } = editorView();
    let notePos = -1;
    view.state.doc.descendants((node, pos) => {
      if (node.isText && node.text === "The Company has a term loan.") notePos = pos;
      return true;
    });
    const before = JSON.stringify(view.state.doc.toJSON());
    act(() => {
      view.dispatch(view.state.tr.insertText("X", notePos + 1));
    });
    expect(JSON.stringify(view.state.doc.toJSON())).toBe(before); // refused inside Note 5
    let headPos = -1;
    view.state.doc.descendants((node, pos) => {
      if (node.isText && node.text === "Balance Sheets") headPos = pos;
      return true;
    });
    act(() => {
      view.dispatch(view.state.tr.insertText("The ", headPos));
    });
    expect(JSON.stringify(view.state.doc.toJSON())).toContain("The Balance Sheets"); // elsewhere ok
  });

  it("one editable editor per page: a second mounts read-only until the first leaves", () => {
    const first = render(<DocumentEditor content={DOC} label="First" />);
    const second = render(<DocumentEditor content={DOC} label="Second" />);
    const flags = [...document.querySelectorAll("[data-document-editor]")].map((e) =>
      e.getAttribute("data-editable"),
    );
    expect(flags).toEqual(["true", "false"]);
    first.unmount();
    second.unmount();
  });
});
