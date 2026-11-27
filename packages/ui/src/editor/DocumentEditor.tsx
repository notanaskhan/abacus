// F-08-T28 (DEC-6026; ADR P-59): the T20 editor engine. TipTap with the custom schema, created
// with `injectCSS: false` (CSP style-src 'self'), drawn only through React and ProseMirror nodes;
// pasted or dropped HTML lands as plain text; statement tables are read-only node views; and a
// section another person is editing is read-only here with its banner. One editable editor per
// page: a second mounts read-only until the first leaves (no CRDT, one editor at a time).
import { EditorContent, useEditor, type JSONContent } from "@tiptap/react";
import { type JSX, useEffect, useMemo, useRef, useState } from "react";
import { SectionEditingBanner } from "../collab/presence";
import { MatchScope } from "../tracing/match";
import { agentDraftPlugin, changeBarPlugin } from "./changes";
import { type LinkedValueHandlers, LinkedValueProvider } from "./linked";
import { plainDrop, plainPaste } from "./paste";
import { protectPlugin } from "./protect";
import { documentExtensions } from "./schema";
import type { SectionLock } from "./types";
import { Extension } from "@tiptap/react";

export interface DocumentEditorProps {
  /** The document, as the consumer's server sent it (sections of blocks). */
  content: JSONContent;
  /** The accessible name of the editing surface ("Granite Peak FY2026 financial statements"). */
  label: string;
  editable?: boolean;
  /** Sections other people are editing now (from the presence source). */
  locks?: readonly SectionLock[];
  /** Every accepted change, as the document after it (the consumer sends steps; T31). */
  onChange?: (doc: JSONContent) => void;
  /** F-08-T29: each linked value's lineage and the Relink / open-lineage intents. */
  linked?: LinkedValueHandlers;
  /** F-08-T30: a comment anchor's thread opens in the dock (C-29). */
  onOpenComment?: (thread: string) => void;
}

const NO_LINEAGE: LinkedValueHandlers = { lineage: () => undefined };

// One editable editor per page (ADR P-59): the first to mount holds the pen.
let pen: symbol | null = null;

function usePen(wanted: boolean): boolean {
  const mine = useRef(Symbol("editor"));
  const [held, setHeld] = useState(false);
  useEffect(() => {
    if (!wanted) return undefined;
    if (pen === null) {
      pen = mine.current;
      setHeld(true);
    }
    return () => {
      if (pen === mine.current) pen = null;
    };
  }, [wanted]);
  return wanted && held;
}

export function DocumentEditor({
  content,
  label,
  editable = true,
  locks = [],
  onChange,
  linked = NO_LINEAGE,
  onOpenComment,
}: DocumentEditorProps): JSX.Element {
  const openComment = useRef(onOpenComment);
  openComment.current = onOpenComment;
  const holding = usePen(editable);
  const locked = useRef<ReadonlySet<string>>(new Set());
  locked.current = useMemo(() => new Set(locks.map((l) => l.section)), [locks]);
  const guard = useMemo(
    () =>
      Extension.create({
        name: "abacusProtect",
        addProseMirrorPlugins: () => [
          protectPlugin(() => locked.current),
          agentDraftPlugin(),
          changeBarPlugin(),
        ],
      }),
    [],
  );
  const editor = useEditor({
    extensions: [...documentExtensions(), guard],
    content,
    editable: holding,
    injectCSS: false,
    immediatelyRender: true,
    editorProps: {
      attributes: { "aria-label": label, "aria-multiline": "true", role: "textbox" },
      handlePaste: (view, event) => plainPaste(view, event),
      handleDrop: (view, event) => plainDrop(view, event),
      handleClick: (view, pos) => {
        const anchor = view.state.doc
          .resolve(pos)
          .marks()
          .find((m) => m.type.name === "commentAnchor");
        const thread: unknown = anchor?.attrs["thread"];
        if (typeof thread === "string" && thread !== "") {
          openComment.current?.(thread);
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor: e }) => onChange?.(e.getJSON()),
  });
  useEffect(() => {
    editor.setEditable(holding);
  }, [editor, holding]);
  return (
    <div
      data-document-editor
      data-editable={holding ? "true" : "false"}
      className="flex flex-col gap-[8px]"
    >
      {locks.map((lock) => (
        <SectionEditingBanner key={lock.section} peer={lock.peer} section={lock.label} />
      ))}
      <MatchScope>
        <LinkedValueProvider value={linked}>
          <EditorContent
            editor={editor}
            className="font-doc text-[9.5px] text-doc-ink outline-none"
          />
        </LinkedValueProvider>
      </MatchScope>
    </div>
  );
}
