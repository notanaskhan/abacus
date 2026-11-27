// @vitest-environment jsdom
// F-08-T30 (TASK-9023; DEC-6028; F-08 §5 C3). Row acceptance: "Agent drafts enter only as tracked
// changes attributed '<person> via Agent', accept and reject fire only from a human click, and
// comments never disable Sign off."
import type { EditorView } from "@tiptap/pm/view";
import type { JSONContent } from "@tiptap/react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ChangeActions,
  AGENT_META,
  insertAgentDraft,
  openChanges,
  signOffBlockedBy,
} from "./changes";
import { DocumentEditor } from "./DocumentEditor";

afterEach(cleanup);

const KEPT =
  "…through October 27, 2026, the date the financial statements were available to be issued.";
const DOC: JSONContent = {
  type: "doc",
  content: [
    {
      type: "section",
      attrs: { key: "note_9", label: "Note 9" },
      content: [
        {
          type: "heading",
          attrs: { level: 2 },
          content: [{ type: "text", text: "9 Subsequent events" }],
        },
        {
          type: "paragraph",
          content: [
            { type: "text", text: KEPT },
            {
              type: "text",
              text: " Dividends paid",
              marks: [{ type: "commentAnchor", attrs: { thread: "th-dividends" } }],
            },
          ],
        },
      ],
    },
  ],
};
const LEASE =
  "On July 24, 2026, the Company entered into a ten-year lease for a distribution center in Grand Junction, Colorado, commencing January 1, 2027, with base rent of $34,000 per month.";

function editorView(): EditorView {
  const root: (HTMLElement & { editor?: { view: EditorView } }) | null =
    document.querySelector(".ProseMirror");
  const view = root?.editor?.view;
  if (view === undefined) throw new Error("no editor view");
  return view;
}

function paragraphStart(view: EditorView): number {
  let at = -1;
  view.state.doc.descendants((node, pos) => {
    if (at < 0 && node.type.name === "paragraph") at = pos + 1;
    return true;
  });
  return at;
}

describe("F-08-T30 tracked changes", () => {
  it("acceptance: an agent draft enters only as a tracked change attributed '<person> via Agent'", () => {
    render(<DocumentEditor content={DOC} label="Notes" />);
    const view = editorView();
    act(() => {
      insertAgentDraft(view, {
        at: paragraphStart(view),
        text: `${LEASE} `,
        id: "chg-note9",
        person: "Hannah Leclerc",
        initials: "HL",
        time: "2026-10-21T14:04",
      });
    });
    const [change] = openChanges(view.state.doc);
    expect([change?.kind, change?.viaAgent, change?.author, change?.text]).toEqual([
      "insert",
      true,
      "Hannah Leclerc",
      `${LEASE} `,
    ]);
    const ins = document.querySelector('ins[data-change="chg-note9"]');
    expect(ins?.getAttribute("title")).toBe("Hannah Leclerc via Agent");
    expect(ins?.getAttribute("data-via-agent")).toBe("true");
    // The change bar carries the initials, "HL via Agent".
    expect(document.querySelector('[data-change-initials="HL via Agent"]')).not.toBeNull();
  });

  it("acceptance: an agent transaction that writes untracked text, or deletes, is refused", () => {
    render(<DocumentEditor content={DOC} label="Notes" />);
    const view = editorView();
    const before = JSON.stringify(view.state.doc.toJSON());
    act(() => {
      view.dispatch(
        view.state.tr
          .insertText("Untracked agent words. ", paragraphStart(view))
          .setMeta(AGENT_META, true),
      );
    });
    act(() => {
      const at = paragraphStart(view);
      view.dispatch(view.state.tr.delete(at, at + 5).setMeta(AGENT_META, true));
    });
    expect(JSON.stringify(view.state.doc.toJSON())).toBe(before);
  });

  it("acceptance: accept and reject fire only from a named person's click", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    const change = { id: "chg-note9", author: "Hannah Leclerc", viaAgent: true, client: false };
    const { rerender } = render(
      <ChangeActions
        change={change}
        actor={{ kind: "agent" }}
        onAccept={onAccept}
        onReject={onReject}
      />,
    );
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull(); // nothing for the agent
    rerender(
      <ChangeActions
        change={change}
        actor={{ kind: "human", name: "Hannah Leclerc" }}
        onAccept={onAccept}
        onReject={onReject}
      />,
    );
    expect(onAccept).not.toHaveBeenCalled();
    expect(onReject).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect(onAccept).toHaveBeenCalledWith("chg-note9");
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onReject).toHaveBeenCalledWith("chg-note9");
    expect(screen.getByText("Hannah Leclerc via Agent")).toBeTruthy();
  });

  it("acceptance: comments never disable Sign off; review notes do", () => {
    expect(signOffBlockedBy({ reviewNotes: 0, comments: 3 })).toBeNull();
    expect(signOffBlockedBy({ reviewNotes: 1, comments: 0 })).toBe("1 open review note");
    expect(signOffBlockedBy({ reviewNotes: 2, comments: 9 })).toBe("2 open review notes");
  });

  it("a comment anchor opens its thread in the dock", () => {
    const onOpenComment = vi.fn();
    render(<DocumentEditor content={DOC} label="Notes" onOpenComment={onOpenComment} />);
    const view = editorView();
    let at = -1;
    view.state.doc.descendants((node, pos) => {
      if (node.isText && node.marks.some((m) => m.type.name === "commentAnchor")) at = pos + 2;
      return true;
    });
    act(() => {
      view.someProp("handleClick", (f) => f(view, at, new MouseEvent("click")));
    });
    expect(onOpenComment).toHaveBeenCalledWith("th-dividends");
    expect(document.querySelector('[data-comment="th-dividends"]')?.className).toContain(
      "bg-amber-tint",
    );
  });
});
