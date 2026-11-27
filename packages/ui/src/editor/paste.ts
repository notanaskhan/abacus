// F-08-T28 (DEC-6026): pasted or dropped content is hostile (ADR-052, ADR-064). HTML never
// reaches the schema: only the clipboard's plain text is inserted, as text, at the selection.
import type { EditorView } from "@tiptap/pm/view";

interface ClipboardLike {
  getData(type: string): string;
}

export function plainPaste(
  view: EditorView,
  event: { clipboardData?: ClipboardLike | null; preventDefault(): void },
): boolean {
  event.preventDefault();
  const text = event.clipboardData?.getData("text/plain") ?? "";
  if (text !== "" && view.editable) {
    view.dispatch(view.state.tr.insertText(text.replace(/\r\n?/g, "\n")));
  }
  return true; // handled: ProseMirror's own HTML parser never runs
}

export function plainDrop(
  view: EditorView,
  event: { dataTransfer?: ClipboardLike | null; preventDefault(): void },
): boolean {
  event.preventDefault();
  const text = event.dataTransfer?.getData("text/plain") ?? "";
  if (text !== "" && view.editable) view.dispatch(view.state.tr.insertText(text));
  return true;
}
