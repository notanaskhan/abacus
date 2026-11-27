// F-08-T30 (DEC-6028; F-08 §5 C3; P-35, DEC-24; INV-1, INV-5): tracked changes and comment anchors.
// - `trackInsert` (green ink, underlined) and `trackDelete` (red ink, struck) marks carry the
//   change id, author, initials, time, `viaAgent` and `client`; each changed block gets the 2 px
//   amber change bar with the author's initials (a node decoration, no HTML written).
// - An agent draft enters only through `insertAgentDraft`: one transaction marked as the agent's,
//   which the guard refuses unless it only inserts text carrying a `viaAgent` insert mark (or
//   marks text deleted). The draft reads "<person> via Agent".
// - Accept and Reject are a named person's clicks (ChangeActions renders nothing for anyone else)
//   and only intents: the kit never applies them; the consumer's server does (P-35).
// - A comment anchor (`commentAnchor`, amber tint and dot) opens its C-29 thread; comments never
//   block sign-off (review notes do): `signOffBlockedBy` reads review notes only.
import { Mark, mergeAttributes } from "@tiptap/react";
import type { Mark as PmMark, Node as PmNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, type Transaction } from "@tiptap/pm/state";
import { AddMarkStep, ReplaceStep } from "@tiptap/pm/transform";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";
import type { JSX } from "react";
import { type Actor, isPerson } from "../attribution/actor";
import { Button } from "../components/button";
import { viaAgent } from "../format";

export interface ChangeAttrs {
  id: string;
  author: string;
  initials: string;
  at: string;
  viaAgent: boolean;
  client: boolean;
}

const CHANGE_ATTRS = {
  id: { default: "" },
  author: { default: "" },
  initials: { default: "" },
  at: { default: "" },
  viaAgent: { default: false },
  client: { default: false },
} as const;

function changeAttributes(): Record<string, { default: unknown; renderHTML: () => object }> {
  return Object.fromEntries(
    Object.entries(CHANGE_ATTRS).map(([k, v]) => [
      k,
      { default: v.default, renderHTML: () => ({}) },
    ]),
  );
}

export const TrackInsert = Mark.create({
  name: "trackInsert",
  inclusive: false,
  excludes: "trackDelete",
  addAttributes: changeAttributes,
  parseHTML: () => [{ tag: "ins[data-change]" }],
  renderHTML({ mark, HTMLAttributes }) {
    return [
      "ins",
      mergeAttributes(HTMLAttributes, {
        "data-change": String(mark.attrs["id"]),
        "data-via-agent": mark.attrs["viaAgent"] === true ? "true" : undefined,
        title: changeTitle(mark.attrs as ChangeAttrs),
        class: "text-green-ink underline decoration-1 underline-offset-2 no-underline-skip",
      }),
      0,
    ];
  },
});

export const TrackDelete = Mark.create({
  name: "trackDelete",
  inclusive: false,
  excludes: "trackInsert",
  addAttributes: changeAttributes,
  parseHTML: () => [{ tag: "del[data-change]" }],
  renderHTML({ mark, HTMLAttributes }) {
    return [
      "del",
      mergeAttributes(HTMLAttributes, {
        "data-change": String(mark.attrs["id"]),
        "data-via-agent": mark.attrs["viaAgent"] === true ? "true" : undefined,
        title: changeTitle(mark.attrs as ChangeAttrs),
        class: "text-red-ink line-through",
      }),
      0,
    ];
  },
});

export const CommentAnchor = Mark.create({
  name: "commentAnchor",
  inclusive: false,
  addAttributes: () => ({ thread: { default: "", renderHTML: () => ({}) } }),
  parseHTML: () => [{ tag: "span[data-comment]" }],
  renderHTML({ mark }) {
    return [
      "span",
      {
        "data-comment": String(mark.attrs["thread"]),
        class:
          "rounded-[2px] bg-amber-tint after:ml-[2px] after:inline-block after:size-[6px] after:rounded-full after:bg-amber after:align-super after:content-['']",
      },
      0,
    ];
  },
});

/** The words on a change: "Hannah Leclerc via Agent" for the agent's draft, the name otherwise. */
export function changeTitle(change: Pick<ChangeAttrs, "author" | "viaAgent">): string {
  return change.viaAgent ? viaAgent(change.author) : change.author;
}

// --- the change bar ----------------------------------------------------------------------------

function changedBlocks(doc: PmNode): DecorationSet {
  const decorations: Decoration[] = [];
  doc.descendants((node, pos) => {
    if (!node.isTextblock) return true;
    const marks: PmMark[] = [];
    node.forEach((child) => {
      marks.push(...child.marks);
    });
    const change = marks.find(
      (m) => m.type.name === "trackInsert" || m.type.name === "trackDelete",
    );
    if (change !== undefined) {
      const attrs = change.attrs as ChangeAttrs;
      const initials = attrs.viaAgent ? viaAgent(attrs.initials) : attrs.initials;
      decorations.push(
        Decoration.node(pos, pos + node.nodeSize, {
          class:
            "relative border-l-2 border-amber pl-[6px] before:absolute before:-left-[30px] before:text-[8px] before:text-amber-ink before:content-[attr(data-change-initials)]",
          "data-change-initials": initials,
        }),
      );
    }
    return false;
  });
  return DecorationSet.create(doc, decorations);
}

export const changeBarKey = new PluginKey<DecorationSet>("abacus-change-bar");

export function changeBarPlugin(): Plugin<DecorationSet> {
  return new Plugin<DecorationSet>({
    key: changeBarKey,
    state: {
      init: (_, state) => changedBlocks(state.doc),
      apply: (tr, set) => (tr.docChanged ? changedBlocks(tr.doc) : set),
    },
    props: {
      decorations: (state) => changeBarKey.getState(state),
    },
  });
}

// --- agent drafts ------------------------------------------------------------------------------

export const AGENT_META = "abacus-agent-draft";

function isAgentInsert(marks: readonly PmMark[]): boolean {
  return marks.some((m) => m.type.name === "trackInsert" && m.attrs["viaAgent"] === true);
}

/** An agent transaction may only insert text marked as its tracked insert, or mark text
 * deleted; nothing it does is ever untracked (INV-1). */
export function agentDraftAllowed(tr: Transaction): boolean {
  if (tr.getMeta(AGENT_META) !== true) return true;
  return tr.steps.every((step) => {
    if (step instanceof AddMarkStep) {
      return step.mark.type.name === "trackDelete" && step.mark.attrs["viaAgent"] === true;
    }
    if (step instanceof ReplaceStep) {
      const json = step.toJSON() as { from: number; to: number };
      if (json.from !== json.to) return false; // no deletion: a deletion is a trackDelete mark
      let ok = true;
      step.slice.content.descendants((node) => {
        if (node.isText && !isAgentInsert(node.marks)) ok = false;
        return true;
      });
      return ok;
    }
    return false;
  });
}

export function agentDraftPlugin(): Plugin {
  return new Plugin({
    key: new PluginKey("abacus-agent-draft"),
    filterTransaction: (tr) => agentDraftAllowed(tr),
  });
}

/** The assistant's draft, inserted at `at` as one tracked change attributed "<person> via Agent". */
export function insertAgentDraft(
  view: EditorView,
  draft: { at: number; text: string; id: string; person: string; initials: string; time: string },
): boolean {
  const mark = view.state.schema.marks["trackInsert"];
  if (mark === undefined) return false;
  const text = view.state.schema.text(draft.text, [
    mark.create({
      id: draft.id,
      author: draft.person,
      initials: draft.initials,
      at: draft.time,
      viaAgent: true,
      client: false,
    }),
  ]); // fmt: skip
  const before = view.state.doc;
  view.dispatch(view.state.tr.insert(draft.at, text).setMeta(AGENT_META, true));
  return view.state.doc !== before;
}

// --- reads ---------------------------------------------------------------------------------------

export interface OpenChange extends ChangeAttrs {
  kind: "insert" | "delete";
  text: string;
}

export function openChanges(doc: PmNode): OpenChange[] {
  const byId = new Map<string, OpenChange>();
  doc.descendants((node) => {
    if (!node.isText) return true;
    for (const m of node.marks) {
      if (m.type.name !== "trackInsert" && m.type.name !== "trackDelete") continue;
      const attrs = m.attrs as ChangeAttrs;
      const found = byId.get(attrs.id);
      if (found === undefined) {
        byId.set(attrs.id, {
          ...attrs,
          kind: m.type.name === "trackInsert" ? "insert" : "delete",
          text: node.text ?? "",
        });
      } else {
        found.text += node.text ?? "";
      }
    }
    return true;
  });
  return [...byId.values()];
}

export function commentThreads(doc: PmNode): string[] {
  const threads = new Set<string>();
  doc.descendants((node) => {
    for (const m of node.marks)
      if (m.type.name === "commentAnchor") threads.add(String(m.attrs["thread"]));
    return true;
  });
  return [...threads];
}

/** Why "Sign off…" is disabled, or null. Comments never block sign-off; review notes do. */
export function signOffBlockedBy(open: { reviewNotes: number; comments: number }): string | null {
  if (open.reviewNotes === 0) return null;
  return open.reviewNotes === 1
    ? "1 open review note"
    : `${String(open.reviewNotes)} open review notes`;
}

// --- accept and reject ---------------------------------------------------------------------------

/** Accept / Reject on one change: a named person's clicks, and only intents (P-35, DEC-24). */
export function ChangeActions({
  change,
  actor,
  onAccept,
  onReject,
}: {
  change: Pick<ChangeAttrs, "id" | "author" | "viaAgent" | "client">;
  actor: Actor;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
}): JSX.Element | null {
  if (!isPerson(actor)) return null;
  return (
    <span data-change-actions={change.id} className="inline-flex gap-[6px]">
      <span className="text-[11.5px] text-ink-3">{changeTitle(change)}</span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          onAccept(change.id);
        }}
      >
        Accept
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => {
          onReject(change.id);
        }}
      >
        Reject
      </Button>
    </span>
  );
}
